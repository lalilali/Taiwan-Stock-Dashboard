"""
MA Crossover strategy.

BUY  when short MA crosses ABOVE long MA (golden cross).
SELL when short MA crosses BELOW long MA (death cross).
"""

import logging
from typing import Optional

import pandas as pd

from strategy.base import BaseStrategy, Signal, TradeSignal

logger = logging.getLogger(__name__)


class MACrossoverStrategy(BaseStrategy):
    name = "ma_crossover"

    def __init__(self, short: int = 5, long: int = 20):
        self.short = short
        self.long = long

    def generate_signal(self, symbol: str, close: pd.Series, ohlcv: Optional[pd.DataFrame] = None) -> TradeSignal:
        price = float(close.iloc[-1])

        if len(close) < self.long + 1:
            return TradeSignal(symbol=symbol, signal=Signal.HOLD, price=price,
                               reason=f"Not enough data (need {self.long + 1} bars)")

        ma_short = close.rolling(self.short).mean()
        ma_long = close.rolling(self.long).mean()

        prev_short = ma_short.iloc[-2]
        prev_long = ma_long.iloc[-2]
        curr_short = ma_short.iloc[-1]
        curr_long = ma_long.iloc[-1]

        # Golden cross: short crosses above long
        if prev_short <= prev_long and curr_short > curr_long:
            reason = f"Golden cross: MA{self.short}({curr_short:.2f}) > MA{self.long}({curr_long:.2f})"
            logger.info("[%s] BUY signal — %s", symbol, reason)
            return TradeSignal(symbol=symbol, signal=Signal.BUY, price=price, reason=reason)

        # Death cross: short crosses below long
        if prev_short >= prev_long and curr_short < curr_long:
            reason = f"Death cross: MA{self.short}({curr_short:.2f}) < MA{self.long}({curr_long:.2f})"
            logger.info("[%s] SELL signal — %s", symbol, reason)
            return TradeSignal(symbol=symbol, signal=Signal.SELL, price=price, reason=reason)

        gap_pct = (curr_short - curr_long) / curr_long * 100
        return TradeSignal(symbol=symbol, signal=Signal.HOLD, price=price,
                           reason=f"No crossover (MA gap {gap_pct:+.2f}%)")
