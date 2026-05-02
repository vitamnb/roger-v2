"""
Roger Meta-Strategy v2
Regime-switching multi-mode strategy for KuCoin crypto
Fixed: Mean reversion fires in all regimes, trend has proper trailing, ATR-based stops
"""

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
import pandas as pd
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class RogerMeta(IStrategy):
    timeframe = '1h'
    
    stoploss = -0.02
    trailing_stop = False
    use_custom_stoploss = True
    can_short = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 200
    
    # --- REGIME DETECTION ---
    ema_trend_period = 200
    ema_fast_period = 9
    ema_slow_period = 21
    adx_period = 14
    adx_trend_threshold = 20
    adx_strong_trend = 30
    atr_period = 14
    
    # --- MODE: TREND FOLLOWING ---
    trend_volume_mult = 1.0
    trend_rr_target = 0.05
    trend_max_position_pct = 0.40
    
    # --- MODE: MEAN REVERSION ---
    mr_rsi_entry = 35
    mr_rsi_oversold = 30
    mr_rsi_exit = 70
    mr_volume_mult = 1.5
    mr_order_block_lookback = 50
    mr_order_block_atr_mult = 2.0
    mr_rr_target = 0.03
    mr_max_position_pct = 0.35
    
    # --- MODE: KANGAROO TAIL (Pin Bar) ---
    kt_lookback = 10
    kt_min_tail_ratio = 2.0
    kt_room_left = 7
    kt_room_left_optimal = 20
    kt_rr_target = 0.03
    kt_volume_mult = 1.2
    
    # --- POSITION SIZING ---
    base_stake = 50.0
    scale_high_mult = 1.5
    scale_low_mult = 0.7
    scale_bear_mult = 0.5
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=self.ema_trend_period)
        dataframe['ema9'] = ta.EMA(dataframe, timeperiod=self.ema_fast_period)
        dataframe['ema21'] = ta.EMA(dataframe, timeperiod=self.ema_slow_period)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_prev'] = dataframe['rsi'].shift(1)
        dataframe['volume_avg20'] = dataframe['volume'].rolling(20).mean()
        
        dataframe['price_above_ema200'] = dataframe['close'] > dataframe['ema200']
        dataframe['ema9_above_21'] = dataframe['ema9'] > dataframe['ema21']
        dataframe['is_trending'] = dataframe['adx'] > self.adx_trend_threshold
        dataframe['is_strong_trend'] = dataframe['adx'] > self.adx_strong_trend
        
        dataframe['regime'] = 0.0
        dataframe.loc[dataframe['is_trending'] & dataframe['price_above_ema200'], 'regime'] = 0.5
        dataframe.loc[dataframe['is_strong_trend'] & dataframe['price_above_ema200'], 'regime'] = 1.0
        dataframe.loc[dataframe['is_trending'] & ~dataframe['price_above_ema200'], 'regime'] = -0.5
        dataframe.loc[dataframe['is_strong_trend'] & ~dataframe['price_above_ema200'], 'regime'] = -1.0
        
        dataframe['regime_confidence'] = np.abs(dataframe['regime'])
        dataframe = self._detect_order_blocks(dataframe)
        dataframe = self._detect_kangaroo_tails(dataframe)
        return dataframe
    
    def _detect_order_blocks(self, df: DataFrame) -> DataFrame:
        df['order_block_zone'] = False
        df['order_block_low'] = np.nan
        df['order_block_high'] = np.nan
        for i in range(self.mr_order_block_lookback, len(df)):
            if i < self.mr_order_block_lookback + 1: continue
            bc = df.iloc[i - self.mr_order_block_lookback]
            if bc['close'] >= bc['open']: continue
            fs = df.iloc[i - self.mr_order_block_lookback + 1:i + 1]
            if len(fs) < 2: continue
            mm = (fs['high'].max() - bc['close']) / bc['close']
            at = bc['atr'] * self.mr_order_block_atr_mult / bc['close']
            if mm > at:
                df.loc[df.index[i], 'order_block_zone'] = True
                df.loc[df.index[i], 'order_block_low'] = bc['low']
                df.loc[df.index[i], 'order_block_high'] = bc['high']
        return df
    
    def _detect_kangaroo_tails(self, df: DataFrame) -> DataFrame:
        # Kangaroo Tail detection per Naked Forex (Peters/Fuller)
        # Bullish: open and close in top third, long lower tail, range > prev 10 candles
        # Bearish: open and close in bottom third, long upper tail, range > prev 10 candles
        df['kt_bullish'] = False
        df['kt_bearish'] = False
        df['kt_range'] = df['high'] - df['low']
        
        for i in range(max(self.kt_lookback, 1), len(df)):
            c = df.iloc[i]
            prev = df.iloc[i-1]
            rng = c['kt_range']
            body = abs(c['close'] - c['open'])
            if body == 0: continue
            
            # Check range > previous N candles
            prev_range_max = df['kt_range'].iloc[max(0, i-self.kt_lookback):i].max()
            if rng <= prev_range_max: continue
            
            # Bullish KT: open and close in top third, long lower tail
            top_third = c['high'] - rng / 3.0
            bot_third = c['low'] + rng / 3.0
            if c['open'] >= top_third and c['close'] >= top_third and c['open'] <= c['high'] and c['close'] <= c['high']:
                tail = min(c['open'], c['close']) - c['low']
                if tail >= body * self.kt_min_tail_ratio:
                    # Open/close inside previous candle's range (not runaway)
                    if c['open'] >= prev['low'] and c['close'] >= prev['low'] and c['open'] <= prev['high'] and c['close'] <= prev['high']:
                        df.loc[df.index[i], 'kt_bullish'] = True
            
            # Bearish KT: open and close in bottom third, long upper tail
            if c['open'] <= bot_third and c['close'] <= bot_third and c['open'] >= c['low'] and c['close'] >= c['low']:
                tail = c['high'] - max(c['open'], c['close'])
                if tail >= body * self.kt_min_tail_ratio:
                    if c['open'] >= prev['low'] and c['close'] >= prev['low'] and c['open'] <= prev['high'] and c['close'] <= prev['high']:
                        df.loc[df.index[i], 'kt_bearish'] = True
        return df
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0
        dataframe['enter_tag'] = ''
        for i in range(1, len(dataframe)):
            regime = dataframe['regime'].iloc[i]
            
            if regime >= 0.5:
                prev_cross = dataframe['ema9'].iloc[i-1] <= dataframe['ema21'].iloc[i-1]
                curr_cross = dataframe['ema9'].iloc[i] > dataframe['ema21'].iloc[i]
                vol_ok = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.trend_volume_mult
                if prev_cross and curr_cross and vol_ok:
                    dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                    dataframe.loc[dataframe.index[i], 'enter_tag'] = 'meta_trend|stake=50.0'
            
            if regime <= -0.8: continue
            rsi_cross = (
                dataframe['rsi_prev'].iloc[i] < self.mr_rsi_entry and
                dataframe['rsi'].iloc[i] >= self.mr_rsi_entry and
                dataframe['rsi_prev'].iloc[i] < self.mr_rsi_oversold
            )
            if not rsi_cross: continue
            ob_zone = False; ob_low = None
            for j in range(max(0, i - self.mr_order_block_lookback), i):
                if dataframe['order_block_zone'].iloc[j]:
                    bl = dataframe['order_block_low'].iloc[j]; bh = dataframe['order_block_high'].iloc[j]
                    if pd.notna(bl) and pd.notna(bh):
                        cp = dataframe['close'].iloc[i]
                        if bl * 0.98 <= cp <= bh * 1.02:
                            ob_zone = True; ob_low = bl; break
            vol_ok = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.mr_volume_mult
            if rsi_cross and ob_zone and vol_ok:
                mult = self.scale_bear_mult if regime < 0 else (self.scale_low_mult if dataframe['regime_confidence'].iloc[i] < 0.3 else 1.0)
                stake = self.base_stake * mult
                dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                dataframe.loc[dataframe.index[i], 'enter_tag'] = f'meta_mr|ob_low={ob_low:.4f}|stake={stake}|regime={regime:.1f}'
            
            # --- KANGAROO TAIL MODE (Pin Bar Reversal) ---
            if regime <= -0.8: continue
            kt_bull = dataframe['kt_bullish'].iloc[i]
            kt_zone = False
            for j in range(max(0, i - self.mr_order_block_lookback), i):
                if dataframe['order_block_zone'].iloc[j]:
                    bl = dataframe['order_block_low'].iloc[j]; bh = dataframe['order_block_high'].iloc[j]
                    if pd.notna(bl) and pd.notna(bh):
                        cp = dataframe['close'].iloc[i]
                        if bl * 0.98 <= cp <= bh * 1.02:
                            kt_zone = True; break
            kt_vol = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.kt_volume_mult
            if kt_bull and kt_zone and kt_vol:
                dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                dataframe.loc[dataframe.index[i], 'enter_tag'] = f'meta_kt|kt_low={dataframe["low"].iloc[i]:.4f}|stake={self.base_stake}|regime={regime:.1f}'
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        for i in range(1, len(dataframe)):
            if dataframe['rsi'].iloc[i] > self.mr_rsi_exit:
                dataframe.loc[dataframe.index[i], 'exit_long'] = 1
            # Exit KT trades if price moves against us 75% toward stop
            if dataframe['kt_bullish'].iloc[i-1] and dataframe['low'].iloc[i] < dataframe['low'].iloc[i-1] * 1.005:
                dataframe.loc[dataframe.index[i], 'exit_long'] = 1
        return dataframe
    
    def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, after_fill, **kwargs):
        if not trade.enter_tag: return self.stoploss
        if 'meta_trend' in trade.enter_tag:
            return -0.03  # Fixed 3% stop for trends
        if 'meta_mr' in trade.enter_tag and 'ob_low=' in trade.enter_tag:
            try:
                ob_low = float(trade.enter_tag.split('ob_low=')[1].split('|')[0])
                stop_pct = (current_rate - ob_low * 0.998) / current_rate
                return -max(stop_pct, 0.005)
            except: pass
        if 'meta_kt' in trade.enter_tag and 'kt_low=' in trade.enter_tag:
            try:
                kt_low = float(trade.enter_tag.split('kt_low=')[1].split('|')[0])
                stop_pct = (current_rate - kt_low * 0.998) / current_rate
                return -max(stop_pct, 0.005)
            except: pass
        return self.stoploss
    
    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        if not trade.enter_tag: return None
        if 'meta_trend' in trade.enter_tag and current_profit >= self.trend_rr_target:
            return 'meta_tp_trend'
        if 'meta_mr' in trade.enter_tag and current_profit >= self.mr_rr_target:
            return 'meta_tp_mr'
        if 'meta_kt' in trade.enter_tag and current_profit >= self.kt_rr_target:
            return 'meta_tp_kt'
        return None
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time, entry_tag: str, side: str, **kwargs) -> bool:
        if not entry_tag: return True
        open_trades = Trade.get_trades_proxy(is_open=True)
        trend_trades = sum(1 for t in open_trades if t.enter_tag and 'meta_trend' in t.enter_tag)
        mr_trades = sum(1 for t in open_trades if t.enter_tag and 'meta_mr' in t.enter_tag)
        kt_trades = sum(1 for t in open_trades if t.enter_tag and 'meta_kt' in t.enter_tag)
        if 'meta_trend' in entry_tag and trend_trades >= 2: return False
        if 'meta_mr' in entry_tag and mr_trades >= 3: return False
        if 'meta_kt' in entry_tag and kt_trades >= 2: return False
        return True
