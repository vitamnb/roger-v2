"""
Cascade-Fade Scalper for KuCoin Futures/Margin
Strategy: Fade liquidation cascade overshoots
Entry: Velocity spike (5-bar cumulative displacement) + volume 3x avg
Exit: Time-based (5 bars) - no targets, no trailing stops
"""

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
import pandas as pd
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class CascadeFadeFutures(IStrategy):
    # Futures on KuCoin uses 1m for scalping
    timeframe = '1m'
    
    # Minimal stop - cascade overshoots can run further
    stoploss = -0.01  # 1% hard stop (last resort)
    trailing_stop = False
    use_custom_stoploss = True
    can_short = False  # Spot mode - short signals ignored
    
    # Time-based exit
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    
    startup_candle_count = 50
    
    # Strategy parameters
    velocity_lookback = 5      # Cumulative displacement over N bars
    velocity_threshold = 0.003   # 0.3% displacement = cascade signal
    volume_mult = 3.0          # Volume 3x average = confirmation
    hold_bars = 5              # Exit after N bars (time-based)
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Velocity: cumulative displacement over lookback
        dataframe['displacement'] = (dataframe['close'] - dataframe['close'].shift(self.velocity_lookback)) / dataframe['close'].shift(self.velocity_lookback)
        
        # Volume average
        dataframe['volume_avg20'] = dataframe['volume'].rolling(20).mean()
        
        # Displacement of previous bar (for entry check)
        dataframe['displacement_prev'] = dataframe['displacement'].shift(1)
        dataframe['volume_prev'] = dataframe['volume'].shift(1)
        dataframe['volume_avg_prev'] = dataframe['volume_avg20'].shift(1)
        
        # Bar counter for time-based exits
        dataframe['bar_count'] = range(len(dataframe))
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'enter_long'] = 0
        dataframe.loc[:, 'enter_short'] = 0
        
        # LONG fade: cascade DOWN detected on previous bar
        # Enter long now, expecting bounce
        long_signal = (
            (dataframe['displacement_prev'] < -self.velocity_threshold) &
            (dataframe['volume_prev'] > dataframe['volume_avg_prev'] * self.volume_mult) &
            (dataframe['volume_avg_prev'] > 0)  # avoid div by zero
        )
        
        # SHORT fade: cascade UP detected on previous bar
        short_signal = (
            (dataframe['displacement_prev'] > self.velocity_threshold) &
            (dataframe['volume_prev'] > dataframe['volume_avg_prev'] * self.volume_mult) &
            (dataframe['volume_avg_prev'] > 0)
        )
        
        dataframe.loc[long_signal, 'enter_long'] = 1
        dataframe.loc[short_signal, 'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        dataframe.loc[:, 'exit_short'] = 0
        
        # Time-based exit: close after hold_bars
        # This is handled in custom_stoploss for simplicity
        # But also set exit signal for freqtrade framework
        
        # Get trade entry index if we have an open trade
        # freqtrade doesn't expose this easily in populate_exit_trend
        # So we use ROI-based exit as proxy
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time, current_rate,
                        current_profit, after_fill) -> float:
        """Time-based exit: close after hold_bars from entry"""
        if not trade.is_open:
            return self.stoploss
        
        # Calculate bars since entry
        bars_held = (current_time - trade.open_date_utc).total_seconds() / 60  # 1m timeframe
        
        if bars_held >= self.hold_bars:
            # Time exit - close at market
            return -0.0001  # Tiny stop to force close
        
        # Otherwise use hard stop
        return self.stoploss
    
    def leverage(self, pair: str, current_time, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str, side: str,
                 **kwargs) -> float:
        """Use 1x leverage (no leverage) for safety"""
        return 1.0
