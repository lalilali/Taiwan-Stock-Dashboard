"""
Technical indicator strategies: RSI, MACD, Bollinger Bands.
Each returns a TradeSignal independently; main.py combines them via voting.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from strategy.base import BaseStrategy, Signal, TradeSignal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Indicator helpers (pure pandas/numpy — no extra dependencies)
# ---------------------------------------------------------------------------

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0):
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


# ---------------------------------------------------------------------------
# RSI Strategy
# ---------------------------------------------------------------------------

class RSIStrategy(BaseStrategy):
    name = "rsi"

    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signal(self, symbol: str, close: pd.Series, ohlcv: Optional[pd.DataFrame] = None) -> TradeSignal:
        price = float(close.iloc[-1])

        if len(close) < self.period + 1:
            return TradeSignal(symbol=symbol, signal=Signal.HOLD, price=price,
                               reason=f"Not enough data (need {self.period + 1} bars)")

        rsi = _rsi(close, self.period)
        curr = float(rsi.iloc[-1])
        prev = float(rsi.iloc[-2])

        # RSI crosses back above oversold → buy
        if prev <= self.oversold and curr > self.oversold:
            reason = f"RSI recovery from oversold: {prev:.1f} → {curr:.1f}"
            logger.info("[%s] BUY signal — %s", symbol, reason)
            return TradeSignal(symbol=symbol, signal=Signal.BUY, price=price, reason=reason,
                               confidence=min(1.0, (self.oversold - prev) / self.oversold))

        # RSI crosses back below overbought → sell
        if prev >= self.overbought and curr < self.overbought:
            reason = f"RSI pullback from overbought: {prev:.1f} → {curr:.1f}"
            logger.info("[%s] SELL signal — %s", symbol, reason)
            return TradeSignal(symbol=symbol, signal=Signal.SELL, price=price, reason=reason,
                               confidence=min(1.0, (prev - self.overbought) / (100 - self.overbought)))

        return TradeSignal(symbol=symbol, signal=Signal.HOLD, price=price,
                           reason=f"RSI neutral at {curr:.1f}")


# ---------------------------------------------------------------------------
# MACD Strategy
# ---------------------------------------------------------------------------

class MACDStrategy(BaseStrategy):
    name = "macd"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def generate_signal(self, symbol: str, close: pd.Series, ohlcv: Optional[pd.DataFrame] = None) -> TradeSignal:
        price = float(close.iloc[-1])
        min_bars = self.slow + self.signal + 5

        if len(close) < min_bars:
            return TradeSignal(symbol=symbol, signal=Signal.HOLD, price=price,
                               reason=f"Not enough data (need {min_bars} bars)")

        macd_line, signal_line, hist = _macd(close, self.fast, self.slow, self.signal)

        prev_hist = float(hist.iloc[-2])
        curr_hist = float(hist.iloc[-1])
        curr_macd = float(macd_line.iloc[-1])
        curr_sig = float(signal_line.iloc[-1])

        # MACD crosses above signal line (histogram flips positive)
        if prev_hist <= 0 and curr_hist > 0:
            reason = f"MACD bullish crossover: MACD={curr_macd:.4f} > Signal={curr_sig:.4f}"
            logger.info("[%s] BUY signal — %s", symbol, reason)
            return TradeSignal(symbol=symbol, signal=Signal.BUY, price=price, reason=reason)

        # MACD crosses below signal line (histogram flips negative)
        if prev_hist >= 0 and curr_hist < 0:
            reason = f"MACD bearish crossover: MACD={curr_macd:.4f} < Signal={curr_sig:.4f}"
            logger.info("[%s] SELL signal — %s", symbol, reason)
            return TradeSignal(symbol=symbol, signal=Signal.SELL, price=price, reason=reason)

        return TradeSignal(symbol=symbol, signal=Signal.HOLD, price=price,
                           reason=f"MACD histogram {curr_hist:+.4f}")


# ---------------------------------------------------------------------------
# Bollinger Bands Strategy
# ---------------------------------------------------------------------------

class BollingerBandsStrategy(BaseStrategy):
    name = "bollinger"

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev

    def generate_signal(self, symbol: str, close: pd.Series, ohlcv: Optional[pd.DataFrame] = None) -> TradeSignal:
        price = float(close.iloc[-1])

        if len(close) < self.period + 1:
            return TradeSignal(symbol=symbol, signal=Signal.HOLD, price=price,
                               reason=f"Not enough data (need {self.period + 1} bars)")

        upper, mid, lower = _bollinger(close, self.period, self.std_dev)

        curr_upper = float(upper.iloc[-1])
        curr_lower = float(lower.iloc[-1])
        curr_mid = float(mid.iloc[-1])
        prev_price = float(close.iloc[-2])

        # Price bounces off lower band (was below, now above) → buy
        if prev_price <= float(lower.iloc[-2]) and price > curr_lower:
            pct_b = (price - curr_lower) / (curr_upper - curr_lower) if curr_upper != curr_lower else 0.5
            reason = f"BB lower bounce: price={price:.2f}, lower={curr_lower:.2f}, %B={pct_b:.2f}"
            logger.info("[%s] BUY signal — %s", symbol, reason)
            return TradeSignal(symbol=symbol, signal=Signal.BUY, price=price, reason=reason,
                               confidence=1.0 - pct_b)

        # Price breaks through upper band → sell / take profit
        if prev_price <= float(upper.iloc[-2]) and price > curr_upper:
            pct_b = (price - curr_lower) / (curr_upper - curr_lower) if curr_upper != curr_lower else 0.5
            reason = f"BB upper breakout: price={price:.2f}, upper={curr_upper:.2f}, %B={pct_b:.2f}"
            logger.info("[%s] SELL signal — %s", symbol, reason)
            return TradeSignal(symbol=symbol, signal=Signal.SELL, price=price, reason=reason,
                               confidence=pct_b - 1.0)

        pct_b = (price - curr_lower) / (curr_upper - curr_lower) if curr_upper != curr_lower else 0.5
        return TradeSignal(symbol=symbol, signal=Signal.HOLD, price=price,
                           reason=f"BB neutral: price={price:.2f}, mid={curr_mid:.2f}, %B={pct_b:.2f}")


# ---------------------------------------------------------------------------
# Combined voting strategy
# ---------------------------------------------------------------------------

class CombinedStrategy(BaseStrategy):
    """
    Runs multiple strategies and returns BUY/SELL only when a majority agree.
    Requires at least `min_agree` strategies to vote the same way.
    """
    name = "combined"

    def __init__(self, strategies: list, min_agree: int = 2):
        self.strategies = strategies
        self.min_agree = min_agree

    def generate_signal(self, symbol: str, close: pd.Series, ohlcv: Optional[pd.DataFrame] = None) -> TradeSignal:
        price = float(close.iloc[-1])
        votes = {Signal.BUY: [], Signal.SELL: []}
        all_reasons = []

        for strat in self.strategies:
            sig = strat.generate_signal(symbol, close, ohlcv)
            all_reasons.append(f"[{strat.name}] {sig.signal.value}: {sig.reason}")
            if sig.signal in (Signal.BUY, Signal.SELL):
                votes[sig.signal].append(sig)

        for direction in (Signal.BUY, Signal.SELL):
            if len(votes[direction]) >= self.min_agree:
                avg_conf = sum(s.confidence for s in votes[direction]) / len(votes[direction])
                reason = f"{len(votes[direction])}/{len(self.strategies)} strategies agree | " + " | ".join(all_reasons)
                return TradeSignal(symbol=symbol, signal=direction, price=price,
                                   reason=reason, confidence=avg_conf)

        return TradeSignal(symbol=symbol, signal=Signal.HOLD, price=price,
                           reason="No consensus | " + " | ".join(all_reasons))
