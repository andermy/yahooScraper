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
    
    def get_symbols(self):
        tickers = self.stock_data.symbols.find()

        return tickers

    def update_options(self, symbol, data):
        if len(data) > 0:
            data.index = data.index.astype(str)
            self.stock_data.optionsdata.insert_one({'sym': symbol, 'options': data.to_dict()})
    
def main():  
    m = stockMongo()
    symbols = m.get_symbols()
    for sym in symbols:
        prices = iterateYahooOptions(sym['sym'], 500)
        m.update_options(sym['sym'], prices)
        print("Yes")

if __name__ == "__main__":  
    main()