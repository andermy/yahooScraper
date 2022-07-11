from this import d
import requests
from bs4 import BeautifulSoup
import datetime
import time
import pandas as pd
import numpy as np
from pymongo import * 
import json
from collections import OrderedDict
from yahoo_fin import options
import asyncio
import os
from dotenv import load_dotenv
import operator
load_dotenv()

class StockMongo():

    mongoClient = None
    stock_data = None
  
    def __init__(self):
        userAndPass = ""
        user = os.getenv('MONGOUSER')
        password = os.getenv('PASSWORD')
        db = os.getenv('DATABASE')
        mongoUser = os.getenv('MONGOACCOUNT')
        if user and password:
            userAndPass = user + ":" + str(password) + "@"
        url = "mongodb+srv://"+ userAndPass + mongoUser + "/test?retryWrites=true&w=majority"
        self.mongoClient = MongoClient(url)
        self.stock_data = self.mongoClient[db]
        self.eod_token = os.getenv('EODTOKEN')
        
    #
    # Adds a symbol from the ddbb, including all timeline entries
    #
    def add (self, symbol):
        exists = self.stock_data.symbols2.find ({'sym':symbol}).count()
        if not exists:
            self.stock_data.symbols2.insert_one ({'sym':symbol});
            print("'" + symbol + "'" + " added to the database")
    
    #
    # Removes a symbol from the ddbb, including all timeline entries
    #
    def remove (self, value):
        exists = self.stock_data.symbols2.find({'sym': value}).count();
        if not exists:
            print("Error: symbol'" + value + "' not in the database")
        else:
            self.stock_data.symbols.delete_many ({'sym':value});
            print("'" + value + "'" + " removed from the database")

    def get_symbols(self):
        tickers = self.stock_data.symbols2.find()
        #tickers = self.stock_data.symbols.find(no_cursor_timeout=True)

        return tickers
    
    def update_options(self, symbol, data, date, otype):
        if len(data) > 0:
            data.index = data.index.astype(str)
            self.stock_data.options_data2.insert_one({'sym': symbol, 'date': date, 'type': otype, 'options': data.to_dict()})
    
    def add_analysis(self, data_dict):
        if isinstance(data_dict, dict):
            self.stock_data.options_analisys.insert_one(data_dict)
    
    def collect_strike_date_options(self, ticker, options, save_db=False, debug=True):
        now = datetime.datetime.now()
        now = datetime.datetime.strptime(now.strftime("%m/%d/%Y"),"%m/%d/%Y")
        debug_dict = {}
        debug_dict['calls'] = 0
        debug_dict['puts'] = 0
        if 'CALL' in options['options'].keys():
            calls = pd.json_normalize(options['options']['CALL'])
            calls['date'] = now
            calls['iv'] = options['impliedVolatility']
            if save_db:
                self.update_options(ticker, calls, now, 'call')
            if debug:
                calls = calls[calls['lastTradeDateTime']!='0000-00-00 00:00:00']
                calls['lastTradeDateTime'] = pd.to_datetime(calls['lastTradeDateTime'], format='%Y-%m-%d')
                calls = calls[calls['lastTradeDateTime'].dt.date==calls['date'].dt.date-datetime.timedelta(1)]
                debug_dict['calls'] = len(calls)
        if 'PUT' in options['options'].keys():
            puts = pd.json_normalize(options['options']['PUT'])
            puts['date'] = now
            puts['iv'] = options['impliedVolatility']
            if save_db:
                self.update_options(ticker, puts, now, 'put')
            if debug:
                puts = puts[puts['lastTradeDateTime']!='0000-00-00 00:00:00']
                puts['lastTradeDateTime'] = pd.to_datetime(puts['lastTradeDateTime'], format='%Y-%m-%d')
                puts = puts[puts['lastTradeDateTime'].dt.date==puts['date'].dt.date-datetime.timedelta(1)]
                debug_dict['puts'] = len(puts)
        return debug_dict

    def collect_eod_options(self, ticker, save_db=False):
        url = 'https://eodhistoricaldata.com/api/options/' + str(ticker) + '.US?api_token=62285d413c8a65.19918555'
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            d = [self.collect_strike_date_options(ticker=ticker, options=expiration_date, save_db=save_db, debug= operator.not_(save_db)) for expiration_date in data['data']]
            calls = [c['calls'] for c in d]
        else:
            print('Something went wrong')
            calls = [0]
        return {'ticker': ticker, 'mean_len': np.mean(calls)}
    
    def collect_test_tickers(self, ticker_list):
        result = [self.collect_eod_options(ticker=ticker, save_db=False) for ticker in ticker_list]
        return result

    def collect_eod_options_tickerlist(self, ticker_list):
        [self.collect_eod_options(ticker=ticker, save_db=True) for ticker in ticker_list]

    def get_options(self, symbol):
        symbols = self.stock_data.options_data2.find({'sym': symbol})
        cleanSymbols = [pd.DataFrame.from_records(s['options']) for s in symbols]
        #for s in symbols:
        #    df = pd.DataFrame.from_records(s['options'])
        #    cleanSymbols.append(df)
        op = pd.concat(cleanSymbols)
        op.expirationDate = pd.to_datetime(op.expirationDate, format='%Y-%m-%d')
        op = op[op['lastTradeDateTime']!='0000-00-00 00:00:00']
        op.lastTradeDateTime = pd.to_datetime(op.lastTradeDateTime, format='%Y-%m-%d').dt.date
        op.updatedAt = pd.to_datetime(op.updatedAt, format='%Y-%m-%d').dt.date
        op.date = op.date - datetime.timedelta(days=1)
        op = op.set_index('date')
        #op['date'] = op.index
        return op

    def get_analisys(self, ticker):
        return self.stock_data.options_analisys.find({'ticker': ticker})

def main():  
    print("getting symbols")
    m = StockMongo()
    symbols = m.get_symbols()
    tickers = []
    for sym in symbols:
        tickers.append(sym['sym'])
    print("running data collection")
    m.collect_eod_options_tickerlist(tickers)

if __name__ == "__main__": 
    main()