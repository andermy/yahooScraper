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

class stockMongo():

    mongoClient = None
    stock_data = None
  
    def __init__(self, user="test", password="test", database="stock_data"):
        userAndPass = ""
        if user and password:
            userAndPass = user + ":" + str(password) + "@"
        url = "mongodb+srv://"+ userAndPass + "nibanfinance-lgkjt.gcp.mongodb.net/test?retryWrites=true&w=majority"
        self.mongoClient = MongoClient(url)
        self.stock_data = self.mongoClient[database]
    
    #
    # Adds a symbol from the ddbb, including all timeline entries
    #
    def add (self, symbol):
        exists = self.stock_data.symbols.find ({'sym':symbol}).count()
        if not exists:
            self.stock_data.symbols.insert_one ({'sym':symbol});
            print("'" + symbol + "'" + " added to the database")
    
    #
    # Removes a symbol from the ddbb, including all timeline entries
    #
    def remove (self, value):
        exists = self.stock_data.symbols.find({'sym': value}).count();
        if not exists:
            print("Error: symbol'" + value + "' not in the database")
        else:
            self.stock_data.symbols.delete_many ({'sym':value});
            print("'" + value + "'" + " removed from the database")

    def get_symbols(self):
        tickers = self.stock_data.symbols.find()
        #tickers = self.stock_data.symbols.find(no_cursor_timeout=True)

        return tickers

    def update_options(self, symbol, data, date, otype):
        if len(data) > 0:
            data.index = data.index.astype(str)
            self.stock_data.options_data2.insert_one({'sym': symbol, 'date': date, 'type': otype, 'options': data.to_dict()})
    
    def update_stocks(self, symbol, data):
        if len(data) > 0:
            data.index = data.index.astype(str)
            self.stock_data.stock_price.insert_one({'sym': symbol, 'date': datetime.datetime.now() ,'stockdata': data.to_dict()})
    
    def update_edited_options(self, symbol, dataW):
        if len(data) > 0:
            data.index = data.index.astype(str)
            self.stock_data.options_data.insert_one({'sym': symbol, 'options': data.to_dict()})

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
    
    def get_stocks(self, symbol):
        symbols = self.stock_data.pricedata.find({'sym': symbol})
        cleanSymbols = []
        for s in symbols:
            print(s)
            df = pd.DataFrame.from_records(s['timeline'])
            cleanSymbols.append(df)
        op = pd.concat(cleanSymbols)
        op['strike'] = pd.to_numeric(op['strike'],errors='coerce')
        op['last'] = pd.to_numeric(op['last'],errors='coerce')
        op['bid'] = pd.to_numeric(op['bid'],errors='coerce')
        op['ask'] = pd.to_numeric(op['ask'],errors='coerce')
        op['volume'] = pd.to_numeric(op['volume'],errors='coerce')
        op['date'] = pd.to_datetime(op['date'], "%Y-%m-%d %H:%M:%S")
        op['strike-date'] = pd.to_datetime(op['strike-date'], "%Y-%m-%d %H:%M:%S")
        op['last_trade'] = pd.to_datetime(op['last_trade'], "%Y-%m-%d")
        op = op.set_index('date')
        return op
    
    #
    # Updates the database fetching data for all symbols since last 
    # date in the data until today
    #
    def update_stockprices(self, symbol):
        
        tickerTimeline = self.get_stock_data(symbol)
        if len(tickerTimeline) > 0:
            newestDate = max(tickerTimeline['date'])
            self.fetchInterval_stock_data(datetime.datetime.strptime(newestDate, "%Y-%m-%d"), 
                                datetime.datetime.now(),
                                symbol=symbol)
        else:
            self.fetchInterval_stock_data(datetime.datetime(2020, 1, 1),
                                datetime.datetime.now(),
                                symbol=symbol)
    #
    # Fetches symbol data for the interval between startDate and endDate
    # If the symbol is not None, all symbols found in the database are
    # updated.
    #
    def fetchInterval_stock_data(self, startDate, endDate, symbol=None):
        date = None
        #try:
        #    sdate = datetime.strptime(startDate, "%Y-%m-%d %H:%M:%S")
        #    edate = datetime.strptime(endDate, "%Y/%m/%d")
        #except ValueError:
        #    print ("Error: invalid provided date format (expected yyyy/mm/dd)")
        #    return
        if symbol == None:
            symbols = self.stock_data.symbols.find()
        else:
            symbols = self.stock_data.symbols.find ({'sym':symbol})
        for symbol in symbols:
            try:
                data = self.get_finnhub_prices(symbol['sym'], startDate, endDate)

                print("Adding '[" + str(startDate) +", " + str(endDate)  + "]' data for symbol '" 
                    + symbol['sym'] + "' (" + str(len(data)) + " entries)")
                data.index = data.index.astype(str)

                if len(data) > 0:
                    self.stock_data.pricedata.insert_one({'sym': symbol['sym'], 'timeline': data.to_dict()})
            except:
                import time
                time.sleep(60)
                print("Can't add '[" + str(startDate) +", " + str(endDate)  + "]' data for symbol '"
                    + symbol['sym'])
    #
    # Collects stock historic data from finnhub.io
    #
    def get_finnhub_prices(self, symbol, startDate, endDate):
        data = requests.get('https://finnhub.io/api/v1/stock/candle?symbol=' + str(symbol) + '&resolution=D&from='+str(int(startDate.timestamp()))+'&to='+str(int(endDate.timestamp()))+'&token=bqmgk37rh5rc5ul5lcs0')
        datap = pd.DataFrame(data.json())
        datap['t'] = pd.to_datetime(datap['t'], unit='s')
        datap['date'] = datap['t']
        #datap['t'] = datap['t'].dt.strftime('%Y-%m-%d')
        datap = datap.set_index('t')
        datap = datap.drop(['s'], axis=1)
        return datap

    #
    # Get pricedata from mongoDB
    #
    def get_stock_data(self, symbol):
        symbols = self.stock_data.pricedata.find({'sym': symbol})
        cleanSymbols = []
        if symbols.count() > 0:
            for s in symbols:
                df = pd.DataFrame.from_records(s['timeline'])
                cleanSymbols.append(df)
            return pd.concat(cleanSymbols)
        else:
            return []
async def collection_options(tick, day):
    try:
        prices = options.get_options_chain(tick, day)
        price_calls = pd.DataFrame.from_dict(prices['calls'])
        price_puts = pd.DataFrame.from_dict(prices['puts'])
        strike_date = datetime.datetime.strptime(day, '%B %d, %Y')
        price_calls['strike-date'] = strike_date
        price_puts['strike-date'] = strike_date
        now = datetime.datetime.now()
        now = datetime.datetime.strptime(now.strftime("%m/%d/%Y"),"%m/%d/%Y")
        price_puts['date'] = now
        price_calls['date'] = now
        price_calls['type'] = 'call'
        price_puts['type'] = 'put'
        m = stockMongo()
        m.update_options(tick, price_calls, now, 'call')
        m.update_options(tick, price_puts, now, 'put')
    except:
        pass

def main():  
    print("getting symbols")
    m = stockMongo()
    symbols = m.get_symbols()
    tickers = []
    for sym in symbols:
        tickers.append(sym['sym'])
    iterations = []
    print("adding iterations")
    for tick in tickers:
        dates = options.get_expiration_dates(tick)
        if len(dates) == 0:
            m = stockMongo()
            m.remove(tick)
        for day in dates:
            iterations.append(collection_options(tick, day))
    
    loop = asyncio.get_event_loop()
    print("running data collection")
    loop.run_until_complete(asyncio.gather(*iterations))
    loop.close()

def main2():
    m = stockMongo()
    prices = []
    try:
        dates = options.get_expiration_dates('AAPL')
        try:
            prices = options.get_options_chain('AAPL', dates[14])
            price_calls = pd.DataFrame.from_dict(prices['calls'])
            price_puts = pd.DataFrame.from_dict(prices['puts'])
            strike_date = datetime.datetime.strptime(dates[14], '%B %d, %Y')
            price_calls['strike-date'] = strike_date
            price_puts['strike-date'] = strike_date
            now = datetime.datetime.now()
            #now = datetime.datetime.strptime(now.strftime("%m/%d/%Y"),"%m/%d/%Y")
            price_puts['date'] = now
            price_calls['date'] = now
            price_calls['type'] = 'call'
            price_puts['type'] = 'put'
            m = stockMongo()
            m.update_options('AAPL', price_calls, now, 'call')
            m.update_options('AAPL', price_puts, now, 'put')
            print("Options updated and stored")
        except:
            print("no prices")
    except:
        print("No date")
if __name__ == "__main__": 
    main()