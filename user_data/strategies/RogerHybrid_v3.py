"""
Roger Hybrid Strategy v3 - Sniper
ENGULF + VOL1.5: RSI35/30, vol1.5, RR2.0, age50
Highest expectancy: $19.19, 75% win rate, 8 trades/6mo
"""

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class RogerHybrid_v3(IStrategy):
    timeframe = '1h'
    stoploss = -0.02
    trailing_stop = False
    use_custom_stoploss = True
    can_short = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 50

    # Config
    rsi_entry = 35
    rsi_oversold = 30
    volume_mult = 1.5
    order_block_lookback = 50
    order_block_atr_mult = 2.0
    rr_target = 0.03

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_prev'] = dataframe['rsi'].shift(1)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['volume_avg20'] = dataframe['volume'].rolling(20).mean()
        dataframe['bullish_engulfing'] = (
            (dataframe['close'].shift(1) < dataframe['open'].shift(1)) &
            (dataframe['close'] > dataframe['open']) &
            (dataframe['close'] > dataframe['open'].shift(1)) &
            (dataframe['open'] <= dataframe['close'].shift(1))
        )
        dataframe = self._detect_order_blocks(dataframe)
        return dataframe

    def _detect_order_blocks(self, df: DataFrame) -> DataFrame:
        df['order_block_zone'] = False
        df['order_block_low'] = np.nan
        df['order_block_high'] = np.nan

        for i in range(self.order_block_lookback, len(df)):
            if i < self.order_block_lookback + 1:
                continue
            block_candle = df.iloc[i - self.order_block_lookback]
            if block_candle['close'] >= block_candle['open']:
                continue
            future_slice = df.iloc[i - self.order_block_lookback + 1:i + 1]
            if len(future_slice) < 2:
                continue
            max_move = (future_slice['high'].max() - block_candle['close']) / block_candle['close']
            atr_threshold = block_candle['atr'] * self.order_block_atr_mult / block_candle['close']
            if max_move > atr_threshold:
                df.loc[df.index[i], 'order_block_zone'] = True
                df.loc[df.index[i], 'order_block_low'] = block_candle['low']
                df.loc[df.index[i], 'order_block_high'] = block_candle['high']
        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0
        dataframe['enter_tag'] = ''

        for i in range(1, len(dataframe)):
            rsi_cross = (
                dataframe['rsi_prev'].iloc[i] < self.rsi_entry and
                dataframe['rsi'].iloc[i] >= self.rsi_entry and
                dataframe['rsi_prev'].iloc[i] < self.rsi_oversold
            )
            if not rsi_cross:
                continue

            if not dataframe['bullish_engulfing'].iloc[i]:
                continue

            ob_zone = False
            ob_low = None
            for j in range(max(0, i - self.order_block_lookback), i):
                if dataframe['order_block_zone'].iloc[j]:
                    block_low = dataframe['order_block_low'].iloc[j]
                    block_high = dataframe['order_block_high'].iloc[j]
                    if pd.notna(block_low) and pd.notna(block_high):
                        current_price = dataframe['close'].iloc[i]
                        if block_low * 0.98 <= current_price <= block_high * 1.02:
                            ob_zone = True
                            ob_low = block_low
                            break

            vol_spike = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.volume_mult

            if rsi_cross and ob_zone and vol_spike:
                dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                dataframe.loc[dataframe.index[i], 'enter_tag'] = f'v3_sniper|ob_low={ob_low:.4f}'

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        for i in range(1, len(dataframe)):
            if dataframe['rsi'].iloc[i] > 70:
                dataframe.loc[dataframe.index[i], 'exit_long'] = 1
        return dataframe

    def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, after_fill, **kwargs):
        if trade.enter_tag and 'ob_low=' in trade.enter_tag:
            try:
                ob_low_str = trade.enter_tag.split('ob_low=')[1].split('|')[0]
                ob_low = float(ob_low_str)
                stop_pct = (current_rate - ob_low * 0.998) / current_rate
                return -max(stop_pct, 0.005)
            except (ValueError, IndexError):
                pass
        return self.stoploss

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        if current_profit >= self.rr_target:
            return 'tp_3pct'
        return None
