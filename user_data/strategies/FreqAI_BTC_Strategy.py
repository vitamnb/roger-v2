"""
FreqAI Strategy for BTC/USDT
ML-based strategy using XGBoostClassifier to predict next candle direction.
"""

import logging
from functools import reduce
from typing import Optional

from pandas import DataFrame

from freqtrade.strategy import IStrategy, CategoricalParameter, DecimalParameter, IntParameter
from freqtrade.strategy import merge_informative_pair
from freqtrade.persistence import Trade

import talib.abstract as ta

logger = logging.getLogger(__name__)


class FreqAI_BTC_Strategy(IStrategy):
    """
    FreqAI-enabled strategy for BTC/USDT on KuCoin.
    Uses XGBoostClassifier to predict next candle direction.
    """

    minimal_roi = {"0": 0.05}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.03
    timeframe = "1h"
    can_short = False
    use_exit_signal = True
    process_only_new_candles = True
    startup_candle_count = 40

    # FreqAI-specific parameters
    feature_parameters = [
        "feature_1h_rsi_14",
        "feature_1h_macd_line",
        "feature_1h_macd_signal",
        "feature_1h_macd_hist",
        "feature_1h_bb_upper",
        "feature_1h_bb_lower",
        "feature_1h_bb_middle",
        "feature_1h_volume_sma_20",
        "feature_4h_rsi_14",
        "feature_4h_macd_line",
        "feature_4h_macd_signal",
        "feature_4h_macd_hist",
        "feature_4h_bb_upper",
        "feature_4h_bb_lower",
        "feature_4h_bb_middle",
        "feature_4h_volume_sma_20",
    ]

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Standard feature engineering for FreqAI.
        This method is called during training and prediction.
        """
        dataframe = dataframe.copy()

        # RSI
        for period in [10, 14, 20]:
            dataframe[f"rsi_{period}"] = ta.RSI(dataframe, timeperiod=period)

        # MACD
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd_line"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]

        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe["bb_upper"] = bollinger["upperband"]
        dataframe["bb_lower"] = bollinger["lowerband"]
        dataframe["bb_middle"] = bollinger["middleband"]
        dataframe["bb_percent"] = (dataframe["close"] - dataframe["bb_lower"]) / (dataframe["bb_upper"] - dataframe["bb_lower"])

        # Moving Averages
        dataframe["ema_10"] = ta.EMA(dataframe, timeperiod=10)
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["sma_50"] = ta.SMA(dataframe, timeperiod=50)

        # Volume features
        dataframe["volume_sma_20"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_sma_20"]

        # Candle features
        dataframe["body"] = (dataframe["close"] - dataframe["open"]) / dataframe["open"]
        dataframe["upper_wick"] = (dataframe["high"] - dataframe["close"].clip(lower=dataframe["open"])) / dataframe["open"]
        dataframe["lower_wick"] = (dataframe["open"].clip(upper=dataframe["close"]) - dataframe["low"]) / dataframe["open"]
        dataframe["range"] = (dataframe["high"] - dataframe["low"]) / dataframe["low"]

        # Rate of change
        dataframe["roc_5"] = ta.ROC(dataframe, timeperiod=5)
        dataframe["roc_10"] = ta.ROC(dataframe, timeperiod=10)

        # ATR
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_percent"] = dataframe["atr"] / dataframe["close"] * 100

        return dataframe

    def feature_engineering_expand_all(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Feature engineering for all informative pairs (called during training).
        """
        dataframe = self.feature_engineering_standard(dataframe, metadata, **kwargs)
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Basic feature engineering (called during prediction).
        """
        dataframe = self.feature_engineering_standard(dataframe, metadata, **kwargs)
        return dataframe

    def feature_engineering_rename(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Rename features for FreqAI.
        """
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Define the target variable for FreqAI.
        Target: Direction of next candle (1 for up, 0 for down/sideways).
        """
        # Target: next candle direction
        dataframe["&target"] = (dataframe["close"].shift(-1) > dataframe["close"]).astype(int)

        # Also create a shifted target for validation
        dataframe["&target_label"] = dataframe["&target"]

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators.
        FreqAI will add ML predictions automatically.
        """
        dataframe = dataframe.copy()

        # Add standard indicators for reference
        dataframe["rsi_14"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # Merge informative timeframe data if available
        if self.dp:
            informative = self.dp.get_pair_dataframe(metadata["pair"], "4h")
            if not informative.empty:
                informative["rsi_14"] = ta.RSI(informative, timeperiod=14)
                informative["ema_20"] = ta.EMA(informative, timeperiod=20)
                dataframe = merge_informative_pair(dataframe, informative, self.timeframe, "4h", ffill=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define entry conditions.
        Uses FreqAI prediction + technical confirmation.
        """
        dataframe["enter_long"] = 0

        # Check if FreqAI prediction exists
        if "&target" in dataframe.columns or "target" in dataframe.columns:
            # Entry condition: FreqAI predicts UP and RSI is oversold
            conditions = [
                # FreqAI predicts next candle goes up
                dataframe.get("&target", dataframe.get("target", 0)) > 0.5,
                # RSI confirmation - oversold
                dataframe["rsi_14"] < 40,
                # Price above EMA20 (trend filter)
                dataframe["close"] > dataframe["ema_20"],
                # Sufficient ATR for movement
                dataframe["atr"] > 0,
            ]
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "enter_long"] = 1
        else:
            # Fallback: pure technical entry when FreqAI not yet active
            conditions = [
                dataframe["rsi_14"] < 35,
                dataframe["close"] > dataframe["ema_20"],
            ]
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "enter_long"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define exit conditions.
        """
        dataframe["exit_long"] = 0

        # Exit condition: RSI overbought
        dataframe.loc[dataframe["rsi_14"] > 70, "exit_long"] = 1

        return dataframe

    def custom_stake_amount(self, pair: str, current_time, current_rate: float,
                         proposed_stake: float, min_stake: Optional[float], max_stake: float,
                         leverage: float, entry_tag: Optional[str], side: str,
                         **kwargs) -> float:
        """
        Custom stake size based on confidence.
        """
        # Return standard stake for now
        return proposed_stake
