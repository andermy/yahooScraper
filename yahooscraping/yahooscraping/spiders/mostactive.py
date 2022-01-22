import scrapy
from ..items import Option
import datetime
from bs4 import BeautifulSoup

class MostactiveSpider(scrapy.Spider):
    name = 'mostactive'
    allowed_domains = ['https://finance.yahoo.com/quote/']

    def start_requests(self):
        today = datetime.datetime.now()
        symbol = "AAPL"
        options_day = '1643932800'
        data_url = "https://finance.yahoo.com/quote/"+ str(symbol) +"/options?date=" + str(options_day)
    
        urls = [data_url]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)


    def parse(self, response):
        print(response)
        options_day = '1643932800'
        today = datetime.datetime.now()
        content = BeautifulSoup(response.text, 'lxml')
        print("no")
        tables = content.find_all("table")
        options_tables = []
        tables = content.find_all("table")
        contracts_data = []
        print(tables)
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
                                option_type="Call"
                                contracts_data.append(["Call", contract[0], today, contract_data[0], options_day, datetime.datetime.strptime(contract_data[1][:10],'%Y-%m-%d'), contract_data[2], contract_data[3], contract_data[4], contract_data[5], contract_data[8], contract_data[10]])
                            else:
                                option_type="Put"
                                contracts_data.append(["Put", contract[0], today, contract_data[0], options_day, datetime.datetime.strptime(contract_data[1][:10],'%Y-%m-%d'), contract_data[2], contract_data[3], contract_data[4], contract_data[5], contract_data[8], contract_data[10]])
                            option = Option()
                            option['contract_name']= contract[0],
                            option['last_trade_date']= contract_data[0],
                            option['today']= today.strptime('%Y-%m-%d'),
                            option['strike_date']= datetime.datetime.strptime(contract_data[1][:10],'%Y-%m-%d'),
                            option['strike']= contract_data[2],
                            option['last_price']= contract_data[3],
                            option['bid']= contract_data[4],
                            option['ask']= contract_data[5],
                            option['volume']= contract_data[8],
                            option['implied_volatility']= contract_data[10],
                            option['option_type']= option_type
                            yield option
            except:
                ValueError
                #print("Table is not empty, but can't read")
                #print(symbol)

    def getYahooOptions(symbol, options_day):
        
        #datestamp = int(time.mktime(options_day.timetuple())) 
        call_info = ['type','in-money', 'date','contract', 'strike-date', 'last_trade', 'strike', 'last', 'bid', 'ask', 'volume', 'iv']
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