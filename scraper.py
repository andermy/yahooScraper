import requests
from bs4 import BeautifulSoup
import datetime
import time
import pandas as pd
from pymongo import * 
import json
from collections import OrderedDict


def get_dates():

    dates = [
        1604620800,
        1605225600,
        1605830400,
        1606435200,
        1607040000,
        1607644800,
        1608249600,
        1608249600,
        1610668800,
        1613692800,
        1616112000,
        1618531200,
        1623974400,
        1631836800,
        1642723200,
        1655424000,
        1663286400,
        1674172800,
    ]

    return dates

def getYahooOptions(symbol, options_day):

    #datestamp = int(time.mktime(options_day.timetuple())) 
    today = datetime.datetime.now()

    data_url = "https://finance.yahoo.com/quote/"+ str(symbol) +"/options?date=" + str(options_day)
    call_info = ['type','in-money', 'date','contract', 'strike-date', 'last_trade', 'strike', 'last', 'bid', 'ask', 'volume', 'iv']
    data_html = requests.get(data_url)
    content = BeautifulSoup(data_html.text, "html.parser")
    options_tables = []
    tables = content.find_all("table")
    contracts_data = []
    if tables != []:
        try:
            for i in range(0, len(content.find_all("table"))):
                options_tables.append(tables[i])

            for i in range(0,2):
                contracts = options_tables[i].find_all("tr")[1:] # first row is header
                contracts_new = []
                for option in contracts:
                    if "in-the-money" in str(option):
                        contracts_new.append(["in-the-money", option])
                    else:
                        contracts_new.append(["out-of-money", option])
            
                for contract in contracts_new:
                    contract_data = []
                    for td in BeautifulSoup(str(contract[1]), "html.parser").find_all("td"):
                        contract_data.append(td.text)
                    if i == 0:
                        #op_date = datetime.fromtimestamp(options_day)
                        contracts_data.append(["Call", contract[0], today, contract_data[0], options_day, datetime.datetime.strptime(contract_data[1][:10],'%Y-%m-%d'), contract_data[2], contract_data[3], contract_data[4], contract_data[5], contract_data[8], contract_data[10]])
                    else:
                        contracts_data.append(["Put", contract[0], today, contract_data[0], options_day, datetime.datetime.strptime(contract_data[1][:10],'%Y-%m-%d'), contract_data[2], contract_data[3], contract_data[4], contract_data[5], contract_data[8], contract_data[10]])
        except:
            ValueError
            #print("Table is not empty, but can't read")
            #print(symbol)

    return pd.DataFrame(contracts_data, columns=call_info)

def get_yahoo_stocks(symbol):
    r = requests.get("https://finance.yahoo.com/quote/" + str(symbol) + "?p="+str(symbol)).text
    soup = BeautifulSoup(r,'html.parser')
    alldata = soup.find_all('tbody')
    try:
        table1 = alldata[0].find_all('tr')
    except:
        table1=None
    try:
        table2 = alldata[1].find_all('tr')
    except:
        table2 = None
    l={}

    for i in range(0,len(table1)):
        try:
            table1_td = table1[i].find_all('td')
        except:
            table1_td = None
        if table1_td[0].text == 'Avg. Volume':     
            l['Avg_volume'] = table1_td[1].text
        else:
            l[table1_td[0].text] = table1_td[1].text
            
    l['date'] = datetime.datetime.now()

    info = ['Previous Close', 'Volume', 'Date']
    b = []
    b.append([float(l['Previous Close']), l['Volume'], l['date']])
    c = pd.DataFrame(b, columns=info)
    
    return c
        

def get_datestamp():  

    today = int(time.time())  
    # print(today)  
    date = datetime.datetime.fromtimestamp(today)  
    yy = date.year  
    mm = date.month  
    dd = date.day

    # must use 12:30 for Unix time instead of 4:30 NY time 
    next_close = datetime.datetime(yy, mm, dd, 0, 0)

    return next_close

def iron_condor_price(x):
    s = -x['priceCHi']+x['priceCLo']+x['pricePHi']-x['pricePLo']
    
    return s/(x['strikePHi']-x['strikePLo'])

def iron_condor_value(x):
    s = 0
    if x['c'] >= x['strikeCLo']:
        s = s - x['c'] + x['strikeCLo']
    if x['c'] >= x['strikeCHi']:
        s = s + x['c'] - x['strikeCHi']
    if x['c'] <= x['strikePHi']:
        s = s - x['c'] + x['strikePHi']
    if x['c'] <= x['strikePLo']:
        s = s + x['c'] - x['strikePLo']
    #/(x['strikeP360']-x['strikeP350'])
    return s

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

    def update_options(self, symbol, data):
        if len(data) > 0:
            data.index = data.index.astype(str)
            self.stock_data.options_data.insert_one({'sym': symbol, 'options': data.to_dict()})
    
    def update_stocks(self, symbol, data):
        if len(data) > 0:
            data.index = data.index.astype(str)
            self.stock_data.stock_price.insert_one({'sym': symbol, 'date': datetime.datetime.now() ,'stockdata': data.to_dict()})
    
    def update_edited_options(self, symbol, dataW):
        if len(data) > 0:
            data.index = data.index.astype(str)
            self.stock_data.options_data.insert_one({'sym': symbol, 'options': data.to_dict()})

    def get_options(self, symbol):
        symbols = self.stock_data.options_data.find({'sym': symbol})
        cleanSymbols = []
        for s in symbols:
            df = pd.DataFrame.from_records(s['options'])
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
        
        tickerTimeline = self.get_stock_data({'sym':symbol})
        if len(tickerTimeline) > 0:
            newestDate = max(tickerTimeline['date'])
            print(ticker['sym'])
            print(newestDate)
            self.fetchInterval_stock_data(datetime.datetime.strptime(newestDate, "%Y-%m-%d"), 
                                datetime.datetime.now(),
                                symbol=ticker["sym"])
        else:
            self.fetchInterval_stock_data(datetime.datetime(2020, 1, 1),
                                datetime.datetime.now(),
                                symbol=ticker["sym"])
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

def main():  
    m = stockMongo()
    symbols = m.get_symbols()
    tickers = []
    for sym in symbols:
        tickers.append(sym['sym'])
    for tick in tickers:
        prices = []
        try:
            dates = get_dates()
            for day in dates:
                try:
                    prices = getYahooOptions(tick, day) 
                    prices['strike-date'] = pd.to_datetime(prices['strike-date'], unit='s')
                    m = stockMongo()
                    m.update_options(tick, prices)
                except:
                    print("Not possible to store:")
                    print(tick)
                if len(prices)==0:
                    print("No prices:")
                    print(tick)
                    #m = stockMongo()
                    #m.remove(tick)
        except:
            print("No dates")
        
    for tick in tickers:
        try:
            prices = get_yahoo_stocks(tick)
            m = stockMongo()
            m.update_stocks(tick, prices)
        except:
            print("Not possible to store:")
            print(tick)
        if len(prices)==0:
            print("No prices:")
            print(tick)
                   
if __name__ == "__main__":  
    main()