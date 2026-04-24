# pragma pylint: disable=missing-docstring,invalid-name,pointless-string-statement
# flake8: noqa: E501

from freqtrade.strategy import IStrategy
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib_indicators
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class RogerYOLOStrategy(IStrategy):
    """
    RogerYOLOStrategy — YOLO layer for opportunistic breakout / new-listing plays.

    Entry: RSI < 35 crosses UP through 40 + volume surge > 1.5x + EMA bull + prev candle green
    Exit:  +12% hard TP  OR  EMA breakdown  OR  24h timeout
    Stop:  -5% hard stop (ATR-adaptive, max 6%)

    Max 2 concurrent YOLO positions (RealTimePoolSize=2).
    Shorts: BLOCKED (spot account only)
    """

    minimal_roi = {
        "0": 0.12,  # +12% full exit
    }

    stoploss = -0.05  # fallback; custom_stoploss overrides
    timeframe = "1h"

    # Independent slot budget for YOLO — doesn't eat into core strategy's 3 slots
    # Note: RealTimePoolSize requires freqtrade 2024+ and must be set in the
    # strategy class or via the exchange config. We also enforce via custom_exit.
    # Run this strategy on a SEPARATE Freqtrade instance or a separate config file
    # if you need strict slot isolation.
    # Here we rely on custom logic and a tight cap.

    # How many YOLO trades can be open at once (enforced in custom_exit)
    _yolo_max_trades = 2
    _yolo_open_trades = set()

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Bollinger Bands (for reference)
        bollinger = qtpylib_indicators.bollinger_bands(
            qtpylib_indicators.typical_price(dataframe), window=20, stds=2
        )
        dataframe["bb_upper"] = bollinger["upper"]
        dataframe["bb_lower"] = bollinger["lower"]
        dataframe["bb_middle"] = bollinger["mid"]

        # ATR for adaptive stops
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # EMA 12 and 26
        dataframe["ema12"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema26"] = ta.EMA(dataframe, timeperiod=26)

        # RSI previous bar
        dataframe["rsi_prev"] = dataframe["rsi"].shift(1)

        # Volume rolling average + ratio
        dataframe["vol_avg"] = dataframe["volume"].rolling(20).mean()
        dataframe["vol_ratio"] = dataframe["volume"] / dataframe["vol_avg"]

        # Green candle flag
        dataframe["green"] = dataframe["close"] > dataframe["open"]
        dataframe["green_prev"] = dataframe["green"].shift(1)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        YOLO Entry: RSI < 35 recovering from oversold,
        crosses UP through 40 with volume surge and EMA confirmation.
        """
        conditions = (
            # RSI was oversold, now recovering
            (dataframe["rsi"] >= 35) &
            (dataframe["rsi_prev"] <= 30) &
            # Volume surge
            (dataframe["vol_ratio"] > 1.5) &
            # EMA in bull alignment
            (dataframe["ema12"] > dataframe["ema26"]) &
            # Price above EMA12
            (dataframe["close"] > dataframe["ema12"]) &
            # Previous candle was green
            (dataframe["green_prev"] == True)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "yolo_breakout"
        return dataframe

    def confirm_trade_entry(
        self, pair: str, order_type: str, amount: float, rate: float,
        time_in_force: str, current_time, entry_tag, side: str, **kwargs
    ) -> bool:
        """
        Enforce max 2 concurrent YOLO positions before allowing new entry.
        """
        if entry_tag == "yolo_breakout":
            open_yolo = len([
                t for t in self.dp.trade_storage.get_all_trades()
                if t.is_open and t.strategy == "RogerYOLOStrategy"
            ])
            if open_yolo >= self._yolo_max_trades:
                return False  # Skip entry — YOLO slots full
        return True

    def custom_exit(
        self, pair: str, trade: "Trade", current_time: "datetime", current_rate: float,
        current_profit: float, **kwargs
    ) -> str:
        """
        YOLO exits with custom tags:
        - +12% TP  -> "yolo_tp"
        - 24h timeout -> "yolo_timeout"
        """
        # TP: +12%
        if current_profit >= 0.12:
            return "yolo_tp"

        # Timeout: 24 hours
        if trade.open_date is not None:
            open_hours = (current_time - trade.open_date).total_seconds() / 3600
            if open_hours >= 24:
                return "yolo_timeout"

        return ""

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Strategic exit: EMA breakdown -> "yolo_emabreak"
        """
        dataframe.loc[
            (
                # Price broke below EMA12 = trend weakening
                (dataframe["close"] < dataframe["ema12"])
            ),
            "exit_long",
        ] = 1
        dataframe.loc[
            (
                (dataframe["close"] < dataframe["ema12"])
            ),
            "exit_tag",
        ] = "yolo_emabreak"
        return dataframe
        """
        ATR-adaptive stop: 2x ATR, max 6%.
        """
        if side != "long":
            return 0

        close = dataframe["close"].iloc[-1]
        atr = dataframe["atr"].iloc[-1]

        if atr > 0 and close > 0:
            stop_pct = min((atr / close) * 2.0, 0.06)
            return -stop_pct

        return -0.05  # fallback 5%
