"""
OHLCV data fetcher for Taiwan stocks.
Uses yfinance (symbol + ".TW") for historical candles needed by technical indicators.
Falls back gracefully if data is unavailable.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# yfinance cache so we don't hammer the API every tick
_cache: dict[str, tuple[datetime, pd.DataFrame]] = {}
CACHE_TTL_MINUTES = 5


def _tw_ticker(symbol: str) -> str:
    """Convert bare Taiwan symbol (e.g. '2330') to yfinance format ('2330.TW')."""
    if symbol.endswith(".TW") or symbol.endswith(".TWO"):
        return symbol
    return f"{symbol}.TW"


def get_ohlcv(symbol: str, days: int = 60) -> Optional[pd.DataFrame]:
    """
    Fetch daily OHLCV for a Taiwan stock.

    Returns a DataFrame with columns: Open, High, Low, Close, Volume
    indexed by date (ascending). Returns None on failure.
    """
    ticker = _tw_ticker(symbol)
    now = datetime.now()

    if ticker in _cache:
        cached_time, cached_df = _cache[ticker]
        if (now - cached_time).seconds < CACHE_TTL_MINUTES * 60:
            return cached_df

    try:
        end = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        start = (now - timedelta(days=days + 10)).strftime("%Y-%m-%d")  # +10 buffer for holidays
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)

        if df.empty:
            logger.warning("No OHLCV data for %s", ticker)
            return None

        df = df.sort_index()
        df.index = pd.to_datetime(df.index)
        _cache[ticker] = (now, df)
        logger.debug("Fetched %d rows for %s", len(df), ticker)
        return df

    except Exception as e:
        logger.error("get_ohlcv(%s) failed: %s", symbol, e)
        return None


def get_latest_close(symbol: str) -> Optional[float]:
    """Return the most recent closing price."""
    df = get_ohlcv(symbol, days=5)
    if df is None or df.empty:
        return None
    close = df["Close"].iloc[-1]
    # Handle case where yfinance returns a Series (multi-ticker download)
    if hasattr(close, "iloc"):
        close = close.iloc[0]
    return float(close)


def get_close_series(symbol: str, days: int = 60) -> Optional[pd.Series]:
    """Return just the Close price Series."""
    df = get_ohlcv(symbol, days=days)
    if df is None or df.empty:
        return None
    col = df["Close"]
    if isinstance(col, pd.DataFrame):
        col = col.iloc[:, 0]
    return col.squeeze()


def invalidate_cache(symbol: Optional[str] = None):
    if symbol:
        _cache.pop(_tw_ticker(symbol), None)
    else:
        _cache.clear()
