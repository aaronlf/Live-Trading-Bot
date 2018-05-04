# -*- coding: utf-8 -*-
"""
Created on Thu Apr 12 13:10:15 2018

@author: Aaron
"""

import pandas as pd
import ccxt
import ccxt2
import numpy as np


#------------------------------------------------------------------------------

exchanges = {
        'bitstamp':{},
        'bittrex':{},
        'coinmarketcap':{}, 
        'gateio':{},
        'kraken':{}
        }
euro_values = {}
BTC_values = {}


#------------------------------------------------------------------------------


def initialiseExchange(exchange):
    exch_obj = getattr(ccxt,exchange)()
    exch_obj.loadMarkets()
    exchanges[exchange] = exch_obj
    
    
def loadAllMarkets():
    for exchange in exchanges:
        try:
            initialiseExchange(exchange)
        except Exception as e:
            print(e)
    
def load_euro_and_BTC_values():    
    loadAllMarkets()
    euro_values['BTC'] = float(exchanges['kraken'].fetchTicker('BTC/EUR')['last'])
    euro_values['LTC'] = float(exchanges['bitstamp'].fetchTicker('LTC/EUR')['last'])
    euro_values['USDT'] = round(float(exchanges['coinmarketcap'].fetchTicker('USDT/EUR')['last']),4)
    euro_values['ETH'] = float(exchanges['bitstamp'].fetchTicker('ETH/EUR')['last'])
    BTC_values['USDT'] = round(1 / float(exchanges['bittrex'].fetchTicker('BTC/USDT')['last']),8)
    BTC_values['ETH'] = float(exchanges['bitstamp'].fetchTicker('ETH/BTC')['last'])
    BTC_values['LTC'] = float(exchanges['bittrex'].fetchTicker('LTC/BTC')['last'])


def convert_to_euro(initial_quote_paid,quote):    
    return initial_quote_paid * euro_values[quote]


def convert_to_BTC(initial_quote_paid,quote):   
    if quote == 'BTC':
        return initial_quote_paid
    else:
        return initial_quote_paid * BTC_values[quote]

#------------------------------------------------------------------------------
    

def profitabilityCalculator(BuyExchange,SellExchange):                        
    '''
    This function takes 2 exchange class instances as inputs. The output of 
    this function is a single-row dataframe giving the gross and net profits 
    made if arbitrage were executed across the two exchanges, given in € 
    and BTC values separately, as well as gross percentage profit and net 
    percentage profit (i.e. after withdrawals). It also contains the average 
    timestamp of execution and which exchange the base currency was bought 
    from and which it was sold on.
    '''
    orderbook_buyExchange = BuyExchange.orderbook
    orderbook_sellExchange = SellExchange.orderbook
    ccxtObject_buyExchange = BuyExchange.ccxtObject
    ccxtObject_sellExchange = SellExchange.ccxtObject
    
    base =  BuyExchange.BASE
    quote = BuyExchange.QUOTE
    tx_fee_buyExchange = ccxtObject_buyExchange.fees['trading']['taker']
    tx_fee_sellExchange = ccxtObject_sellExchange.fees['trading']['taker']
    ccxt2_buyExchange = getattr(ccxt2,BuyExchange.NAME)()
    ccxt2_sellExchange = getattr(ccxt2,SellExchange.NAME)()
    
    try:
        wd_fee_buyExchange = ccxt2_buyExchange.fees['funding']['withdraw'][base]
    except:
        wd_fee_buyExchange = None
    try:
        wd_fee_sellExchange = ccxt2_sellExchange.fees['funding']['withdraw'][quote]
    except:
        wd_fee_sellExchange = None
    volume_buyExchange = orderbook_buyExchange['volume']
    volume_sellExchange = orderbook_sellExchange['volume']
    maxVolume = min([volume_buyExchange,volume_sellExchange])
   
    # NEW
    if maxVolume > SellExchange.availableBalanceBASE:
        maxVolume = SellExchange.availableBalanceBASE
        
    
    ask_buyExchange = orderbook_buyExchange['price']
    bid_sellExchange = orderbook_sellExchange['price']
    
    initial_quote_paid = maxVolume * ask_buyExchange
    
    # NEW
    if initial_quote_paid > BuyExchange.availableBalanceQUOTE:
        initial_quote_paid = BuyExchange.availableBalanceQUOTE
        maxVolume = initial_quote_paid / ask_buyExchange
    
    
    initial_base_received = maxVolume * (1 - tx_fee_buyExchange)
    initial_quote_received = (  (maxVolume * bid_sellExchange) 
                              * (1 - tx_fee_sellExchange) )
    if wd_fee_buyExchange:
        initial_base_after_withdrawal = initial_base_received - wd_fee_buyExchange         
        quote_gained_after_withdrawal = ( initial_base_after_withdrawal 
                                        * bid_sellExchange 
                                        * (1 - tx_fee_sellExchange) )
    else:
        quote_gained_after_withdrawal = 0
    quote_gained = ( initial_base_received 
                    * bid_sellExchange 
                    * (1 - tx_fee_buyExchange) )
    
    if wd_fee_sellExchange:
        quote_left_over_after_second_withdrawal = ( quote_gained_after_withdrawal 
                                                   - wd_fee_sellExchange )
    grossProfit = quote_gained - initial_quote_paid
    percentGrossProfit = round(((grossProfit / initial_quote_paid) - 1),3)
    grossProfitEuro = convert_to_euro(grossProfit,quote)
    grossProfitBTC = convert_to_BTC(grossProfit,quote)
    
    if wd_fee_buyExchange and wd_fee_sellExchange:
        netProfit = quote_left_over_after_second_withdrawal - initial_quote_paid
        percentNetProfit = round(((netProfit / initial_quote_paid) - 1),3)
        netProfitEuro = convert_to_euro(netProfit,quote)
        netProfitBTC = convert_to_BTC(netProfit,quote)
    else:
        netProfit = np.nan
        percentNetProfit = np.nan
        netProfitEuro = np.nan
        netProfitBTC = np.nan
        
    maxInitialAmountEuro = convert_to_euro(initial_quote_paid,quote)
    maxInitialAmountBTC = convert_to_BTC(initial_quote_paid,quote)
    
    df_result = pd.DataFrame({
            'maxInitialAmountEuro':[maxInitialAmountEuro],
            'maxInitialAmountBTC':[maxInitialAmountBTC],
            'grossProfitEuro':[grossProfitEuro],
            'grossProfitBTC':[grossProfitBTC],
            'percentGrossProfit':[percentGrossProfit],
            'netProfitEuro':[netProfitEuro],
            'netProfitBTC':[netProfitBTC],
            'percentNetProfit':[percentNetProfit],
            'askPrice_buyExchange':[ask_buyExchange],
            'bidPrice_sellExchange':[bid_sellExchange],
            'maxVolume':[maxVolume],
            'initial_base_received':[initial_base_received],
            'initial_quote_received':[initial_quote_received],
			'timestamp':time.time()
            })
    
    return df_result


#------------------------------------------------------------------------------
    

def runProfitabilityCalculator(BuyExchange,SellExchange):
    result1 = profitabilityCalculator(BuyExchange,SellExchange)
    result2 = profitabilityCalculator(SellExchange,BuyExchange)
    if result1['grossProfitEuro'][0] > result2['grossProfitEuro'][0]:
        return result1
    else:
        return result2
    
    
#------------------------------------------------------------------------------


print("Loading the profitability calculator...")
load_euro_and_BTC_values()
print("Loading complete.")


#------------------------------------------------------------------------------