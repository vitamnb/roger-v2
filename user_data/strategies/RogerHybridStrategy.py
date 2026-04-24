"""
Roger Hybrid Strategy v1
Combines Entry B (RSI cross) with order block context and volume confirmation.
"""

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class RogerHybridStrategy(IStrategy):
    """
    Hybrid strategy:
    - Primary signal: RSI crosses up through 35 from below 30
    - Context: Price near fresh 4h order block (demand zone)
    - Confirmation: Volume > 1.2x 20-period average
    - Daily bias: bullish (higher timeframe alignment)
    """

    # Strategy config
    timeframe = '1h'
    stoploss = -0.02
    trailing_stop = False
    use_custom_stoploss = True
    can_short = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Hyperopt parameters
    rsi_entry = 35
    rsi_oversold = 30
    volume_mult = 1.2
    order_block_lookback = 20
    order_block_atr_mult = 2.0
    rr_target = 0.03  # 3% take profit

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Calculate all indicators."""
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_prev'] = dataframe['rsi'].shift(1)

        # ATR for order block detection
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # Volume
        dataframe['volume_avg20'] = dataframe['volume'].rolling(20).mean()

        # Order block detection
        dataframe = self._detect_order_blocks(dataframe)

        return dataframe

    def _detect_order_blocks(self, df: DataFrame) -> DataFrame:
        """Detect bullish order blocks in recent history."""
        df['order_block_zone'] = False
        df['order_block_low'] = np.nan
        df['order_block_high'] = np.nan

        for i in range(self.order_block_lookback, len(df)):
            # Look back for a bearish candle followed by big up move
            if i < self.order_block_lookback + 1:
                continue

            block_candle = df.iloc[i - self.order_block_lookback]

            # Bearish candle
            if block_candle['close'] >= block_candle['open']:
                continue

            # Check if followed by significant up move
            future_slice = df.iloc[i - self.order_block_lookback + 1:i + 1]
            if len(future_slice) < 2:
                continue

            max_move = (future_slice['high'].max() - block_candle['close']) / block_candle['close']
            atr_threshold = block_candle['atr'] * self.order_block_atr_mult / block_candle['close']

            if max_move > atr_threshold:
                # Valid order block
                df.loc[df.index[i], 'order_block_zone'] = True
                df.loc[df.index[i], 'order_block_low'] = block_candle['low']
                df.loc[df.index[i], 'order_block_high'] = block_candle['high']

        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Entry signal logic."""
        dataframe['enter_long'] = 0
        dataframe['enter_tag'] = ''

        for i in range(1, len(dataframe)):
            # Signal 1: RSI cross up through 35 from below 30
            rsi_cross = (
                dataframe['rsi_prev'].iloc[i] < self.rsi_entry and
                dataframe['rsi'].iloc[i] >= self.rsi_entry and
                dataframe['rsi_prev'].iloc[i] < self.rsi_oversold
            )

            if not rsi_cross:
                continue

            # Signal 2: Near fresh order block
            ob_zone = False
            ob_low = None
            ob_high = None

            # Look back for recent order blocks
            for j in range(max(0, i - self.order_block_lookback), i):
                if dataframe['order_block_zone'].iloc[j]:
                    block_low = dataframe['order_block_low'].iloc[j]
                    block_high = dataframe['order_block_high'].iloc[j]

                    if pd.notna(block_low) and pd.notna(block_high):
                        current_price = dataframe['close'].iloc[i]
                        # Within 2% of block zone
                        if block_low * 0.98 <= current_price <= block_high * 1.02:
                            ob_zone = True
                            ob_low = block_low
                            ob_high = block_high
                            break

            # Signal 3: Volume spike
            vol_spike = dataframe['volume'].iloc[i] > dataframe['volume_avg20'].iloc[i] * self.volume_mult

            if rsi_cross and ob_zone and vol_spike:
                dataframe.loc[dataframe.index[i], 'enter_long'] = 1
                dataframe.loc[dataframe.index[i], 'enter_tag'] = f'rsi_ob_vol|ob_low={ob_low:.4f}'

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Exit signal logic."""
        dataframe['exit_long'] = 0

        for i in range(1, len(dataframe)):
            # Exit on RSI overbought (>70)
            if dataframe['rsi'].iloc[i] > 70:
                dataframe.loc[dataframe.index[i], 'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: 'datetime',
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> float:
        """Dynamic stop based on order block low."""
        # Extract order block low from enter tag
        if trade.enter_tag and 'ob_low=' in trade.enter_tag:
            try:
                ob_low_str = trade.enter_tag.split('ob_low=')[1].split('|')[0]
                ob_low = float(ob_low_str)
                # Stop just below order block low
                stop_pct = (current_rate - ob_low * 0.998) / current_rate
                return -max(stop_pct, 0.005)  # Minimum 0.5% stop
            except (ValueError, IndexError):
                pass

        return self.stoploss

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime',
                    current_rate: float, current_profit: float, **kwargs):
        """Custom exit for take profit."""
        # 3% take profit
        if current_profit >= self.rr_target:
            return 'tp_3pct'

        return None
