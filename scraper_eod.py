import requests
from bs4 import BeautifulSoup
import datetime
import time
import pandas as pd
from pymongo import * 
import json
from collections import OrderedDict
from yahoo_fin import options
import asyncio
import os
from dotenv import load_dotenv
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
    
    def collect_strike_date_options(self, ticker, options, save_db=False):
        now = datetime.datetime.now()
        now = datetime.datetime.strptime(now.strftime("%m/%d/%Y"),"%m/%d/%Y")
        if 'CALL' in options['options'].keys():
            calls = pd.json_normalize(options['options']['CALL'])
            calls['date'] = now
            calls['iv'] = options['impliedVolatility']
            if save_db:
                    self.update_options(ticker, calls, now, 'call')
        if 'PUT' in options['options'].keys():
            puts = pd.json_normalize(options['options']['PUT'])
            puts['date'] = now
            puts['iv'] = options['impliedVolatility']
            if save_db:
                self.update_options(ticker, puts, now, 'put')

    def collect_eod_options(self, ticker, save_db=False):
        url = 'https://eodhistoricaldata.com/api/options/' + str(ticker) + '.US?api_token=62285d413c8a65.19918555'
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            [self.collect_strike_date_options(ticker=ticker, options=expiration_date, save_db=save_db) for expiration_date in data['data']]
        else:
            print('Something went wrong')

    def collect_eod_options_tickerlist(self, ticker_list):
        [self.collect_eod_options(ticker=ticker, save_db=True) for ticker in ticker_list]

    def get_options(self, symbol):
        symbols = self.stock_data.options_data2.find({'sym': symbol})
        cleanSymbols = []
        for s in symbols:
            df = pd.DataFrame.from_records(s['options'])
            cleanSymbols.append(df)
        op = pd.concat(cleanSymbols)
        op['Strike'] = pd.to_numeric(op['Strike'],errors='coerce')
        op['Last Price'] = pd.to_numeric(op['Last Price'],errors='coerce')
        op['Bid'] = pd.to_numeric(op['Bid'],errors='coerce')
        op['Ask'] = pd.to_numeric(op['Ask'],errors='coerce')
        op['Volume'] = pd.to_numeric(op['Volume'],errors='coerce')
        op['Open Interest'] = pd.to_numeric(op['Open Interest'],errors='coerce')
        #op['date'] = pd.to_datetime(op['date'], "%Y-%m-%d %H:%M:%S")
        #op['strike-date'] = pd.to_datetime(op['strike-date'], "%Y-%m-%d %H:%M:%S")
        #op['Last Trade Date'] = pd.to_datetime(op['Last Trade Date'], "%Y-%m-%d")
        op = op.set_index('date')
        return op


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