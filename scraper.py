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
        #1592524800,
        #1593129600,
        #1593648000,
        #1594339200,
        #1594944000,
        #1595548800,
        1596153600,
        1596758400,
        1597363200,
        1597968000,
        1600387200,
        1598572800,
        1599177600,
        1600387200,
        1605830400,
        1602806400,
        1608249600,
        1610668800,
        1623974400,
        1631836800,
        1642723200,
        1655424000,
        1663286400
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

def get_headers():
    return {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-GB,en;q=0.9,en-US;q=0.8,ml;q=0.7",
            "cache-control": "max-age=0",
            "dnt": "1",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.122 Safari/537.36"}


def parse(ticker):
    url = "http://finance.yahoo.com/quote/%s?p=%s" % (ticker, ticker)
    response = requests.get(
        url, verify=False, headers=get_headers(), timeout=30)
    print("Parsing %s" % (url))
    parser = html.fromstring(response.text)
    summary_table = parser.xpath(
        '//div[contains(@data-test,"summary-table")]//tr')
    summary_data = OrderedDict()
    other_details_json_link = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{0}?formatted=true&lang=en-US&region=US&modules=summaryProfile%2CfinancialData%2CrecommendationTrend%2CupgradeDowngradeHistory%2Cearnings%2CdefaultKeyStatistics%2CcalendarEvents&corsDomain=finance.yahoo.com".format(
        ticker)
    summary_json_response = requests.get(other_details_json_link)
    try:
        json_loaded_summary = json.loads(summary_json_response.text)
        summary = json_loaded_summary["quoteSummary"]["result"][0]
        y_Target_Est = summary["financialData"]["targetMeanPrice"]['raw']
        earnings_list = summary["calendarEvents"]['earnings']
        eps = summary["defaultKeyStatistics"]["trailingEps"]['raw']
        datelist = []

        for i in earnings_list['earningsDate']:
            datelist.append(i['fmt'])
        earnings_date = ' to '.join(datelist)

        for table_data in summary_table:
            raw_table_key = table_data.xpath(
                './/td[1]//text()')
            raw_table_value = table_data.xpath(
                './/td[2]//text()')
            table_key = ''.join(raw_table_key).strip()
            table_value = ''.join(raw_table_value).strip()
            summary_data.update({table_key: table_value})
        summary_data.update({'1y Target Est': y_Target_Est, 'EPS (TTM)': eps,
                             'Earnings Date': earnings_date, 'ticker': ticker,
                             'url': url})
        return summary_data
    except ValueError:
        print("Failed to parse json response")
        return {"error": "Failed to parse json response"}
    except:
        return {"error": "Unhandled Error"}

def get_yahoo_financial(symbol):
    url = "https://finance.yahoo.com/quote/AAPL/financials?p=AAPL"
    r = requests.get(url)
    content = BeautifulSoup(r.text, "html.parser")
    tables = content.find_all("table")

    other_details_json_link = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{0}?formatted=true&lang=en-US®ion=US&modules=summaryProfile%2CfinancialData%2CrecommendationTrend%2CupgradeDowngradeHistory%2Cearnings%2CdefaultKeyStatistics%2CcalendarEvents&corsDomain=finance.yahoo.com".format(
        ticker)

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
        tickers = self.stock_data.symbols.find(no_cursor_timeout=True)

        return tickers

    def update_options(self, symbol, data):
        if len(data) > 0:
            data.index = data.index.astype(str)
            self.stock_data.optionsdata.insert_one({'sym': symbol, 'options': data.to_dict()})

    def get_options(self, symbol):
        symbols = self.stock_data.optionsdata.find({'sym': symbol})
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
    
    #
    # Updates the database fetching data for all symbols since last 
    # date in the data until today
    #
    def update_stockprices(self):
        tickers = self.stock_data.symbols.find()
        for ticker in tickers:
            tickerTimeline = self.get_stock_data(ticker['sym'])
            if len(tickerTimeline) > 0:
                newestDate = max(tickerTimeline.index)
                self.fetchInterval_stock_data(datetime.datetime.strptime(newestDate, "%Y-%m-%d %H:%M:%S"), 
                                    datetime.datetime.now(),
                                    symbol=ticker["sym"])
            else:
                self.fetchInterval_stock_data(datetime.datetime(2000, 1, 1),
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
            
            data = self.get_finnhub_prices(symbol['sym'], startDate, endDate)

            print("Adding '[" + str(startDate) +", " + str(endDate)  + "]' data for symbol '" 
                + symbol['sym'] + "' (" + str(len(data)) + " entries)")
            data.index = data.index.astype(str)

            if len(data) > 0:
                self.stock_data.pricedata.insert_one({'sym': symbol['sym'], 'timeline': data.to_dict()})
            
    #
    # Collects stock historic data from finnhub.io
    #
    def get_finnhub_prices(self, symbol, startDate, endDate):
        data = requests.get('https://finnhub.io/api/v1/stock/candle?symbol=' + str(symbol) + '&resolution=D&from='+str(int(startDate.timestamp()))+'&to='+str(int(endDate.timestamp()))+'&token=bqmgk37rh5rc5ul5lcs0')
        datap = pd.DataFrame(data.json())
        datap['t'] = pd.to_datetime(datap['t'], unit='s')
        datap = datap.set_index('t')
        datap = datap.drop(['s'], axis=1)
        return datap

    #
    # Get pricedata from mongoDB
    #
    def get_stock_data(self, symbol):
        symbols = self.stock_data.pricedata.find({'sym': symbol})
        cleanSymbols = []
        for s in symbols:
            df = pd.DataFrame.from_records(s['timeline'])
            cleanSymbols.append(df)
        return pd.concat(cleanSymbols)

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
        
        
if __name__ == "__main__":  
    main()