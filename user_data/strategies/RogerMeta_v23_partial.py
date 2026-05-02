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
