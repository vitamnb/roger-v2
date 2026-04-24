# Roger Hybrid Strategy - Variants v1-v9
# Base strategy with parameter-driven variations

from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter, BooleanParameter
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class RogerHybrid_v1(IStrategy):
    """
    v1: Baseline - RSI35/30, vol1.2, RR2.0, age50, no engulf
    """
    INTERFACE_VERSION = 3
    timeframe = '1h'
    stoploss = -0.02
    trailing_stop = False
    use_custom_stoploss = False

    # Parameters
    rsi_entry = IntParameter(30, 45, default=35, space="buy")
    rsi_oversold = IntParameter(15, 30, default=30, space="buy")
    volume_mult = DecimalParameter(1.0, 3.0, default=1.2, space="buy")
    rr_ratio = DecimalParameter(1.5, 3.0, default=2.0, space="buy")
    block_age = IntParameter(10, 100, default=50, space="buy")
    use_engulfing = BooleanParameter(default=False, space="buy")
    use_rsi70_exit = BooleanParameter(default=False, space="sell")

    # ROI table (not used since we use custom exits)
    minimal_roi = {"0": 1}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_prev'] = dataframe['rsi'].shift(1)
        dataframe['volume_avg20'] = dataframe['volume'].rolling(20).mean()
        
        # Order block detection (simplified for live)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['bullish_block'] = self.detect_blocks(dataframe, 'bullish')
        
        # Engulfing
        dataframe['engulfing'] = (
            (dataframe['close'].shift(1) < dataframe['open'].shift(1)) &
            (dataframe['close'] > dataframe['open']) &
            (dataframe['close'] > dataframe['open'].shift(1)) &
            (dataframe['open'] <= dataframe['close'].shift(1))
        )
        
        return dataframe

    def detect_blocks(self, df, block_type):
        """Simplified order block detection for live trading."""
        blocks = []
        for i in range(5, len(df)):
            if df['close'].iloc[i] > df['open'].iloc[i]:  # Bullish candle
                if df['low'].iloc[i] < df['low'].iloc[i-1] and df['low'].iloc[i] < df['low'].iloc[i-2]:
                    blocks.append(i)
        return pd.Series([i in blocks for i in range(len(df))])

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        
        # RSI signal
        conditions.append(dataframe['rsi_prev'] < self.rsi_entry.value)
        conditions.append(dataframe['rsi'] >= self.rsi_entry.value)
        conditions.append(dataframe['rsi_prev'] < self.rsi_oversold.value)
        
        # Volume
        conditions.append(dataframe['volume'] > dataframe['volume_avg20'] * self.volume_mult.value)
        
        # Order block zone (simplified)
        conditions.append(dataframe['bullish_block'])
        
        # Engulfing
        if self.use_engulfing.value:
            conditions.append(dataframe['engulfing'])
        
        dataframe.loc[reduce(lambda x, y: x & y, conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Custom exit logic handled in custom_exit or stoploss
        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                   current_profit: float, **kwargs) -> str:
        if self.use_rsi70_exit.value:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            last_candle = dataframe.iloc[-1]
            if last_candle['rsi'] > 70:
                return "rsi70_exit"
        return None


# Import for reduce
from functools import reduce
import pandas as pd
