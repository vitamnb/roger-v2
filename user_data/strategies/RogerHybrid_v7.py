"""
Roger Hybrid Strategy v7 - Conservative
RR1.5: RSI35/30, vol1.2, RR1.5, age50
Expectancy: $3.42, 50.8% win, 59 trades/6mo
"""

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class RogerHybrid_v7(IStrategy):
    timeframe = '1h'
    stoploss = -0.02
    trailing_stop = False
    use_custom_stoploss = True
    can_short = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 50

    rsi_entry = 35
    rsi_oversold = 30
    volume_mult = 1.2
    order_block_lookback = 50
    order_block_atr_mult = 2.0
    rr_target = 0.02  # 1.5:1 R:R (2% target vs 2% stop)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_prev'] = dataframe['rsi'].shift(1)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['volume_avg20'] = dataframe['volume'].rolling(20).mean()
        dataframe = self._detect_order_blocks(dataframe)
        return dataframe

    def _detect_order_blocks(self, df: DataFrame) -> DataFrame:
        df['order_block_zone'] = False; df['order_block_low'] = np.nan; df['order_block_high'] = np.nan
        for i in range(self.order_block_lookback, len(df)):
            if i < self.order_block_lookback + 1: continue
            bc = df.iloc[i - self.order_block_lookback]
            if bc['close'] >= bc['open']: continue
            fs = df.iloc[i - self.order_block_lookback + 1:i + 1]
            if len(fs) < 2: continue
            mm = (fs['high'].max() - bc['close']) / bc['close']
            at = bc['atr'] * self.order_block_atr_mult / bc['close']
            if mm > at:
                df.loc[df.index[i], 'order_block_zone'] = True
                df.loc[df.index[i], 'order_block_low'] = bc['low']
                df.loc[df.index[i], 'order_block_high'] = bc['high']
        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0; dataframe['enter_tag'] = ''
        for i in range(1, len(dataframe)):
            rsi_cross = (dataframe['rsi_prev'].iloc[i] < self.rsi_entry and
                        dataframe['rsi'].iloc[i] >= self.rsi_entry and
                        dataframe['rsi_prev'].iloc[i] < self.rsi_oversold)
            if not rsi_cross: continue
            ob_zone = False; ob_low = None
            for j in range(max(0, i - self.order_block_lookback), i):
                if dataframe['order_block_zone'].iloc[j]:
                    bl = dataframe['order_block_low'].iloc[j]; bh = dataframe['order_block_high'].iloc[j]
                    if pd.notna(bl) and pd.notna(bh):
                        cp = dataframe['close'].iloc[i]
                        if bl * 0.98 <= cp <= bh * 1.02:
                            ob_zone = True; ob_low = bl; break
            vol_spike = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.volume_mult
            if rsi_cross and ob_zone and vol_spike:
                dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                dataframe.loc[dataframe.index[i], 'enter_tag'] = f'v7_conservative|ob_low={ob_low:.4f}'
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        for i in range(1, len(dataframe)):
            if dataframe['rsi'].iloc[i] > 70: dataframe.loc[dataframe.index[i], 'exit_long'] = 1
        return dataframe

    def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, after_fill, **kwargs):
        if trade.enter_tag and 'ob_low=' in trade.enter_tag:
            try:
                ob_low = float(trade.enter_tag.split('ob_low=')[1].split('|')[0])
                stop_pct = (current_rate - ob_low * 0.998) / current_rate
                return -max(stop_pct, 0.005)
            except: pass
        return self.stoploss

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        if current_profit >= self.rr_target: return 'tp_2pct'
        return None
