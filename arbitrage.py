# -*- coding: utf-8 -*-
"""
Created on Thu Apr 26 13:13:05 2018

@author: Aaron
"""


import time
import threading
import sched
import pandas as pd
import ccxt
import profitability_calculator as pc



#========================================================================================================


class Exchange:
    
    BASE_CURRENCY = coins['baseCurrency'] # "BUY" CURRENCY
    QUOTE_CURRENCY = coins['quoteCurrency']
    SYMBOL = BASE_CURRENCY + '/' + QUOTE_CURRENCY
    
    
    def __init__(self,exchangeDict,exchangeType,trial=True):

        self.NAME = exchangeDict['exchangeName']
        self.WITHDRAWAL_ADDRESS = exchangeDict['withdrawalAddress'] 
        # For BuyExchange this is the quote currency's address on the other exchange, e.g. BTC 
        # For SellExchange this is the base currency's address on the other exchange, e.g. LINK
        
        self.exchangeType = exchangeType
        self.tradingPaused = False
        self.trial = trial
        
        self.ccxtObject = getattr(ccxt,self.NAME)()
        self.ccxtObject.loadMarkets()
        self.ccxtObject.apiKey = exchangeDict['publicKey']
        self.ccxtObject.secret = exchangeDict['privateKey']
        
        if self.trial == False:
            balances = self.ccxtObject.fetchBalance()
            self.availableBalanceBASE = balances['free'][Exchange.BASE_CURRENCY]
            self.availableBalanceQUOTE = balances['free'][Exchange.QUOTE_CURRENCY]
        else:
            self.availableBalanceBASE = 10 # 10 BASE coins
            self.availableBalanceQUOTE = 0.25 # 0.25 QUOTE coins, e.g. BTC
            
        self.orders = self.getOrderbook()
        self.profitStats = {}
        
        
    #--------------------------------


    def checkBalanceBASE(self):
        balanceBASE = self.ccxtObject.fetchBalance()['free'][Exchange.BASE_CURRENCY]
        if balanceBASE != self.availableBalanceBASE:
            self.availableBalanceBASE = balanceBASE
            return balanceBASE
    
    
    def checkBalanceQUOTE(self):
        balanceQUOTE = self.ccxtObject.fetchBalance()['free'][Exchange.QUOTE_CURRENCY]
        if balanceQUOTE != self.availableBalanceQUOTE:
            self.availableBalanceQUOTE = balanceQUOTE
            return balanceQUOTE    
    
    
    #--------------------------------
    
    
    def fetch_orders_safely(self,i):
        if i < 5:
            try:
                orderbook = self.ccxtObject.fetch_l2_order_book(Exchange.SYMBOL,5)
            except:
                print("Note: There was an error fetching the "
                      + Exchange.SYMBOL + " orderbook for " + str(self.NAME) 
                      + 'at ' + time.strftime("%d-%m-%Y %H:%M:%S"))
                time.sleep(5)
                orderbook = self.fetch_orders_safely(i+1)
        else:
            orderbook = {'asks':False}
        return orderbook
    
    
    def getOrderbook(self):
        orderbook = self.fetch_orders_safely(0)
        if not orderbook['asks']:
            return {}
            # THIS CONDITION IS IF THE ORDERBOOK DATA IS BAD!
            
        precision = self.ccxtObject.markets[Exchange.SYMBOL]['precision']
        if precision == {}: # CCXT HAS NOT FILLED IN THE PRECISION FOR ALL COINS CORRECTLY
            precision = {'amount': 8, 'price': 8}
        elif type(precision['amount']) != int or type(precision['price']) != int:
            precision = {'amount': 8, 'price': 8}
        timestamp = int(round(time.time() * 1000))
        
        volume = 0
        weighted_price = 0
        if self.exchangeType == 'BUY':
            orders = orderbook['asks'][:3]
        else:
            orders = orderbook['bids'][:3]
        for i in orders:
            volume += i[1]
            weighted_price += i[0]*i[1]
        weighted_price = weighted_price / volume
        volume = 0
        for i in orders:
            if ( (self.exchangeType == 'BUY' and i[0] >= weighted_price) or 
                 (self.exchangeType == 'SELL' and i[0] <= weighted_price) ):
                    volume += i[1]
    
        orderbook_dict = {
                'timestamp':timestamp,
                'price':round(weighted_price,precision['price']),
                'volume':round(volume,precision['amount'])
                }
        self.orders = orderbook_dict
        return orderbook_dict
    
    
    def getOrderbookContinuously(self):
        s = sched.scheduler()
        s.enter((self.ccxtObject.rateLimit*1.5),0,self.getOrderbook)
        s.run()
    
    
    #--------------------------------
    
    
    def executeTrade(self):
        volume = self.profitStats['maxVolume'][0]
        if self.exchangeType == 'BUY':
            price = self.profitStats['askPrice_buyExchange'][0]
            self.ccxtObject.createLimitBuyOrder(Exchange.SYMBOL,volume,price)
        elif self.exchangeType == 'SELL':
            price = self.profitStats['bidPrice_sellExchange'][0]
            self.ccxtObject.createLimitSellOrder(Exchange.SYMBOL,volume,price)


    def checkTrade(self):
        '''
        CHECK TO ENSURE THE TRADE WAS SUCCESSFUL
        '''
        balanceBeforeBASE = self.availableBalanceBASE
        balanceBeforeQUOTE = self.availableBalanceQUOTE   
        
        while True:
            if self.exchangeType == 'BUY':
                if self.checkBalanceBASE() >= (balanceBeforeBASE + self.profitStats['initial_base_received'][0]):
                    # THIS WILL HAVE TO BE CHANGED IF WEIGHTED VOLUME ORDERS DON'T WORK

                    # The trade has been completed successfully. Proceed.
                    break
            if self.exchangeType == 'SELL':
                if self.checkBalanceQUOTE() >= (balanceBeforeQUOTE + self.profitStats['initial_quote_received'][0]):
                    # The trade has been completed successfully. Proceed.
                    break
            time.sleep(1)
    
    
    def trade(self):
        self.checkBalanceBASE()
        self.checkBalanceQUOTE()
        self.executeTrade()
        self.checkTrade()
        
        
    #--------------------------------
    
    
    def waitForDeposit(self):
        balanceBeforeBASE = self.availableBalanceBASE
        balanceBeforeQUOTE = self.availableBalanceQUOTE   
        
        while True:
            if self.exchangeType == 'BUY':
                if self.checkBalanceQUOTE() >= balanceBeforeQUOTE:
                    # The deposit has been completed successfully. Proceed.
                    break
            if self.exchangeType == 'SELL':
                if self.checkBalanceBASE() >= balanceBeforeBASE:
                    # The deposit has been completed successfully. Proceed.
                    break
            time.sleep(1)
        balanceDifferences = {
                        'balanceBeforeBASE':[balanceBeforeBASE],
                        'balanceBeforeQUOTE':[balanceBeforeQUOTE],
                        'balanceAfterBASE':[self.checkBalanceBASE()],
                        'balanceAfterQUOTE':[self.checkBalanceQUOTE()],
                        'balanceDifferenceBASE':[(self.availableBalanceBASE - balanceBeforeBASE)],
                        'balanceDifferenceQUOTE':[(self.availableBalanceQUOTE - balanceBeforeQUOTE)],
                        'time':[time.strftime("%d-%m-%Y %H:%M:%S")]
                        }
        return balanceDifferences
    
    
    def withdraw(self):
        if self.exchangeType == 'BUY':
            currency = Exchange.BASE_CURRENCY
            amount = self.availableBalanceBASE
        else:
            currency = Exchange.QUOTE_CURRENCY
            amount = self.availableBalanceQUOTE
            
        self.ccxtObject.withdraw(currency,amount,self.WITHDRAWAL_ADDRESS)
        
    
    def withdrawAndConfirm(self,BothExchangesInstance):
        self.checkBalanceBASE()
        self.checkBalanceQUOTE()
        self.withdraw()
        balanceDifferences = self.waitForDeposit()
        
        '''
        The following code outputs the net profits and balances on the 
        exchange, either the buyExchange or the sellExchange.
        '''
        exchange_output_text = (
                        'Net profits earned for ' + self.NAME + ': \n'
                        + Exchange.BASE_CURRENCY + 'gained/lost = ' + balanceDifferences['balanceDifferenceBASE'][0] + '\n'
                        + Exchange.QUOTE_CURRENCY + 'gained/lost = ' + balanceDifferences['balanceDifferenceQUOTE'][0] + '\n'
                        + 'Time: ' + balanceDifferences['time'][0] + '\n\n\n'
                        )
        with threading.Lock():
            print(exchange_output_text)
            with open('output_'+self.NAME+'.txt','a') as t:
                t.write(exchange_output_text)
            with open('balances_'+self.NAME+'.csv','a') as c:
                pd.DataFrame(balanceDifferences).to_csv(c,header=False)
        
        if self.exchangeType == 'BUY':
            BothExchangesInstance.balanceDifferenceBASE_BUY_EXCHANGE = balanceDifferences['balanceDifferenceBASE'][0]
            BothExchangesInstance.balanceDifferenceQUOTE_BUY_EXCHANGE = balanceDifferences['balanceAfterQUOTE'][0]
        else:
            BothExchangesInstance.balanceDifferenceBASE_SELL_EXCHANGE = balanceDifferences['balanceDifferenceBASE'][0]
            BothExchangesInstance.balanceDifferenceQUOTE_SELL_EXCHANGE = balanceDifferences['balanceAfterQUOTE'][0]
                
    #--------------------------------

        
        
#========================================================================================================
        

        
class BothExchanges:

    def __init__(self):
        self.balanceDifferenceBASE_BUY_EXCHANGE = 0
        self.balanceDifferenceBASE_SELL_EXCHANGE = 0
        self.balanceDifferenceQUOTE_BUY_EXCHANGE = 0
        self.balanceDifferenceQUOTE_SELL_EXCHANGE = 0
        self.profitGainedBASE = 0
        self.profitGainedQUOTE = 0
        
    def getProfitBASE(self):
        self.profitGainedBASE = (self.balanceDifferenceBASE_BUY_EXCHANGE 
                                + self.balanceDifferenceBASE_SELL_EXCHANGE)
        return self.profitGainedBASE
    
    def getProfitQUOTE(self):
        self.profitGainedQUOTE = (self.balanceDifferenceQUOTE_BUY_EXCHANGE 
                                + self.balanceDifferenceQUOTE_SELL_EXCHANGE)
        return self.profitGainedQUOTE    
        
        
        
    
#========================================================================================================    
        
        
def buyAndSell(BuyExchange,SellExchange):
    buyThread = threading.Thread(target=BuyExchange.trade(),daemon=True)
    sellThread = threading.Thread(target=SellExchange.trade(),daemon=True)    
    
    buyThread.start()
    sellThread.start()
    buyThread.join()
    sellThread.join()


    
def moveFunds(BuyExchange,SellExchange,BothExchanges):
    buyExchangeThread = threading.Thread(target=BuyExchange.withdrawAndConfirm,argument=(BothExchanges,),daemon=True)
    sellExchangeThread = threading.Thread(target=SellExchange.withdrawAndConfirm,argument=(BothExchanges,),daemon=True)
    
    buyExchangeThread.start()
    sellExchangeThread.start()
    buyExchangeThread.join()
    sellExchangeThread.join()
     
    '''
    The following lines of code outputs the NET PROFIT MADE FROM BOTH EXCHANGES
    '''
    profits = {
            'netProfitBASE':[BothExchanges.getProfitBASE()],
            'netProfitQUOTE':[BothExchanges.getProfitQUOTE()],
            'time':[time.strftime("%d-%m-%Y %H:%M:%S")]
            }
    output_text_both = (
            'Net profits earned between both exchanges: \n'
            + BuyExchange.BASE_CURRENCY + 'gained/lost = ' + profits['netProfitBASE'][0] + '\n'
            + BuyExchange.QUOTE_CURRENCY + 'gained/lost = ' + profits['netProfitQUOTE'][0] + '\n'
            + 'Time: ' + profits['time'][0] + '\n\n\n'
            )
    with threading.Lock():
        print(output_text_both)
        with open('output_both.txt','a') as t:
            t.write(output_text_both)
        with open('profits.csv','a') as c:
            pd.DataFrame(profits).to_csv(c,header=False)        
    
    
    
#========================================================================================================


  
def arbitrage(BuyExchange,SellExchange,BothExchanges,minProfitEuro):

    BuyExchangeOrderbookThread = threading.Thread(target=BuyExchange.getOrderbooksContinuously,daemon=True)
    SellExchangeOrderbookThread = threading.Thread(target=SellExchange.getOrderbooksContinuously,daemon=True)
    BuyExchangeOrderbookThread.start()
    SellExchangeOrderbookThread.start()
    time.sleep(3)
    
    while True:
        while BuyExchange.tradingPaused == False and SellExchange.tradingPaused == False: 
            profitCalculations = pc.profitabilityCalculator(BuyExchange,SellExchange)
            BuyExchange.profitStats = profitCalculations
            SellExchange.profitstats = profitCalculations
            
            if profitCalculations['netProfitEuro'][0] > minProfitEuro:
                BuyExchange.tradingPaused = True
                SellExchange.tradingPaused = True
                
                buyAndSell(BuyExchange,SellExchange)
                moveFunds(BuyExchange,SellExchange,BothExchanges)
                
                BuyExchange.tradingPaused = False
                SellExchange.tradingPaused = False
                
                with open('predicted_profits.csv','a') as c:
                    profitCalculations.to_csv(c,header=False)
            else:
                time.sleep(0.5)
        

def trial_arbitrage(BuyExchange,SellExchange,minProfitEuro):

    BuyExchangeOrderbookThread = threading.Thread(target=BuyExchange.getOrderbooksContinuously,daemon=True)
    SellExchangeOrderbookThread = threading.Thread(target=SellExchange.getOrderbooksContinuously,daemon=True)
    BuyExchangeOrderbookThread.start()
    SellExchangeOrderbookThread.start()
    time.sleep(3)

    while True:
        profitCalculations = pc.profitabilityCalculator(BuyExchange,SellExchange)        
        if profitCalculations['netProfitEuro'][0] > minProfitEuro:
            
            output_text = (
                            'Time:' + time.strftime("%d-%m-%Y %H:%M:%S") + '\n'
                            + 'Predicted net profit (€): ' + profitCalculations['netProfitEuro'][0] + '\n'
                            + 'Predicted net profit (BTC): ' + profitCalculations['netProfitBTC'][0] + '\n\n\n'
                            )
            
            with threading.Lock():
                print(output_text)
                with open('output_trial.txt','a') as t:
                    t.write(output_text)
                with open('predicted_profits_trial.csv','a') as c:
                    profitCalculations.to_csv(c,header=False)        
                
            time.sleep(5400)
        else:
            time.sleep(0.5)

            
            
#========================================================================================================

coins = {
    'baseCurrency' : '_________',             #FILL IN BASE CURRENCY
    'quoteCurrency' : '_________'             #FILL IN QUOTE CURRENCY
        }

exchanges = {
        'BUY':{
            'exchangeName' : '_________',     #FILL IN BUY_EXCHANGE NAME
            'publicKey' : '_________',        #FILL IN BUY_EXCHANGE PUBLIC API KEY
            'privateKey' : '_________',       #FILL IN BUY_EXCHANGE PRIVATE API KEY
            'withdrawalAddress' : '_________' #FILL IN THE *SELL_EXCHANGE* DEPOSIT ADDRESS FOR THE BASE CURRENCY
                },
        'SELL':{
            'exchangeName' : '_________',     #FILL IN SELL_EXCHANGE NAME
            'publicKey' : '_________',        #FILL IN SELL_EXCHANGE PUBLIC API KEY
            'privateKey' : '_________',       #FILL IN SELL_EXCHANGE PRIVATE API KEY
            'withdrawalAddress' : '_________' #FILL IN THE *BUY_EXCHANGE* DEPOSIT ADDRESS FOR THE BASE CURRENCY
                }
            }
            
minProfitEuro = 10
trial = True

            
if __name__ == '__main__':
    
    BuyExchange = Exchange(exchangeDict=exchanges['BUY'],exchangeType='BUY')
    SellExchange = Exchange(exchangeDict=exchanges['SELL'],exchangeType='SELL')
    BothExchanges = BothExchanges()
    
    if trial == True:
        trial_arbitrage(BuyExchange,SellExchange,minProfitEuro)
    else:
        arbitrage(BuyExchange,SellExchange,BothExchanges,minProfitEuro)

