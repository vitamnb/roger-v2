"""
Roger Meta-Strategy v2.3
Regime-switching multi-mode strategy for KuCoin crypto
Modes: Trend | Mean Reversion | Kangaroo Tail | Big Shadow | Wammies/Moolahs
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
    
    # --- MODE: KANGAROO TAIL ---
    kt_lookback = 10
    kt_min_tail_ratio = 2.0
    kt_room_left = 7
    kt_room_left_optimal = 20
    kt_rr_target = 0.03
    kt_volume_mult = 1.2
    kt_max_trades = 2
    
    # --- MODE: BIG SHADOW ---
    bs_lookback = 5
    bs_optimal_lookback = 10
    bs_room_left = 7
    bs_room_left_optimal = 20
    bs_volume_mult = 1.2
    bs_rr_target = 0.04
    bs_max_trades = 2
    
    # --- MODE: WAMMIES (Bullish Double Bottom) ---
    wammies_min_candles_between = 6
    wammies_optimal_candles = 20
    wammies_volume_mult = 1.2
    wammies_rr_target = 0.04
    wammies_max_trades = 2
    
    # --- MODE: MOOLAHS (Bearish Double Top) ---
    moolahs_min_candles_between = 6
    moolahs_optimal_candles = 20
    moolahs_volume_mult = 1.2
    moolahs_rr_target = 0.04
    moolahs_max_trades = 2
    
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
        dataframe = self._detect_big_shadows(dataframe)
        dataframe = self._detect_wammies_moolahs(dataframe)
        return dataframe

    def _detect_order_blocks(self, df: DataFrame) -> DataFrame:
        df['order_block_zone'] = False
        df['order_block_low'] = np.nan
        df['order_block_high'] = np.nan
        lookback = self.mr_order_block_lookback
        for i in range(lookback, len(df)):
            bc = df.iloc[i - lookback]
            if bc['close'] >= bc['open']:
                continue
            fs = df.iloc[i - lookback + 1:i + 1]
            if len(fs) < 2:
                continue
            mm = (fs['high'].max() - bc['close']) / bc['close']
            at = bc['atr'] * self.mr_order_block_atr_mult / bc['close']
            if mm > at:
                df.loc[df.index[i], 'order_block_zone'] = True
                df.loc[df.index[i], 'order_block_low'] = bc['low']
                df.loc[df.index[i], 'order_block_high'] = bc['high']
        return df

    def _detect_kangaroo_tails(self, df: DataFrame) -> DataFrame:
        df['kt_bullish'] = False
        df['kt_bearish'] = False
        df['kt_range'] = df['high'] - df['low']
        
        for i in range(max(self.kt_lookback, 1), len(df)):
            c = df.iloc[i]
            prev = df.iloc[i-1]
            rng = c['kt_range']
            body = abs(c['close'] - c['open'])
            if body == 0:
                continue
            
            prev_range_max = df['kt_range'].iloc[max(0, i-self.kt_lookback):i].max()
            if rng <= prev_range_max:
                continue
            
            top_third = c['high'] - rng / 3.0
            bot_third = c['low'] + rng / 3.0
            
            if (c['open'] >= top_third and c['close'] >= top_third and
                c['open'] <= c['high'] and c['close'] <= c['high']):
                tail = min(c['open'], c['close']) - c['low']
                if tail >= body * self.kt_min_tail_ratio:
                    if (c['open'] >= prev['low'] and c['close'] >= prev['low'] and
                        c['open'] <= prev['high'] and c['close'] <= prev['high']):
                        df.loc[df.index[i], 'kt_bullish'] = True
            
            if (c['open'] <= bot_third and c['close'] <= bot_third and
                c['open'] >= c['low'] and c['close'] >= c['low']):
                tail = c['high'] - max(c['open'], c['close'])
                if tail >= body * self.kt_min_tail_ratio:
                    if (c['open'] >= prev['low'] and c['close'] >= prev['low'] and
                        c['open'] <= prev['high'] and c['close'] <= prev['high']):
                        df.loc[df.index[i], 'kt_bearish'] = True
        return df

    def _detect_big_shadows(self, df: DataFrame) -> DataFrame:
        df['bs_bullish'] = False
        df['bs_bearish'] = False
        df['bs_range'] = df['high'] - df['low']
        
        for i in range(max(self.bs_optimal_lookback, 2), len(df)):
            c1 = df.iloc[i-1]
            c2 = df.iloc[i]
            
            # Bullish Big Shadow: candle2 engulfs candle1, close near high
            c2_range = c2['bs_range']
            c1_range = c1['bs_range']
            if c2_range <= c1_range:
                continue
            
            prev_max = df['bs_range'].iloc[max(0, i-self.bs_lookback):i].max()
            prev_opt_max = df['bs_range'].iloc[max(0, i-self.bs_optimal_lookback):i].max()
            
            # Check if c2_range is widest of last 5 (optimal: 10)
            if c2_range <= prev_max:
                continue
            
            # Bullish: c2 engulfs c1, close in upper third
            if (c2['low'] < c1['low'] and c2['high'] > c1['high'] and
                c2['close'] >= c2['low'] + c2_range * 0.66):
                # Room to left check
                left_bars = df.iloc[max(0, i-self.bs_room_left):i]
                room_ok = (c2_range > left_bars['bs_range'].max() * 0.8) if len(left_bars) > 0 else True
                if room_ok:
                    df.loc[df.index[i], 'bs_bullish'] = True
            
            # Bearish Big Shadow: c2 engulfs c1, close in lower third
            if (c2['low'] < c1['low'] and c2['high'] > c1['high'] and
                c2['close'] <= c2['low'] + c2_range * 0.33):
                left_bars = df.iloc[max(0, i-self.bs_room_left):i]
                room_ok = (c2_range > left_bars['bs_range'].max() * 0.8) if len(left_bars) > 0 else True
                if room_ok:
                    df.loc[df.index[i], 'bs_bearish'] = True
        return df

    def _detect_wammies_moolahs(self, df: DataFrame) -> DataFrame:
        df['wammie'] = False
        df['moolah'] = False
        
        for i in range(self.wammies_optimal_candles + 5, len(df)):
            # Wammie: double bottom, 2nd touch higher low
            for j in range(self.wammies_min_candles_between, self.wammies_optimal_candles + 1):
                if i - j < 1:
                    continue
                t1 = df.iloc[i - j]
                t2 = df.iloc[i]
                
                # Second touch higher low than first
                if t2['low'] > t1['low'] * 1.001:
                    # Check candles between - price moved up
                    between = df.iloc[i-j+1:i]
                    if len(between) > 0 and between['high'].max() > t1['high'] * 1.01:
                        # Strong bullish candle on 2nd touch
                        if t2['close'] > t2['open'] and (t2['close'] - t2['open']) / (t2['high'] - t2['low'] + 0.0001) > 0.5:
                            df.loc[df.index[i], 'wammie'] = True
                            break
            
            # Moolah: double top, 2nd touch lower high
            for j in range(self.moolahs_min_candles_between, self.moolahs_optimal_candles + 1):
                if i - j < 1:
                    continue
                t1 = df.iloc[i - j]
                t2 = df.iloc[i]
                
                # Second touch lower high than first
                if t2['high'] < t1['high'] * 0.999:
                    # Check candles between - price moved down
                    between = df.iloc[i-j+1:i]
                    if len(between) > 0 and between['low'].min() < t1['low'] * 0.99:
                        # Strong bearish candle on 2nd touch
                        if t2['close'] < t2['open'] and (t2['open'] - t2['close']) / (t2['high'] - t2['low'] + 0.0001) > 0.5:
                            df.loc[df.index[i], 'moolah'] = True
                            break
        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0
        dataframe['enter_tag'] = ''
        
        for i in range(1, len(dataframe)):
            regime = dataframe['regime'].iloc[i]
            
            # --- MODE 1: TREND FOLLOWING ---
            if regime >= 0.5:
                prev_cross = dataframe['ema9'].iloc[i-1] <= dataframe['ema21'].iloc[i-1]
                curr_cross = dataframe['ema9'].iloc[i] > dataframe['ema21'].iloc[i]
                vol_ok = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.trend_volume_mult
                if prev_cross and curr_cross and vol_ok:
                    dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                    dataframe.loc[dataframe.index[i], 'enter_tag'] = 'meta_trend|stake=50.0'
                    continue
            
            # --- MODE 2: MEAN REVERSION ---
            if regime <= -0.8:
                continue
            rsi_cross = (
                dataframe['rsi_prev'].iloc[i] < self.mr_rsi_entry and
                dataframe['rsi'].iloc[i] >= self.mr_rsi_entry and
                dataframe['rsi_prev'].iloc[i] < self.mr_rsi_oversold
            )
            if not rsi_cross:
                continue
            
            ob_zone = False
            ob_low = None
            for j in range(max(0, i - self.mr_order_block_lookback), i):
                if dataframe['order_block_zone'].iloc[j]:
                    bl = dataframe['order_block_low'].iloc[j]
                    bh = dataframe['order_block_high'].iloc[j]
                    if pd.notna(bl) and pd.notna(bh):
                        cp = dataframe['close'].iloc[i]
                        if bl * 0.98 <= cp <= bh * 1.02:
                            ob_zone = True
                            ob_low = bl
                            break
            
            vol_ok = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.mr_volume_mult
            if rsi_cross and ob_zone and vol_ok:
                mult = self.scale_bear_mult if regime < 0 else (
                    self.scale_low_mult if dataframe['regime_confidence'].iloc[i] < 0.3 else 1.0
                )
                stake = self.base_stake * mult
                dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                dataframe.loc[dataframe.index[i], 'enter_tag'] = f'meta_mr|ob_low={ob_low:.4f}|stake={stake}|regime={regime:.1f}'
                continue
            
            # --- MODE 3: KANGAROO TAIL ---
            if regime <= -0.8:
                continue
            
            kt_bull = dataframe['kt_bullish'].iloc[i]
            if not kt_bull:
                continue
            
            kt_zone = False
            for j in range(max(0, i - self.mr_order_block_lookback), i):
                if dataframe['order_block_zone'].iloc[j]:
                    bl = dataframe['order_block_low'].iloc[j]
                    bh = dataframe['order_block_high'].iloc[j]
                    if pd.notna(bl) and pd.notna(bh):
                        cp = dataframe['close'].iloc[i]
                        if bl * 0.98 <= cp <= bh * 1.02:
                            kt_zone = True
                            break
            
            kt_vol = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.kt_volume_mult
            if kt_zone and kt_vol:
                dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                kt_low = dataframe['low'].iloc[i]
                dataframe.loc[dataframe.index[i], 'enter_tag'] = f'meta_kt|kt_low={kt_low:.4f}|stake={self.base_stake}|regime={regime:.1f}'
                continue
            
            # --- MODE 4: BIG SHADOW ---
            bs_bull = dataframe['bs_bullish'].iloc[i]
            if bs_bull:
                bs_zone = False
                for j in range(max(0, i - self.mr_order_block_lookback), i):
                    if dataframe['order_block_zone'].iloc[j]:
                        bl = dataframe['order_block_low'].iloc[j]
                        bh = dataframe['order_block_high'].iloc[j]
                        if pd.notna(bl) and pd.notna(bh):
                            cp = dataframe['close'].iloc[i]
                            if bl * 0.98 <= cp <= bh * 1.02:
                                bs_zone = True
                                break
                bs_vol = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.bs_volume_mult
                if bs_zone and bs_vol:
                    dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                    bs_low = dataframe['low'].iloc[i-1]
                    dataframe.loc[dataframe.index[i], 'enter_tag'] = f'meta_bs|bs_low={bs_low:.4f}|stake={self.base_stake}|regime={regime:.1f}'
                    continue
            
            # --- MODE 5: WAMMIES ---
            if dataframe['wammie'].iloc[i]:
                wammie_vol = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.wammies_volume_mult
                if wammie_vol:
                    w_low = dataframe['low'].iloc[i]
                    dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                    dataframe.loc[dataframe.index[i], 'enter_tag'] = f'meta_wammie|w_low={w_low:.4f}|stake={self.base_stake}|regime={regime:.1f}'
                    continue
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        for i in range(1, len(dataframe)):
            if dataframe['rsi'].iloc[i] > self.mr_rsi_exit:
                dataframe.loc[dataframe.index[i], 'exit_long'] = 1
                continue
            
            if dataframe['kt_bullish'].iloc[i-1]:
                if dataframe['low'].iloc[i] < dataframe['low'].iloc[i-1] * 1.005:
                    dataframe.loc[dataframe.index[i], 'exit_long'] = 1
        return dataframe

    def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, after_fill, **kwargs):
        if not trade.enter_tag:
            return self.stoploss
        
        tag = trade.enter_tag
        
        if 'meta_trend' in tag:
            return -0.03
        
        if 'meta_mr' in tag and 'ob_low=' in tag:
            try:
                ob_low = float(tag.split('ob_low=')[1].split('|')[0])
                stop_pct = (current_rate - ob_low * 0.998) / current_rate
                return -max(stop_pct, 0.005)
            except (ValueError, IndexError):
                return self.stoploss
        
        if 'meta_kt' in tag and 'kt_low=' in tag:
            try:
                kt_low = float(tag.split('kt_low=')[1].split('|')[0])
                stop_pct = (current_rate - kt_low * 0.998) / current_rate
                return -max(stop_pct, 0.005)
            except (ValueError, IndexError):
                return self.stoploss
        
        if 'meta_bs' in tag and 'bs_low=' in tag:
            try:
                bs_low = float(tag.split('bs_low=')[1].split('|')[0])
                stop_pct = (current_rate - bs_low * 0.998) / current_rate
                return -max(stop_pct, 0.005)
            except (ValueError, IndexError):
                return self.stoploss
        
        if 'meta_wammie' in tag and 'w_low=' in tag:
            try:
                w_low = float(tag.split('w_low=')[1].split('|')[0])
                stop_pct = (current_rate - w_low * 0.998) / current_rate
                return -max(stop_pct, 0.005)
            except (ValueError, IndexError):
                return self.stoploss
        
        return self.stoploss

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        if not trade.enter_tag:
            return None
        
        if 'meta_trend' in trade.enter_tag and current_profit >= self.trend_rr_target:
            return 'meta_tp_trend'
        if 'meta_mr' in trade.enter_tag and current_profit >= self.mr_rr_target:
            return 'meta_tp_mr'
        if 'meta_kt' in trade.enter_tag and current_profit >= self.kt_rr_target:
            return 'meta_tp_kt'
        if 'meta_bs' in trade.enter_tag and current_profit >= self.bs_rr_target:
            return 'meta_tp_bs'
        if 'meta_wammie' in trade.enter_tag and current_profit >= self.wammies_rr_target:
            return 'meta_tp_wammie'
        
        return None

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time, entry_tag: str, side: str, **kwargs) -> bool:
        if not entry_tag:
            return True
        
        open_trades = Trade.get_trades_proxy(is_open=True)
        trend_count = sum(1 for t in open_trades if t.enter_tag and 'meta_trend' in t.enter_tag)
        mr_count = sum(1 for t in open_trades if t.enter_tag and 'meta_mr' in t.enter_tag)
        kt_count = sum(1 for t in open_trades if t.enter_tag and 'meta_kt' in t.enter_tag)
        bs_count = sum(1 for t in open_trades if t.enter_tag and 'meta_bs' in t.enter_tag)
        wammie_count = sum(1 for t in open_trades if t.enter_tag and 'meta_wammie' in t.enter_tag)
        
        if 'meta_trend' in entry_tag and trend_count >= 2:
            return False
        if 'meta_mr' in entry_tag and mr_count >= 3:
            return False
        if 'meta_kt' in entry_tag and kt_count >= self.kt_max_trades:
            return False
        if 'meta_bs' in entry_tag and bs_count >= self.bs_max_trades:
            return False
        if 'meta_wammie' in entry_tag and wammie_count >= self.wammies_max_trades:
            return False
        
        return True
