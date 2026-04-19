# pragma pylint: disable=missing-docstring,invalid-name,pointless-string-statement
# flake8: noqa: E501

from freqtrade.strategy import IStrategy
from freqtrade.exchange import timeframe_to_minutes
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib_indicators
import pandas as pd
import numpy as np


class RogerStrategy(IStrategy):
    """
    Roger's starting strategy — simple RSI + Bollinger Bands.
    Designed to verify KuCoin connectivity, then iterate from there.
    """

    # 3.5:1 R:R — stop = 2% risk, target = 7% reward
    minimal_roi = {
        "0": 0.07,
        "60": 0.08,
        "180": 0.10,
    }
    stoploss = -0.02

    # 1h candles for swing-style trading
    timeframe = "1h"

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
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
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                (dataframe["rsi"] < 35) &
                (dataframe["bb_percent"] < 0.20)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                (dataframe["rsi"] > 70) &
                (dataframe["bb_percent"] > 0.80)
            ),
            "exit_long",
        ] = 1
        return dataframe