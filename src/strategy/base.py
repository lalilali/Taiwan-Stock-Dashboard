"""Base strategy interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradeSignal:
    symbol: str
    signal: Signal
    price: float
    reason: str
    confidence: float = 1.0  # 0.0–1.0, for future weighting


class BaseStrategy(ABC):
    """All strategies implement generate_signal()."""

    name: str = "base"

    @abstractmethod
    def generate_signal(self, symbol: str, close: pd.Series, ohlcv: Optional[pd.DataFrame] = None) -> TradeSignal:
        """
        Given a symbol and its price history, return a TradeSignal.
        close  — pd.Series of closing prices, most-recent last
        ohlcv  — full OHLCV DataFrame (optional, for volume-aware strategies)
        """
        ...
