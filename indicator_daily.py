import pandas as pd
import numpy as np
import datetime
from datetime import date, timedelta
import matplotlib.pyplot as plt
import time
from yahoo_fin import options
from yahoo_fin.stock_info import *
from yahoo_fin.stock_info import get_data, get_splits
import scraper_eod as s
import itertools
from sklearn.linear_model import LinearRegression
#from itertools import accumulate, chain

class TickerAggregation():
    def __init__(self):
        self.mongodb = s.StockMongo()
        self.symbols = list(self.mongodb.get_symbols())
        self.formulas = list(self.mongodb.stock_data.options_analisys.find())
        self.tickers = list(set([sym['sym'] for sym in self.symbols]))
        self.reduced_formaulas = [self.get_formulae(ticker) for ticker in self.tickers]
        self.reduced_formaulas = [f for f in self.reduced_formaulas if f is not None]
        #self.reduced_formaulas = list(chain(*self.reduced_formaulas))
        self.options = [self.get_today_review(analisys) for analisys in self.reduced_formaulas]
        self.returns = [o.returns for o in self.options if o is not None]
        self.df = self.get_df()
        self.mongodb.sync_next_day_portfolio()
        self.run_trades()
        #self.sync_todays_portfolio()

    def get_formulae(self, ticker):
        x = [f for f in self.formulas if f['ticker']==ticker]
        if len(x) > 0:
            return x[len(x)-1]
        else:
            return None

    def get_today_review(self, analisys):
        try:
            return Options(analisys['ticker'], analisys)
            #return o.returns
            #return s[(s['rel_risk']>0)&(s['rel_risk']<3)&(s['r']>0)&(s['r']<2)].copy()
        except:
            print(analisys['ticker'])
            return None

    def get_df(self):
        now = datetime.datetime.now()
        now = datetime.datetime.strptime(now.strftime("%m/%d/%Y"),"%m/%d/%Y")
        df = pd.concat(self.returns)
        df['date'] = now
        df['value'] = df.low_put_value - df.high_put_value + df.low_call_value - df.high_put_value
        return df
        #c = b[(b['rel_risk']>0.25)&(b['p']>0.5)]
        #return c.sort_values(by=['r'])

    def run_trades(self):
        self.traded_tickers = []
        selected_trades = self.df[(self.df['value']>0)&(self.df['rel_risk']<1)&(self.df['rel_risk']>0.35)&(self.df['r']>0)]
        selected_trades = selected_trades.sort_values(by=['rel_risk', 'p', 'r'], ascending=False)
        for index, row in selected_trades.iterrows():
            if len(self.traded_tickers) < 3:
                self.traded_tickers.append(row['ticker'])
                self.trade(row)

    def trade(self, row):
        if row['ticker'] not in self.traded_tickers:
            self.mongodb.add_trade(row.to_dict())
            print(row['ticker'])

    def sync_todays_portfolio(self):
        portfolio = self.mongodb.get_portfolio(None)
        port = pd.DataFrame.from_records(portfolio)
        a = []
        for i, row in port.iterrows():
            a.append(self.sync_ticker_in_portfolio(row))
        return a

    def sync_ticker_in_portfolio(self, element):
        op = [o for o in self.options if o is not None]
        options = [o.options for o in op if o.ticker == element['ticker']]
        if len(options) > 0:
            op = options[0]
            call1 = op[(op['strike'] == element['lowStrikeCall'])&(op['expirationDate'] == element['strike_date'])&(op['type'] == 'CALL')][['date', 'lastPrice', 'expirationDate', 'strike', 'daysBeforeExpiration', 'iv']]
            call1.columns = ['date', 'callLow', 'expirationDate', 'strikeCallLow', 'daysBeforeExpiration', 'iv']
            call2 = op[(op['strike'] == element['highStrikeCall'])&(op['expirationDate'] == element['strike_date'])&(op['type'] == 'CALL')][['date', 'lastPrice', 'strike']]
            call2.columns = ['date', 'callHigh', 'strikeCallHigh']
            put1 = op[(op['strike'] == element['lowStrikePut'])&(op['expirationDate'] == element['strike_date'])&(op['type'] == 'CALL')][['date', 'lastPrice', 'strike']]
            put1.columns = ['date', 'putLow', 'strikePutLow']
            put2 = op[(op['strike'] == element['highStrikePut'])&(op['expirationDate'] == element['strike_date'])&(op['type'] == 'CALL')][['date', 'lastPrice', 'strike']]
            put2.columns = ['date', 'putHigh', 'strikePutHigh']

            condor = call1.merge(call2, on='date', how='inner')
            condor = condor.merge(put1, on='date', how='inner')
            condor = condor.merge(put2, on='date', how='inner')

            condor['condor'] = condor.callLow-condor.callHigh-condor.putHigh+condor.putLow
            data_dict = {'strike_date': element['strike_date'], 'p': element['p'], 'highStrikePut': element['highStrikePut'], 'lowStrikeCall': element['lowStrikeCall'], 'lowStrikePut': element['lowStrikePut'], 'highStrikeCall': element['highStrikeCall']}
            data_dict['high_put_value'] = condor['putHigh']
            data_dict['low_call_value'] = condor['callLow']
            data_dict['high_call_value'] = condor['callHigh']
            data_dict['low_put_value'] = condor['putLow']
            data_dict['value'] = condor['condor']
            data_dict['ticker'] = element['ticker']
            now = datetime.datetime.now()
            now = datetime.datetime.strptime(now.strftime("%m/%d/%Y"),"%m/%d/%Y")
            data_dict['date'] = now
            #self.mongodb.stock_data.portfolio_time_series.insert_one(data_dict)
            return data_dict


class Options():

    def __init__(self, ticker, formula):
        #self.mongodb = s.StockMongo()
        try:
            self.ticker = ticker
            self.formula = formula
            self.options = self.collect_eod_options(self.ticker)
            self.prepare_options()
            self.start_date = min(self.options.index)
            self.end_date = max(self.options.index)
            self.strike_dates = []
            self.strikeDates = []
            #self.formula = {}
        except:
            self.len_records = 0
        self.map_strike_dates()
        try:
            self.stock_data = StockData(ticker)
            self.vix = StockData("^VIX")
            self.merge_stock_data()
            self.merge_vix_data()
            self.count_records()
        except:
            self.len_records = 0
        #self.analyse_options()
        self.map_strike_date_objects()
        self.map_strike_dates_returns()
        
    def prepare_options(self):
        self.options = self.options[self.options['lastTradeDateTime']!='0000-00-00 00:00:00']
        self.options['lastTradeDateTime'] = pd.to_datetime(self.options['lastTradeDateTime'], format='%Y-%m-%d')
        self.options = self.options[self.options['volume']>10].copy()
        
    def map_strike_dates(self):
        self.options = self.options[(self.options['daysBeforeExpiration']<70)&(self.options['daysBeforeExpiration']>30)]
        self.strike_dates = self.options.pivot_table(columns="expirationDate", values="volume", aggfunc=np.count_nonzero).columns

    def set_strike_date(self, num=7):
        self.options = self.options[self.options['expirationDate']==self.strike_dates[num]]

    def merge_stock_data(self):
        self.options = self.options.merge(self.stock_data.stock_data[['close', 'volatility', 'date']], on='date')

    def merge_vix_data(self):
        self.vix.rename_vix()
        self.options = self.options.merge(self.vix.stock_data[['vix', 'date']], on='date')

    def map_strike_date_objects(self):
        self.strikeDates = self.strike_dates.map(lambda x: StrikeDateOptions(options=self.options, strike_date=x, formula=self.formula))

    def map_strike_dates_returns(self):
        self.returns = pd.DataFrame(list(itertools.chain(*[sDate.returns for sDate in self.strikeDates])))
        self.returns['ticker'] = self.ticker
    
    def count_records(self):
        self.len_records =  len(self.options)

    def collect_strike_date_options(self, options):
        now = datetime.datetime.now()
        now = datetime.datetime.strptime(now.strftime("%m/%d/%Y"),"%m/%d/%Y")
        if 'CALL' in options['options'].keys():
            calls = pd.json_normalize(options['options']['CALL'])
            calls['date'] = now
            calls['iv'] = options['impliedVolatility']
        if 'PUT' in options['options'].keys():
            puts = pd.json_normalize(options['options']['PUT'])
            puts['date'] = now
            puts['iv'] = options['impliedVolatility']
        o = pd.concat([calls, puts])
        return o

    def collect_eod_options(self, ticker):
        url = 'https://eodhistoricaldata.com/api/options/' + str(ticker) + '.US?api_token=62285d413c8a65.19918555'
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            d = [self.collect_strike_date_options(options=expiration_date) for expiration_date in data['data']]
            options = pd.concat(d)
            options.expirationDate = pd.to_datetime(options.expirationDate, format='%Y-%m-%d')
            options = options[options['lastTradeDateTime']!='0000-00-00 00:00:00']
            options.lastTradeDateTime = pd.to_datetime(options.lastTradeDateTime, format='%Y-%m-%d').dt.date
            options.updatedAt = pd.to_datetime(options.updatedAt, format='%Y-%m-%d').dt.date
            options.date = options.date - datetime.timedelta(days=1)
            options = options.set_index('date')
        else:
            print('Something went wrong with ' + ticker)
            options = None
        return options

    #def analyse_options(self):
    #    formula = self.mongodb.get_analisys(self.ticker)
    #    if formula.count() > 0:
    #        self.formula = formula[formula.count()-1]


class StrikeDateOptions():

    def __init__(self, options, strike_date, formula):
        self.options = options
        self.mapped_options = None
        self.strike_date = strike_date
        self.condors = []
        self.formula = formula
        self.map_strike_date_options()
        self.map_implied_volatility()
        self.map_volatility()
        self.map_vol_range_returns()

    def map_implied_volatility(self):
        date_list = self.mapped_options.pivot_table(columns="date", values="close", aggfunc=np.count_nonzero).columns
        self.ImpliedVolatility = [ImpliedVolatility(options=self.mapped_options, date=this_date) for this_date in date_list]
        self.iv = pd.DataFrame([{'date': i.date, 'iv2': i.iv} for i in self.ImpliedVolatility])
        self.mapped_options = self.mapped_options.merge(self.iv, left_on='date', right_on='date', how='left')

    def map_strike_date_options(self):
        self.mapped_options = self.options[self.options['expirationDate']==self.strike_date].copy()
        self.start_date = min(self.mapped_options.date)
        self.end_date = max(self.mapped_options.date)
        
    def map_condor(self):
        date_list = pd.date_range(start=self.start_date, end=self.end_date-datetime.timedelta(1))
        self.condors = date_list.map(lambda x: Condor(options=self.mapped_options, limit=0, start_date=x))

    def map_volatility(self):
        date_list = pd.date_range(start=self.start_date, end=self.end_date-datetime.timedelta(1))
        self.volRange = VolatilityRange(options=self.mapped_options, strike_date=self.strike_date, formula=self.formula)
        
    def map_returns(self):
        self.returns = [condor.mean_return for condor in self.condors]

    def map_risk_returns(self):
        self.returns = [condor.get_risk_and_returns(self.strike_date) for condor in self.condors]

    def map_vol_range_returns(self):
        self.returns = self.volRange.returns
    
class VolatilityRange():

    def __init__(self, options, strike_date, formula):
        self.strike_date = strike_date
        self.options = options
        self.formula = formula
        self.map_condor()
        self.map_risk_returns()
    
    def map_condor(self):
        vols = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]
        self.condors = [Condor(options=self.options, vol_factor=vol, formula=self.formula) for vol in vols]
        #self.condors = vols.map(lambda x: Condor(options=self.mapped_options, vol_factor=x, start_date=self.start_date))
        
    def map_risk_returns(self):
        self.returns = [condor.calculate_expected_return(self.strike_date) for condor in self.condors]


class Condor():

    def __init__(self, options, vol_factor, formula):
        self.call_strike_low = None
        self.call_strike_high = None
        self.put_strike_low = None
        self.put_strike_high = None
        self.formula = formula
        self.options = options
        self.close = self.options.close.iloc[0]
        self.volatility = self.options.iv.iloc[0]/100
        self.iv = self.options.iv.iloc[0]
        self.iv2 = self.options.iv2.iloc[0]
        self.vix = self.options.vix.iloc[0]
        self.vol_factor = vol_factor
        self.condor_options = None
        self.mean_return = None
        self.is_valid = False
        self.is_80_percente_won = False
        self.is_20_percent_lost = False
        self.risk_rel = None
        self.days_to_strike = None
        self.filter_strike_options()
        self.balance_condor()
        if self.is_valid:
            self.set_condor()
        
    def set_condor(self):

        call1 = self.options[(self.options['strike']==self.call_strike_low)&(self.options['type']=='CALL')][['date', 'lastPrice', 'expirationDate', 'strike', 'close', 'volatility','daysBeforeExpiration', 'iv']]
        call1.columns = ['date', 'callLow', 'expirationDate', 'strikeCallLow', 'close', 'volatility','daysBeforeExpiration', 'iv']
        call2 = self.options[(self.options['strike']==self.call_strike_high)&(self.options['type']=='CALL')][['date', 'lastPrice', 'strike']]
        call2.columns = ['date', 'callHigh', 'strikeCallHigh']
        put1 = self.options[(self.options['strike']==self.put_strike_high)&(self.options['type']=='PUT')][['date', 'lastPrice', 'strike']]
        put1.columns = ['date', 'putLow', 'strikePutLow']
        put2 = self.options[(self.options['strike']==self.put_strike_low)&(self.options['type']=='PUT')][['date', 'lastPrice', 'strike']]
        put2.columns = ['date', 'putHigh', 'strikePutHigh']

        condor = call1.merge(call2, on='date', how='inner')
        condor = condor.merge(put1, on='date', how='inner')
        condor = condor.merge(put2, on='date', how='inner')

        condor['condor'] = condor.callLow-condor.callHigh-condor.putHigh+condor.putLow
        condor['strikeDiff'] = condor.strikeCallLow - condor.strikePutLow
            #condor['strikeVol'] = condor.strikeDiff/condor.close
        condor['riskCalls'] = condor.strikeCallHigh - condor.strikeCallLow
        condor['riskPuts'] = condor.strikePutLow-condor.strikePutHigh
        condor['risk'] = condor[['riskCalls', 'riskPuts']].max(axis=1)
        condor['riskRel'] = condor.condor/condor.risk
            #condor['condorValue'] = condor.valueCallLow-condor.valueCallHigh-condor.valuePutHigh+condor.valuePutLow
        condor['condorStrikeDiff'] = condor.strikeCallLow-condor.strikeCallHigh-condor.strikePutHigh+condor.strikePutLow
        condor.drop_duplicates()
            #if self.end_date > condor['expirationDate'].iloc[0] - datetime.timedelta(15):
            #    self.end_date = condor['expirationDate'].iloc[0] - datetime.timedelta(15) 
            #    condor = condor[(condor.date <= self.end_date)&(condor.date >= self.start_date)].copy()
            
        self.condor_options = condor
        self.risk_rel = self.condor_options.riskRel.iloc[0]
        self.days_to_strike = condor.daysBeforeExpiration.iloc[0]
        self.high_put_strike = condor.strikePutHigh.iloc[0]
        self.low_put_strike = condor.strikePutLow.iloc[0]
        self.low_call_strike = condor.strikeCallLow.iloc[0]
        self.high_call_strike = condor.strikeCallHigh.iloc[0]
        self.high_put = condor.putHigh.iloc[0]
        self.low_call = condor.callLow.iloc[0]
        self.high_call = condor.putLow.iloc[0]
        self.low_put = condor.callHigh.iloc[0]
        
        

    def filter_strike_options(self):
        strike_cols = self.options.pivot_table(columns="strike", values="date", aggfunc=np.count_nonzero).columns
        valid_call_strikes = [self.valid_strike('CALL', strike) for strike in strike_cols]
        valid_put_strikes = [self.valid_strike('PUT', strike) for strike in strike_cols]

        self.valid_call_strikes = np.array(strike_cols[valid_call_strikes])
        self.valid_put_strikes = np.array(strike_cols[valid_put_strikes])
 
    def valid_strike(self, option_type, strike):
        if option_type == "CALL":
            options = self.options[(self.options['strike']==strike)&(self.options['type']==option_type)&(self.options['strike']>self.close*(1+self.volatility*self.vol_factor))]
        else:
            options = self.options[(self.options['strike']==strike)&(self.options['type']==option_type)&(self.options['strike']<self.close*(1-self.volatility*self.vol_factor))]
        if len(options) > 0:
            return True
        else:
            return False

    def balance_condor(self):
        #strike_cols = self.options.pivot_table(columns="Strike", values="date", aggfunc=np.count_nonzero).columns
        strikes_above = self.valid_call_strikes
        strikes_below = self.valid_put_strikes
        
        if (len(strikes_above) > 1) & (len(strikes_below) > 1):
            self.call_strike_low = strikes_above[0]
            self.put_strike_high = strikes_below[len(strikes_below)-1]
            diff_calls = strikes_above[1] - self.call_strike_low
            diff_puts = -strikes_below[len(strikes_below)-2] + strikes_below[len(strikes_below)-1]
            if diff_calls > diff_puts:
                self.call_strike_high = strikes_above[1]
                self.put_strike_low = strikes_below[np.absolute(-strikes_below  + diff_calls + self.put_strike_high) == min(np.absolute(-strikes_below + diff_calls + self.put_strike_high))][0]
            else:
                self.put_strike_low = strikes_below[len(strikes_below)-2]
                self.call_strike_high = strikes_above[np.absolute(strikes_above  - diff_puts - self.call_strike_low) == min(np.absolute(strikes_above - diff_puts - self.call_strike_low))][0]
            self.is_valid = True

    def balance_risk(self):
        riskRel = self.condor_options.riskRel.iloc[0]
        while riskRel < 0.33:
            self.volatility = self.volatility * 0.95
            print(self.volatility)
            self.filter_strike_options()
            self.balance_condor()
            if self.is_valid:
                self.set_condor()
                riskRel = self.condor_options.riskRel.iloc[0]
                print(riskRel)
            if self.volatility <0.05:
                break

    def calculate_expected_return(self, strike_date):
        f = self.formula
        if self.is_valid:
            if self.risk_rel > 0:
                r = f['y0'] + f['probability']*0.68 * self.vol_factor/0.5 + f['iv']*self.iv + f['vix']*self.vix + f['days_to_strike']*self.days_to_strike + f['sqr_rel_risk']*np.log(self.risk_rel)
                ret = {'strike_date': strike_date, 'rel_risk': self.risk_rel, 'high_put_value': self.high_put, 'low_call_value': self.low_call, 'high_call_value': self.high_call, 'low_put_value': self.low_put, 'highStrikePut': self.high_put_strike, 'lowStrikeCall': self.low_call_strike, 'lowStrikePut': self.low_put_strike, 'highStrikeCall': self.high_call_strike, 'p': 0.68 * self.vol_factor/0.5, 'r': r}
            else:
                r = 2
                ret = {'strike_date': strike_date, 'rel_risk': None, 'high_put_value': None, 'low_call_value': None, 'high_call_value': None, 'low_put_value': None, 'highStrikePut': None, 'lowStrikeCall': None, 'lowStrikePut': None, 'highStrikeCall': None, 'p': 0.68 * self.vol_factor/0.5, 'r': r}
        else:
            r = 2
            ret = {'strike_date': strike_date, 'rel_risk': None, 'high_put_value': None, 'low_call_value': None, 'high_call_value': None, 'low_put_value': None,  'highStrikePut': None, 'lowStrikeCall': None, 'lowStrikePut': None, 'highStrikeCall': None, 'p': 0.68 * self.vol_factor/0.5, 'r': r}
        return ret
        
    def get_risk_and_returns(self, strike_date):
        return {'strike_date': strike_date, 'return': self.mean_return, 'rel_risk': self.risk_rel, 'probability': 0.68 * self.vol_factor/0.5, 'volatility': self.volatility, 'is_won':self.is_80_percente_won, 'days_to_strike': self.days_to_strike, 'iv': self.iv, 'iv2': self.iv2, 'is_lost': self.is_20_percent_lost, 'vix':self.vix}


class StockData():

    def __init__(self, ticker):
        self.stock_data = None
        self.ticker = ticker
        self.get_data()
        self.prepare_data()

    def get_data(self):
        # set date range for historical prices
        end_time = date.today()
        start_time = end_time - timedelta(days=400)
        
        # reformat date range
        end = end_time.strftime('%Y-%m-%d')
        start = start_time.strftime('%Y-%m-%d')
        
        # get daily stock prices over date range
        prices = get_data(self.ticker, start, end, 'daily')
        #compute daily returns and 20 day moving historical volatility
        window_size = 20
        prices['returns']=prices['close'].pct_change()
        prices['volatility']=prices['returns'].rolling(window_size).std()*(252**0.5)
        prices['date'] = prices.index
        self.stock_data = prices

    def prepare_data(self):
        window_size = 20
        self.stock_data['returns']=self.stock_data['close'].pct_change()
        self.stock_data['volatility']=self.stock_data['returns'].rolling(window_size).std()*(252**0.5)
        self.stock_data['date'] = self.stock_data.index

    def get_close(self, date):
        return self.stock_data.loc[date].close

    def get_vol(self, date):
        return self.stock_data.loc[date].volatility

    def rename_vix(self):
        self.stock_data = self.stock_data.rename(columns={'close':'vix'})

class ImpliedVolatility():

    def __init__(self, options, date):
        self.date = date
        self.options = options[(options.date == date)].copy()
        self.close = self.options.close.iloc[0]
        self.iv = 0
        self.filter_strike_options()
        self.set_implied_volatility()

    def filter_strike_options(self):
        strike_cols = self.options.pivot_table(columns="strike", values="date", aggfunc=np.count_nonzero).columns
        valid_call_strikes = [self.valid_strike('CALL', strike) for strike in strike_cols]
        valid_put_strikes = [self.valid_strike('PUT', strike) for strike in strike_cols]

        self.valid_call_strikes = np.array(strike_cols[valid_call_strikes])
        self.valid_put_strikes = np.array(strike_cols[valid_put_strikes])
 
    def valid_strike(self, option_type, strike):
        if option_type == "CALL":
            options = self.options[(self.options['strike']==strike)&(self.options['type']==option_type)]
        else:
            options = self.options[(self.options['strike']==strike)&(self.options['type']==option_type)]
        if len(options) > 0:
            return True
        else:
            return False

    def set_implied_volatility(self):
        strikes_above = self.valid_call_strikes
        strikes_below = self.valid_put_strikes
        
        if (len(strikes_above) > 0) & (len(strikes_below) > 0):
            put_am = strikes_below[np.absolute(-strikes_below  + self.close) == min(np.absolute(-strikes_below + self.close))][0]
            options_put = self.options[(self.options['strike']==put_am)&(self.options['type']=='PUT')]
            call_am = strikes_above[np.absolute(-strikes_above  + self.close) == min(np.absolute(-strikes_above + self.close))][0]
            options_call = self.options[(self.options['strike']==call_am)&(self.options['type']=='CALL')]
            self.iv = np.mean([options_call['iv'].iloc[0], options_put['iv'].iloc[0]])


def main():  
    print("starting")
    now = datetime.datetime.now()
    if now.weekday() not in [5,6]:
        t = TickerAggregation()
    

if __name__ == "__main__": 
    main()