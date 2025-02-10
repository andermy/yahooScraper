import pandas as pd
from black_scholes import black_scholes
from strategy_template import VolatilityTradingStrategyTemplate
pd.options.mode.chained_assignment = None


class VolatilityTradingStrategy(VolatilityTradingStrategyTemplate):
    """
    Class for implementing a trading strategy based on volatility signals.
    """
    def __init__(self, ticker, start_date, end_date, rolling_window=5, band_multiplier=1.5, transaction_cost=200):
        """
        Initialize the trading strategy.
        
        :param ticker: Stock ticker symbol (e.g., 'SPY').
        :param start_date: Start date for historical data (YYYY-MM-DD).
        :param end_date: End date for historical data (YYYY-MM-DD).
        :param rolling_window: Window size for calculating rolling statistics (default: 5).
        :param band_multiplier: Multiplier for upper and lower bands (default: 1.5).
        :param transaction_cost: Percentage transaction cost per trade (default: 0.1%).
        """
        super().__init__(ticker, start_date, end_date, rolling_window, band_multiplier, transaction_cost)
        self.calculate_strategy()
        self.backtest()

    
    def calculate_strategy(self):
        """
        Calculate the Black-Scholes option price for each trading day.
        """
        r = 0.04
        T = 30 / 365  # Assuming 30 days to expiration
        capital_allocation = 20
        # Annualiser volatiliteten
        has_options_liste = []
        for i in range(len(self.data)):
            has_options = False
            if self.data['Sell_Signal'].iloc[i]:
                price = self.data['Adj Close'].iloc[i]
                std = self.data['Volatility_Anu'].iloc[i]
                t = pd.Timestamp(self.data.index[i])
                if not self.option_series or ((t - self.option_series[-1].index[-1]).days > 15):
                    calls_low = self.data.apply(lambda row: black_scholes(row['Adj Close'], price + std*2, max((t-pd.Timestamp(row.name)).days/365 + T,0), r, row['Volatility_Anu'], option_type='call'), axis=1)*1.35
                    calls_high = self.data.apply(lambda row: black_scholes(row['Adj Close'], price + std*2 + capital_allocation, max((t-pd.Timestamp(row.name)).days/365 + T,0), r, row['Volatility_Anu'], option_type='call'), axis=1)*1.35
                    puts_low = self.data.apply(lambda row: black_scholes(row['Adj Close'], price - std*2 -capital_allocation, max((t-pd.Timestamp(row.name)).days/365 + T,0), r, row['Volatility_Anu'], option_type='put'), axis=1)*1.35
                    puts_high = self.data.apply(lambda row: black_scholes(row['Adj Close'], price - std*2, max((t-pd.Timestamp(row.name)).days/365 + T,0), r, row['Volatility_Anu'], option_type='put'), axis=1)*1.35
                    calls_low = calls_low.loc[t:t + pd.Timedelta(days=15)]
                    calls_high = calls_high.loc[t:t + pd.Timedelta(days=15)]
                    puts_low = puts_low.loc[t:t + pd.Timedelta(days=15)]
                    puts_high = puts_high.loc[t:t + pd.Timedelta(days=15)]
                    combined_series = - calls_low + calls_high + puts_low - puts_high
                    combined_series = + combined_series - combined_series.iloc[0] + capital_allocation
                    has_options = True
                    prices = self.data['Adj Close'][combined_series.index]
                    volatility = self.data['Volatility_Anu'][combined_series.index]
                    df = pd.concat([prices, volatility, calls_high, calls_low, puts_high, puts_low, combined_series], axis=1)
                    df.columns = ['Adj Close', 'Volatility', 'Calls_high', 'Calls_low', 'Puts_high', 'Puts_low','Strategy']
                    self.option_series.append(df['Strategy'].loc[t:t + pd.Timedelta(days=15)].copy())
                    self.option_data_series.append((df.loc[t:t + pd.Timedelta(days=15)].copy()))
                        
            has_options_liste.append(has_options)
        self.data['Has Options'] = has_options_liste
            
    