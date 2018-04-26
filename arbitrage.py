# -*- coding: utf-8 -*-
"""
Created on Thu Apr 26 13:13:05 2018

@author: Aaron
"""


import ccxt


#------------------------------------------------------------------------------

class BuyExchange:
    def __init__(self,exchangeDict,trial=True):
        """
        Instantiates class and instance attributes and loads the ccxt object's
        markets and API keys.
        """

        self.BASE_CURRENCY = exchangeDict['baseCurrency'] # "BUY" CURRENCY
        self.QUOTE_CURRENCY = exchangeDict['quoteCurrency']
        
        self.NAME = exchangeDict['exchangeName']
        self.DEPOSIT_ADDRESS = exchangeDict['depositAddress']# for BuyExchange this is the quote currency, ie BTC, for SellExchange this is base currency
        
        self.ccxtObject = getattr(ccxt,self.NAME)()
        self.ccxtObject.loadMarkets()
        self.ccxtObject.apikey = exchangeDict['publicKey']
        self.ccxtObject.secret = exchangeDict['privateKey']
        
        balances = self.ccxtObject.fetchBalance()
        self.availableBalanceBASE = balances['free'][self.BASE_CURRENCY]
        self.availableBalanceQUOTE = balances['free'][self.QUOTE_CURRENCY]
        
        self.exchangeType = 'BUY'
        self.tradingPaused = False
        self.trial = trial
        
        
    def getOrderbook(self):
        # FETCH ORDERBOOK
        
        # IF SELF.exchangeType == 'BUY':
        #   GET SELL ORDERS
        # ELSE:
        #   GET BID ORDERS  
        pass
    
    
    def executeTrade(self):
        # MAKE SURE IT KNOWS IF IT'S A BUY OR A SELL
        
        # CHECK TO ENSURE THE TRADE WAS SUCCESSFUL
        pass
    
    
    def waitforDeposit(self):
        pass
        
    
    def checkBalanceBASE(self):
        balanceBASE = self.ccxtObject.fetchBalance()['free'][self.BASE_CURRENCY]
        if balanceBASE != self.availableBalanceBASE:
            self.availableBalanceBASE = balanceBASE
            return balanceBASE
    
    
    def checkBalanceQUOTE(self):
        balanceQUOTE = self.ccxtObject.fetchBalance()['free'][self.QUOTE_CURRENCY]
        if balanceQUOTE != self.availableBalanceQUOTE:
            self.availableBalanceQUOTE = balanceQUOTE
            return balanceQUOTE
    
    
    # WITHDRAWAL FUNCTION GOES OUTSIDE CLASSES
    
        