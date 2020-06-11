import requests
from bs4 import BeautifulSoup
import datetime
import time
import pandas as pd
from pymongo import * 


def iterateYahooOptions(symbol, num):
    date = get_datestamp()
    options = []

    for day in range(0,num):
        print(day)
        date += datetime.timedelta(days=1)
        options.append(getYahooOptions(symbol, date))
    
    options = pd.concat(options)
    #options = options.set_index('date')
    return options

def getYahooOptions(symbol, options_day):

    datestamp = int(time.mktime(options_day.timetuple())) 
    today = datetime.datetime.now()

    data_url = "https://finance.yahoo.com/quote/"+ str(symbol) +"/options?date=" + str(datestamp)
    call_info = ['type','in-money', 'date','contract', 'strike-date', 'last_trade', 'strike', 'last', 'bid', 'ask', 'volume', 'iv']
    data_html = requests.get(data_url)
    content = BeautifulSoup(data_html.text, "html.parser")
    options_tables = []
    tables = content.find_all("table")
    contracts_data = []
    if tables != []:
        try:
            print(datestamp)
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
                        contracts_data.append(["Call", contract[0], today, contract_data[0], options_day, datetime.datetime.strptime(contract_data[1][:10],'%Y-%m-%d'), contract_data[2], contract_data[3], contract_data[4], contract_data[5], contract_data[8], contract_data[10]])
                    else:
                        contracts_data.append(["Put", contract[0], today, contract_data[0], options_day, datetime.datetime.strptime(contract_data[1][:10],'%Y-%m-%d'), contract_data[2], contract_data[3], contract_data[4], contract_data[5], contract_data[8], contract_data[10]])
        except:
            ValueError
            print("Table is not empty, but can't read")

    return pd.DataFrame(contracts_data, columns=call_info)
    
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
    
    def get_symbols(self):
        tickers = self.stock_data.symbols.find()

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

def add_companies():
    symbols = requests.get('https://finnhub.io/api/v1/stock/symbol?exchange=US&token=bqmgk37rh5rc5ul5lcs0')
    stocks = []
    i = 0
    for sym in symbols.json():
        i = i +1
        print(i)
        titles = ['symbol', 'ic-grossporfit', 'ic-netincomeloss', 'ic-operatingexpences', 'cf-netincomeloss', 'cf-interestpaidnet', 'bs-assets', 'bs-liabilities', 'bs-inventorynet', 'filesdate']
        try:
            r = requests.get('https://finnhub.io/api/v1/stock/financials-reported?symbol=' + str(sym['symbol']) + '&token=bqmgk37rh5rc5ul5lcs0')
            data = r.json()['data'][0]['report']
            stocks.append([sym['symbol'], data['ic']['GrossProfit'], data['ic']['NetIncomeLoss'],data['ic']['OperatingExpenses'],data['cf']['NetIncomeLoss'], data['cf']['InterestPaidNet'], data['bs']['Assets'], data['bs']['Liabilities'], data['bs']['InventoryNet'], r.json()['data']['filedDate']])
        except:
            ValueError
    return pd.DataFrame(stockMongo, columns=titles)

def main():  
    m = stockMongo()
    symbols = m.get_symbols()
    for sym in symbols:
        prices = iterateYahooOptions(sym['sym'], 500)
        m.update_options(sym['sym'], prices)
        print("Yes")

if __name__ == "__main__":  
    main()