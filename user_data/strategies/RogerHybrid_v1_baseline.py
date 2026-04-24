from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
import talib.abstract as ta
from pandas import DataFrame

class RogerHybrid_v1_baseline(IStrategy):
    """
    v1 BASELINE: RSI35/30, vol1.2, RR2.0, block age 50, no engulf
    """
    INTERFACE_VERSION = 3
    timeframe = '1h'
    stoploss = -0.02
    trailing_stop = False
    use_custom_stoploss = False

    rsi_entry = IntParameter(30, 45, default=35, space="buy", optimize=False)
    rsi_oversold = IntParameter(15, 30, default=30, space="buy", optimize=False)
    volume_mult = DecimalParameter(1.0, 3.0, default=1.2, space="buy", optimize=False)
    rr_ratio = DecimalParameter(1.5, 3.0, default=2.0, space="sell", optimize=False)
    block_age = IntParameter(10, 100, default=50, space="buy", optimize=False)

    minimal_roi = {"0": 1}
    startup_candle_count = 50

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_prev'] = dataframe['rsi'].shift(1)
        dataframe['volume_avg20'] = dataframe['volume'].rolling(20).mean()
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append(dataframe['rsi_prev'] < self.rsi_entry.value)
        conditions.append(dataframe['rsi'] >= self.rsi_entry.value)
        conditions.append(dataframe['rsi_prev'] < self.rsi_oversold.value)
        conditions.append(dataframe['volume'] > dataframe['volume_avg20'] * self.volume_mult.value)
        conditions.append(dataframe['close'] > dataframe['close'].shift(1) * 0.98)

        if conditions:
            dataframe.loc[all(conditions), 'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe['rsi'] > 70, 'sell'] = 1
        return dataframe
