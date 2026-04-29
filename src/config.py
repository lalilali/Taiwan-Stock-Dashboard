import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # --- Fubon credentials (loaded from .env) ---
    account_id: str = field(default_factory=lambda: os.getenv("FUBON_ID", ""))
    password: str = field(default_factory=lambda: os.getenv("FUBON_PASSWORD", ""))
    cert_path: str = field(default_factory=lambda: os.getenv("FUBON_CERT_PATH", ""))
    cert_password: str = field(default_factory=lambda: os.getenv("FUBON_CERT_PASSWORD", ""))

    # --- Trading mode ---
    paper_trading: bool = field(default_factory=lambda: os.getenv("PAPER_TRADING", "true").lower() == "true")

    # --- Watchlist (Taiwan stock symbols) ---
    watchlist: List[str] = field(default_factory=lambda: ["2330", "2317", "2454", "2881", "2382"])

    # --- Risk parameters ---
    max_position_pct: float = 0.10    # max 10% of portfolio per stock
    stop_loss_pct: float = 0.05       # 5% stop loss from entry price
    take_profit_pct: float = 0.10     # 10% take profit
    max_daily_loss_pct: float = 0.03  # halt trading if daily loss exceeds 3%
    min_order_quantity: int = 1000    # minimum lot size (1 lot = 1000 shares in TW)

    # --- MA Crossover strategy ---
    ma_short: int = 5
    ma_long: int = 20

    # --- RSI settings ---
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0

    # --- MACD settings ---
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # --- Bollinger Bands settings ---
    bb_period: int = 20
    bb_std: float = 2.0

    # --- Historical data ---
    history_days: int = 60            # days of OHLCV history to load for indicators

    # --- Scheduler ---
    check_interval_seconds: int = 60  # how often to run strategy during market hours
    market_open: str = "09:00"
    market_close: str = "13:30"
    timezone: str = "Asia/Taipei"


# Singleton
config = Config()
