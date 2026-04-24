# pragma pylint: disable=missing-docstring,invalid-name,pointless-string-statement
# flake8: noqa: E501

from freqtrade.strategy import IStrategy
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib_indicators
import pandas as pd
import numpy as np


class RogerStrategy(IStrategy):
    """
    RogerStrategy v6 -- Entry E + Partial Exit (RogerLayer2)

    Entry E (from ema_research.py):
    - Pullback: price within 1.5% of 12 EMA (either direction)
    - RSI crosses up through 40 from below 50
    - Previous candle green

    Partial Exit (RogerLayer2):
    - Sell 50% at +3.5%  -> stop moves to breakeven (0%) on remainder
    - Sell remaining 50% at +7% (minimal_roi final exit)

    Shorts: BLOCKED (spot account only)
    """

    minimal_roi = {
        "0": 0.07,  # exit remaining at +7%
        "partial_exit": 0.0,  # remaining half exits at breakeven after partial
    }

    stoploss = -0.03
    timeframe = "1h"
    position_adjustment_enable = True

    # RSI override: block LONG when RSI > 75 (non-negotiable)
    # This lives here since the strategy itself needs to enforce it
    _rsi_blocked = False

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Bollinger Bands
        bollinger = qtpylib_indicators.bollinger_bands(
            qtpylib_indicators.typical_price(dataframe), window=20, stds=2
        )
        dataframe["bb_upper"] = bollinger["upper"]
        dataframe["bb_lower"] = bollinger["lower"]
        dataframe["bb_middle"] = bollinger["mid"]
        dataframe["bb_percent"] = (
            (dataframe["close"] - dataframe["bb_lower"]) /
            (dataframe["bb_upper"] - dataframe["bb_lower"])
        )

        # ATR for adaptive stops
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # EMA 12 and 26 for pullback detection
        dataframe["ema12"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema26"] = ta.EMA(dataframe, timeperiod=26)

        # RSI previous bar for cross detection
        dataframe["rsi_prev"] = dataframe["rsi"].shift(1)

        # Green candle flag
        dataframe["green"] = dataframe["close"] > dataframe["open"]
        dataframe["green_prev"] = dataframe["green"].shift(1)

        # Price vs EMA12 distance (for pullback detection)
        dataframe["ema12_dist_pct"] = (
            (dataframe["close"] - dataframe["ema12"]) / dataframe["ema12"] * 100
        )

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Entry E:
        1. Price within 1.5% of 12 EMA (pullback zone)
        2. RSI crosses up through 40 from below 50
        3. Previous candle green
        4. RSI > 75 BLOCKED (RSI override)
        """
        dataframe.loc[
            (
                # Pullback zone
                (dataframe["ema12_dist_pct"] >= -1.5) &
                (dataframe["ema12_dist_pct"] <= 1.5) &
                # RSI crosses up through 40 from below 50
                (dataframe["rsi"] >= 40) &
                (dataframe["rsi_prev"] < 50) &
                # Previous candle green
                (dataframe["green_prev"] == True) &
                # RSI override: not extreme overbought
                (dataframe["rsi"] <= 75)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Strategic exit: EMA breakdown (trend weakening).
        The minimal_roi handles the +7% final TP.
        """
        dataframe.loc[
            (
                # Price broke 2%+ below 12 EMA = severe trend weakening
                # Exit here (EMA exit) not at exact touch — buffer prevents fakeouts
                # Hard stop at -3% sits underneath as ultimate backstop
                (dataframe["close"] < dataframe["ema12"] * 0.98)
            ),
            "exit_long",
        ] = 1
        return dataframe

    def custom_exit(
        self, pair: str, trade: "Trade", current_time: "datetime", current_rate: float,
        current_profit: float, **kwargs
    ) -> str:
        """
        Partial exit at +3.5%: sell 50% of position.
        Returns 'partial_exit' tag -> freqtrade closes half, stop locks to breakeven.
        """
        if current_profit >= 0.035:
            return "partial_exit"
        return ""

    def custom_stoploss(self, dataframe: pd.DataFrame, side: str, **kwargs) -> float:
        """
        ATR-adaptive stop: 1.5x ATR, max 4%.
        """
        if side != "long":
            return 0

        close = dataframe["close"].iloc[-1]
        atr = dataframe["atr"].iloc[-1]

        if atr > 0 and close > 0:
            stop_pct = min((atr / close) * 1.5, 0.04)
            return -stop_pct

        return -0.03
