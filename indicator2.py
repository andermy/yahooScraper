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

class Options():

    def __init__(self, ticker):
        self.mongodb = s.StockMongo()
        try:
            self.options = self.mongodb.get_options(ticker)
            self.start_date = min(self.options.index)
            self.end_date = max(self.options.index)
            self.strike_dates = []
            self.strikeDates = []
            self.ticker = ticker
            self.prepare_options()
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
        self.map_strike_date_objects()
        self.map_strike_dates_returns()
        
    def prepare_options(self):
        self.options = self.options[self.options['lastTradeDateTime']!='0000-00-00 00:00:00']
        self.options['lastTradeDateTime'] = pd.to_datetime(self.options['lastTradeDateTime'], format='%Y-%m-%d')
        
    def map_strike_dates(self):
        options = self.options[(self.options['daysBeforeExpiration']<50)&(self.options['daysBeforeExpiration']>40)]
        self.strike_dates = options.pivot_table(columns="expirationDate", values="volume", aggfunc=np.count_nonzero).columns

    def set_strike_date(self, num=7):
        self.options = self.options[self.options['expirationDate']==self.strike_dates[num]]

    def merge_stock_data(self):
        self.options = self.options.merge(self.stock_data.stock_data[['close', 'volatility', 'date']], on='date')

    def merge_vix_data(self):
        self.vix.rename_vix()
        self.options = self.options.merge(self.vix.stock_data[['vix', 'date']], on='date')

    def map_strike_date_objects(self):
        self.strikeDates = self.strike_dates.map(lambda x: StrikeDateOptions(options=self.options, strike_date=x))
    
    def map_strike_dates_returns(self):
        self.returns = pd.DataFrame(list(itertools.chain(*[sDate.returns for sDate in self.strikeDates])))
    
    def count_records(self):
        self.len_records =  len(self.options)

    def regression(self):
        linear_regressor = LinearRegression()
        selection = self.returns[(self.returns['rel_risk']>0)&(self.returns['rel_risk']<3)&(self.returns['return']>0)&(self.returns['return']<2)]
        selection['sqr_rel_risk'] = np.log(selection['rel_risk'])
        y = selection['return']
        x = selection[['sqr_rel_risk', 'probability', 'iv', 'vix', 'days_to_strike']]
        linear_regressor.fit(x, y)
        now = datetime.datetime.now()
        now = datetime.datetime.strptime(now.strftime("%m/%d/%Y"),"%m/%d/%Y")
        return_dict = {
            'y0': linear_regressor.intercept_,
            'sqr_rel_risk': linear_regressor.coef_[0],
            'probability': linear_regressor.coef_[1], 
            'iv': linear_regressor.coef_[2], 
            'vix': linear_regressor.coef_[3], 
            'days_to_strike': linear_regressor.coef_[4],
            'ticker': self.ticker,
            'date': now
        }
        self.mongodb.add_analysis(return_dict)
                

class StrikeDateOptions():

    def __init__(self, options, strike_date):
        self.options = options
        self.mapped_options = None
        self.strike_date = strike_date
        self.condors = []
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
        self.volRange = date_list.map(lambda x: VolatilityRange(options=self.mapped_options, strike_date=self.strike_date, start_date=x))
        
    def map_returns(self):
        self.returns = [condor.mean_return for condor in self.condors]

    def map_risk_returns(self):
        self.returns = [condor.get_risk_and_returns(self.strike_date) for condor in self.condors]

    def map_vol_range_returns(self):
        self.returns = list(itertools.chain(*[vol.returns for vol in self.volRange]))
    
class VolatilityRange():

    def __init__(self, options, strike_date, start_date=datetime.datetime.now() - datetime.timedelta(45), end_date=datetime.datetime.now()):
        self.start_date = start_date
        self.end_date = end_date
        self.strike_date = strike_date
        self.options = options
        self.map_condor()
        self.map_risk_returns()
    
    def map_condor(self):
        vols = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]
        self.condors = [Condor(options=self.options, vol_factor=vol, start_date=self.start_date) for vol in vols]
        #self.condors = vols.map(lambda x: Condor(options=self.mapped_options, vol_factor=x, start_date=self.start_date))
        
    def map_risk_returns(self):
        self.returns = [condor.get_risk_and_returns(self.strike_date) for condor in self.condors]


class Condor():

    def __init__(self, options, vol_factor, start_date=datetime.datetime.now() - datetime.timedelta(45), end_date=datetime.datetime.now()):
        self.call_strike_low = None
        self.call_strike_high = None
        self.put_strike_low = None
        self.put_strike_high = None
        self.start_date = start_date
        self.end_date = end_date
        self.options = options[(options.date <= self.end_date)&(options.date >= self.start_date)].copy()
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

        if len(condor) >1:
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
            condor['change'] = condor.condor.pct_change()
            init_value = condor.condor.iloc[0]
            condor['80percentWon'] = condor.condor< init_value*0.2
            condor['20percentLost'] = condor.condor> init_value*1.2
            condor['returns'] = condor.condor/init_value
            if condor['80percentWon'].sum() > 0:
                self.is_80_percente_won = True
            if condor['20percentLost'].sum() > 0:
                self.is_20_percent_lost = True
            if self.end_date > condor['expirationDate'].iloc[0] - datetime.timedelta(15):
                self.end_date = condor['expirationDate'].iloc[0] - datetime.timedelta(15) 
                condor = condor[(condor.date <= self.end_date)&(condor.date >= self.start_date)].copy()
            if len(condor) > 2:
                self.mean_return = condor.returns.iloc[-1]
                self.risk_rel = condor.riskRel.iloc[0]
                self.days_to_strike = condor.daysBeforeExpiration.iloc[0]
        
        self.condor_options = condor

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
        if len(options) > 5:
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
    d = datetime.datetime.now()
    day_of_month = int(d.strftime("%d"))
    month = int(d.strftime("%m"))
    odd = int((month % 2) >0)
    print("getting symbols")
    m = s.StockMongo()
    symbols = m.get_symbols()
    tickers = []
    for sym in symbols:
        tickers.append(sym['sym'])
    
    start = int(6 * (day_of_month-1)) + 100*odd
    if start-9 <= len(tickers):
        print("running data collection")
        for tick in tickers[start+4:start+7]:
            try:
                o = Options(tick)
                o.regression()
                print("Completed for " + str(tick))
            except:
                print("Error for " + str(tick))

if __name__ == "__main__": 
    main()