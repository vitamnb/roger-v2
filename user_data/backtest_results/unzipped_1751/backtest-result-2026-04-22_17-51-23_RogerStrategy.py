# pragma pylint: disable=missing-docstring,invalid-name,pointless-string-statement
# flake8: noqa: E501

from freqtrade.strategy import IStrategy
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib_indicators
import pandas as pd
import numpy as np


class RogerStrategy(IStrategy):
    """
    RogerStrategy v5 -- Entry E (from ema_research.py, verified 2026-04-22)

    Entry E parameters (exact from ema_research.py):
    - Pullback: price within 1.5% of 12 EMA (either direction)
    - RSI crosses up through 40 from below 50
    - Previous candle green

    Exit: hard TP at 5%, ATR-based stop
    """

    minimal_roi = {
        "0": 0.05,  # TP 5%
    }

    stoploss = -0.03  # base stop (ATR overrides per-pair)

    timeframe = "1h"

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
        dataframe["ema12_dist_pct"] = (dataframe["close"] - dataframe["ema12"]) / dataframe["ema12"] * 100

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Entry E (from ema_research.py, verified 2026-04-22):
        1. Price within 1.5% of 12 EMA (pullback zone, either direction)
        2. RSI crosses up through 40 from below 50
        3. Previous candle green

        All three must be true.
        """
        dataframe.loc[
            (
                # Pullback zone: price within 1.5% of 12 EMA
                (dataframe["ema12_dist_pct"] >= -1.5) &
                (dataframe["ema12_dist_pct"] <= 1.5) &

                # RSI crosses up through 40 from below 50
                (dataframe["rsi"] >= 40) &
                (dataframe["rsi_prev"] < 50) &

                # Previous candle green
                (dataframe["green_prev"] == True)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Exit: RSI overbought + upper Bollinger OR price dropped below 12 EMA.
        ATR stop handles the hard stop; this is the strategic exit.
        """
        dataframe.loc[
            (
                # RSI overbought
                (dataframe["rsi"] > 65) &
                (dataframe["bb_percent"] > 0.80)
            ) |
            (
                # Price broke below 12 EMA = trend weakening
                (dataframe["close"] < dataframe["ema12"])
            ),
            "exit_long",
        ] = 1
        return dataframe

    def custom_stop_loss(self, dataframe: pd.DataFrame, side: str, **kwargs) -> float:
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

        return -0.03  # fallback 3%
