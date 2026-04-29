"""
Taiwan Auto Trader — main entry point.

Flow (every `check_interval_seconds` during market hours):
  1. For each symbol in watchlist:
     a. Fetch OHLCV history
     b. Run strategy → TradeSignal
     c. Check stop-loss / take-profit on open positions
     d. Risk manager approves position size
     e. Place order via Fubon (or paper trade)
     f. Record trade in SQLite
  2. Print portfolio summary at market close
"""

import logging
import signal
import sys
import time
from datetime import datetime

import pytz
import schedule

from broker.fubon_client import FubonClient, Side
from config import config
from data.market_data import get_close_series, get_latest_close
from portfolio.tracker import init_db, print_summary, record_trade
from risk import RiskManager
from strategy.base import Signal
from strategy.ma_crossover import MACrossoverStrategy
from strategy.technical import BollingerBandsStrategy, CombinedStrategy, MACDStrategy, RSIStrategy

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("trader.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_shutdown = False
broker = FubonClient(config, paper_trading=config.paper_trading)
risk = RiskManager(config)

# Build combined strategy: MA crossover + RSI + MACD + Bollinger Bands
# Requires at least 2 of 4 to agree before acting
strategy = CombinedStrategy(
    strategies=[
        MACrossoverStrategy(short=config.ma_short, long=config.ma_long),
        RSIStrategy(period=config.rsi_period, oversold=config.rsi_oversold, overbought=config.rsi_overbought),
        MACDStrategy(fast=config.macd_fast, slow=config.macd_slow, signal=config.macd_signal),
        BollingerBandsStrategy(period=config.bb_period, std_dev=config.bb_std),
    ],
    min_agree=2,
)

# ---------------------------------------------------------------------------
# Market hours check (Asia/Taipei)
# ---------------------------------------------------------------------------

_tz = pytz.timezone(config.timezone)


def _is_market_open() -> bool:
    now = datetime.now(_tz)
    # Taiwan market: Mon–Fri, 09:00–13:30
    if now.weekday() >= 5:
        return False
    open_h, open_m = map(int, config.market_open.split(":"))
    close_h, close_m = map(int, config.market_close.split(":"))
    open_time = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    close_time = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
    return open_time <= now <= close_time


# ---------------------------------------------------------------------------
# Core trading tick
# ---------------------------------------------------------------------------

def _process_symbol(symbol: str, portfolio_value: float):
    close = get_close_series(symbol, days=config.history_days)
    if close is None or len(close) < 2:
        logger.warning("[%s] Insufficient price data — skipping", symbol)
        return

    current_price = get_latest_close(symbol) or float(close.iloc[-1])

    # --- Stop-loss / take-profit check on existing position ---
    exit_reason = risk.should_exit(symbol, current_price)
    if exit_reason:
        qty = _get_held_quantity(symbol)
        if qty > 0:
            _execute_trade(symbol, Side.SELL, current_price, qty,
                           reason=f"Risk exit: {exit_reason}", portfolio_value=portfolio_value)
        return

    # --- Strategy signal ---
    trade_signal = strategy.generate_signal(symbol, close)

    if trade_signal.signal == Signal.BUY:
        qty = risk.calc_quantity(symbol, current_price, portfolio_value)
        if qty > 0:
            _execute_trade(symbol, Side.BUY, current_price, qty,
                           reason=trade_signal.reason, portfolio_value=portfolio_value)

    elif trade_signal.signal == Signal.SELL:
        qty = _get_held_quantity(symbol)
        if qty > 0:
            _execute_trade(symbol, Side.SELL, current_price, qty,
                           reason=trade_signal.reason, portfolio_value=portfolio_value)
        else:
            logger.debug("[%s] SELL signal but no position held", symbol)

    else:
        logger.debug("[%s] HOLD — %s", symbol, trade_signal.reason)


def _execute_trade(symbol: str, side: Side, price: float, quantity: int,
                   reason: str, portfolio_value: float):
    result = broker.place_order(symbol, side, price, quantity)
    if result.success:
        pnl = record_trade(
            symbol=symbol,
            side=side.value.upper(),
            price=price,
            quantity=quantity,
            order_id=result.order_id,
            strategy=strategy.name,
            reason=reason,
            is_paper=config.paper_trading,
        )
        if pnl is not None:
            risk.update_daily_pnl(pnl)
    else:
        logger.error("[%s] Order failed: %s", symbol, result.message)


def _get_held_quantity(symbol: str) -> int:
    from portfolio.tracker import get_open_positions
    for pos in get_open_positions():
        if pos["symbol"] == symbol:
            return pos["quantity"]
    return 0


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------

def trading_tick():
    global _shutdown
    if _shutdown:
        return

    if not _is_market_open():
        logger.debug("Market closed — skipping tick")
        return

    logger.info("--- Trading tick: %s ---", datetime.now(_tz).strftime("%H:%M:%S"))

    portfolio_value = broker.get_account_value()
    if portfolio_value == 0 and not config.paper_trading:
        logger.warning("Could not retrieve portfolio value — using default 500,000 TWD")
        portfolio_value = 500_000  # safe default if API call fails

    if portfolio_value == 0 and config.paper_trading:
        portfolio_value = 1_000_000  # 1M TWD virtual capital in paper mode

    if risk.is_halted(portfolio_value):
        logger.warning("Risk circuit breaker active — no new orders this session")
        return

    for symbol in config.watchlist:
        try:
            _process_symbol(symbol, portfolio_value)
        except Exception as e:
            logger.error("[%s] Unexpected error: %s", symbol, e, exc_info=True)


def end_of_day():
    logger.info("=== End of day summary ===")
    print_summary()
    risk.reset_halt()


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

def _handle_signal(sig, frame):
    global _shutdown
    logger.info("Shutdown signal received — cleaning up...")
    _shutdown = True
    broker.disconnect()
    print_summary()
    sys.exit(0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("Starting Taiwan Auto Trader")
    logger.info("Paper trading: %s", config.paper_trading)
    logger.info("Watchlist: %s", config.watchlist)
    logger.info("Strategy: %s (combined — MA/RSI/MACD/BB)", strategy.name)

    init_db()

    if not broker.connect():
        logger.error("Failed to connect to broker — aborting")
        sys.exit(1)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Schedule the trading tick every N seconds
    schedule.every(config.check_interval_seconds).seconds.do(trading_tick)
    # End-of-day summary at 13:35 Taiwan time (just after market close)
    schedule.every().day.at("13:35").do(end_of_day)

    logger.info("Scheduler started — checking every %ds", config.check_interval_seconds)

    # Run once immediately if market is open
    if _is_market_open():
        trading_tick()

    while not _shutdown:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
