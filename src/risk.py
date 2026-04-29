"""
Risk management: position sizing, stop-loss checks, daily loss circuit breaker.
"""

import logging
from datetime import date
from typing import Optional

from portfolio.tracker import get_all_trades, get_open_positions

logger = logging.getLogger(__name__)

# Taiwan lot size: 1 lot = 1000 shares
TAIWAN_LOT = 1000


class RiskManager:
    def __init__(self, config):
        self.config = config
        self._daily_pnl: dict[str, float] = {}   # date_str -> realized pnl
        self._halted = False

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def calc_quantity(self, symbol: str, price: float, portfolio_value: float) -> int:
        """
        Return how many shares (rounded to lot size) to buy.
        Limits position to max_position_pct of portfolio.
        Returns 0 if position sizing is not possible.
        """
        if price <= 0 or portfolio_value <= 0:
            return 0

        max_value = portfolio_value * self.config.max_position_pct

        # Check if already holding this symbol — reduce allowance
        positions = get_open_positions()
        for pos in positions:
            if pos["symbol"] == symbol:
                held_value = pos["quantity"] * pos["avg_cost"]
                max_value = max(0, max_value - held_value)
                break

        raw_shares = max_value / price
        lots = int(raw_shares // TAIWAN_LOT)
        quantity = lots * TAIWAN_LOT

        if quantity < self.config.min_order_quantity:
            logger.warning("[%s] Position size %d < min %d — skipping", symbol, quantity, self.config.min_order_quantity)
            return 0

        logger.debug("[%s] Sized %d shares (%.0f TWD budget)", symbol, quantity, max_value)
        return quantity

    # ------------------------------------------------------------------
    # Stop-loss / take-profit checks for open positions
    # ------------------------------------------------------------------

    def should_exit(self, symbol: str, current_price: float) -> Optional[str]:
        """
        Returns 'stop_loss' or 'take_profit' if exit condition met, else None.
        Caller should emit a SELL signal.
        """
        positions = get_open_positions()
        for pos in positions:
            if pos["symbol"] != symbol:
                continue
            avg_cost = pos["avg_cost"]
            if avg_cost <= 0:
                continue
            change_pct = (current_price - avg_cost) / avg_cost

            if change_pct <= -self.config.stop_loss_pct:
                logger.warning(
                    "[%s] Stop-loss triggered: cost=%.2f current=%.2f (%.1f%%)",
                    symbol, avg_cost, current_price, change_pct * 100,
                )
                return "stop_loss"

            if change_pct >= self.config.take_profit_pct:
                logger.info(
                    "[%s] Take-profit triggered: cost=%.2f current=%.2f (%.1f%%)",
                    symbol, avg_cost, current_price, change_pct * 100,
                )
                return "take_profit"
        return None

    # ------------------------------------------------------------------
    # Daily loss circuit breaker
    # ------------------------------------------------------------------

    def update_daily_pnl(self, pnl: float):
        today = str(date.today())
        self._daily_pnl[today] = self._daily_pnl.get(today, 0.0) + pnl

    def is_halted(self, portfolio_value: float) -> bool:
        """Returns True if daily loss exceeds the configured threshold."""
        if self._halted:
            return True
        today = str(date.today())
        daily_loss = self._daily_pnl.get(today, 0.0)
        if daily_loss < 0 and portfolio_value > 0:
            loss_pct = abs(daily_loss) / portfolio_value
            if loss_pct >= self.config.max_daily_loss_pct:
                logger.critical(
                    "Daily loss circuit breaker: %.1f%% loss (limit %.1f%%) — HALTED",
                    loss_pct * 100, self.config.max_daily_loss_pct * 100,
                )
                self._halted = True
                return True
        return False

    def reset_halt(self):
        """Call at start of new trading day."""
        self._halted = False
        logger.info("Risk halt reset for new trading day")
