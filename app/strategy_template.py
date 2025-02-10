import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import seaborn as sns
from black_scholes import black_scholes

pd.options.mode.chained_assignment = None


class VolatilityTradingStrategyTemplate:
    """
    Class for implementing a trading strategy based on volatility signals.
    """
    def __init__(self, ticker, start_date, end_date, rolling_window=5, band_multiplier=1.5, transaction_cost=2000):
        """
        Initialize the trading strategy.
        
        :param ticker: Stock ticker symbol (e.g., 'SPY').
        :param start_date: Start date for historical data (YYYY-MM-DD).
        :param end_date: End date for historical data (YYYY-MM-DD).
        :param rolling_window: Window size for calculating rolling statistics (default: 5).
        :param band_multiplier: Multiplier for upper and lower bands (default: 1.5).
        :param transaction_cost: Percentage transaction cost per trade (default: 0.1%).
        """
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.rolling_window = rolling_window
        self.band_multiplier = band_multiplier
        self.transaction_cost = transaction_cost
        self.data = None
        self.signals = None
        self.performance = None
        self.option_series = []
        self.option_data_series = []
        self.fetch_data()
        self.calculate_volatility()
        self.fetch_vix_data()
        self.generate_signals()
        
    def fetch_data(self):
        """
        Fetch historical data using yFinance.
        """
        print(f"Fetching data for {self.ticker} from {self.start_date} to {self.end_date}...")
        self.data = yf.download(self.ticker, start=self.start_date, end=self.end_date)
        self.data['Return'] = self.data['Adj Close'].pct_change()
        self.data = self.data.dropna()
    
    def fetch_vix_data(self):
        """
        Fetch historical data for VIX using yFinance.
        """
        print(f"Fetching data for VIX from {self.start_date} to {self.end_date}...")
        vix = yf.download("^VIX", start=self.start_date, end=self.end_date)
        vix = vix.dropna()
        vix['VIX_std'] = vix['Adj Close'].rolling(window=self.rolling_window).std()
        vix['VIX_mean'] = vix['Adj Close'].rolling(window=self.rolling_window).mean()
        vix['VIX_Upper_Band'] = vix['VIX_mean'] + self.band_multiplier * vix['VIX_std']
        vix['VIX_Lower_Band'] = vix['VIX_mean'] - self.band_multiplier * vix['VIX_std']
        self.data['VIX'] = vix['VIX_mean']
        self.data['VIX_Upper_Band'] = vix['VIX_Upper_Band']
        self.data['VIX_Lower_Band'] = vix['VIX_Lower_Band']

    def calculate_volatility(self):
        """
        Calculate rolling volatility and generate trading bands.
        """
        self.data['Volatility'] = self.data['Return'].rolling(window=self.rolling_window).std()
        self.data['Volatility_Anu'] = self.data['Volatility']  * np.sqrt(252)
        self.data['Rolling_Mean_Vol'] = self.data['Volatility'].rolling(window=self.rolling_window).mean()
        self.data['Rolling_Std_Vol'] = self.data['Volatility'].rolling(window=self.rolling_window).std()
        self.data['Upper_Band'] = self.data['Rolling_Mean_Vol'] + self.band_multiplier * self.data['Rolling_Std_Vol']
        self.data['Lower_Band'] = self.data['Rolling_Mean_Vol'] - self.band_multiplier * self.data['Rolling_Std_Vol']
        
    def generate_signals(self):
        """
        Generate buy and sell signals based on volatility bands.
        """
        self.data['Buy_Signal'] = (self.data['Volatility'] < self.data['Lower_Band']) & (self.data['Volatility_Anu'] < 0.07)
        self.data['Sell_Signal'] = (self.data['Volatility'] > self.data['Upper_Band']) & (self.data['VIX'] > 30)
        self.signals = self.data[['Buy_Signal', 'Sell_Signal']]

            
    def backtest(self, initial_capital=10000):
        """
        Backtest the strategy with Strategy positions based on Black-Scholes option prices.
        
        :param initial_capital: Starting amount for the backtest.
        """
        print("Backtesting strategy with Strategy positions...")
        cash = initial_capital
        portfolio_values = []

        # Kombiner alle verdier fra buy_series til en enkelt pandas Series
        combined_series = pd.Series(dtype=float)
        position = cash / self.option_series[0].iloc[0]
        for series in self.option_series:
            if not combined_series.empty:
                # Legg til siste verdi fra forrige serie til første verdi i nåværende serie
                series = series + combined_series.iloc[-1] - series.iloc[0] - self.transaction_cost/position
            combined_series = pd.concat([combined_series, series])
        
        # Interpolate NaN values in combined_series
        combined_series = combined_series.interpolate(method='linear')
        # Fill NaN values before the first value with 0
        combined_series = combined_series.fillna(0)
        # Iterer gjennom data og oppdater porteføljeverdi
        position = cash / combined_series.iloc[0]
            
        for date in combined_series.index:
            portfolio_values.append(position * combined_series.loc[date])

        # Konverter porteføljeverdier til en pandas Series for enkel sammenligning
        portfolio_values_series = pd.Series(portfolio_values, index=combined_series.index)
        self.data['Portfolio_Value'] = portfolio_values_series.copy()
        self.data['Portfolio_Value'] = self.data['Portfolio_Value'].interpolate(method='linear')
        self.data = self.data.dropna(subset=['Portfolio_Value', 'Volatility', 'VIX'])

        print(f"Sluttverdi av porteføljen: {portfolio_values_series.iloc[-1]:.2f}")
    
    def get_strategy_stats(self):
        data = []
        for series in self.option_data_series:
            data.append({'Price': series.Strategy.iloc[0], 'Return': (series.Strategy.iloc[-1] - series.Strategy.iloc[0])/series.Strategy.iloc[0], 'Volatility': series['Volatility'].iloc[0], 'date': series.index[0]}) 

        return pd.DataFrame(data)

    def plot_strategy_stats(self):
        data = []
        for series in self.option_data_series:
            data.append({'Price': series.Strategy.iloc[0], 'Return': (series.Strategy.iloc[-1] - series.Strategy.iloc[0])/series.Strategy.iloc[0], 'ReturnStock': (series['Adj Close'].iloc[-1] - series['Adj Close'].iloc[0])/series['Adj Close'].iloc[0], 'Volatility': series['Volatility'].iloc[0]}) 

        df = pd.DataFrame(data)
        # Lag en scatter plot for å vise sammenhengen mellom opsjonspris og avkastning
        plt.figure(figsize=(10, 6))
        sns.scatterplot(x='Price', y='Return', data=df)
        plt.title('Sammenheng mellom opsjonspris og avkastning')
        plt.xlabel('Opsjonspris')
        plt.ylabel('Avkastning')
        plt.show()

        # Lag en scatter plot for å vise sammenhengen mellom aksjeavkastning og volatilitet
        plt.figure(figsize=(10, 6))
        sns.scatterplot(x='Return', y='Volatility', data=df)
        plt.title('Sammenheng mellom avkastning og volatilitet')
        plt.xlabel('Aksjeavkastning')
        plt.ylabel('Volatilitet')
        plt.show()

        # Lag en pair plot for å vise sammenhengen mellom alle variablene
        sns.pairplot(df)
        plt.suptitle('Sammenheng mellom opsjonspris, avkastning, aksjeavkastning og volatilitet', y=1.02)
        plt.show()
    
    def plot_strategy(self):
        """
        Plot volatility, signals, and portfolio performance.
        """
        
        plt.figure(figsize=(14, 8))

        # Plot Volatility
        plt.subplot(3, 1, 1)
        plt.plot(self.data['Volatility'], label='Volatility', color='blue', linewidth=1.5)
        #plt.plot(self.data['Adj Close'], label='Adj Close', color='black', linewidth=1.5)
        plt.plot(self.data['Upper_Band'], label='Upper Band', linestyle='--', color='red', linewidth=1.2)
        plt.plot(self.data['Lower_Band'], label='Lower Band', linestyle='--', color='green', linewidth=1.2)
        plt.scatter(self.data.index[self.data['Buy_Signal']], self.data['Volatility'][self.data['Buy_Signal']],
                    label='Buy Signal', color='lime', marker='o', s=100, edgecolor='black', zorder=5)
        plt.scatter(self.data.index[self.data['Sell_Signal']], self.data['Volatility'][self.data['Sell_Signal']],
                    label='Sell Signal', color='red', marker='x', s=100, linewidth=2, zorder=5)
        plt.scatter(self.data.index[self.data['Has Options']], self.data['Volatility'][self.data['Has Options']],
                    label='Has options', color='purple', marker='x', s=100, linewidth=2, zorder=5)
        plt.title(f"Volatility and Trading Signals for {self.ticker}")
        plt.legend()
        plt.grid(alpha=0.3)

        # Plot Portfolio Value
        plt.subplot(3, 1, 2)
        plt.plot(self.data['Portfolio_Value'], label='Portfolio Value', color='purple')

        plt.title("Portfolio Performance")
        plt.legend()
        plt.grid(alpha=0.3)
        
        # Plot volatility VIX
        plt.subplot(3, 1, 3)
        plt.plot(self.data['VIX'], label='VIX', color='blue', linewidth=1.5)
        plt.plot(self.data['VIX_Upper_Band'], label='Upper Band', linestyle='--', color='red', linewidth=1.2)
        plt.plot(self.data['VIX_Lower_Band'], label='Lower Band', linestyle='--', color='green', linewidth=1.2)
        
        plt.title("Portfolio Performance")
        plt.legend()
        plt.grid(alpha=0.3)

        plt.tight_layout()
        plt.show()

    def plot_trade(self, number, columns):
        """
        Plot volatility, signals, and portfolio performance.
        """
        plt.figure(figsize=(14, 8))

        # Plot Volatility
        plt.subplot(2, 1, 1)
        plt.plot(self.option_data_series[number]['Adj Close'], label='Price', color='blue', linewidth=1.5)
        #plt.plot(self.data['Adj Close'], label='Adj Close', color='black', linewidth=1.5)
        plt.title(f"Stock Price and Trading Signals for {self.ticker}")
        plt.legend()
        plt.grid(alpha=0.3)

        # Plot Portfolio Value
        #'Call Price', 'Put Price', 'Strategy Price'
        colors = ['blue', 'red', 'green', 'purple', 'orange']
        plt.subplot(2, 1, 2)
        for ind, column in enumerate(columns):
            plt.plot(self.option_data_series[number][column], label=column, color=colors[ind])
        plt.title("Portfolio Performance")
        plt.legend()
        plt.grid(alpha=0.3)

        plt.tight_layout()
        plt.show()

