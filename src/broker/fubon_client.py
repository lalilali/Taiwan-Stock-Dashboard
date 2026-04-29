"""
Fubon Neo SDK wrapper.
Handles login, order placement, account queries, and real-time quotes.
All order calls are no-ops in paper trading mode.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str]
    symbol: str
    side: Side
    price: float
    quantity: int
    message: str = ""


@dataclass
class Position:
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.avg_cost) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.avg_cost == 0:
            return 0.0
        return (self.current_price - self.avg_cost) / self.avg_cost


class FubonClient:
    def __init__(self, config, paper_trading: bool = True):
        self.config = config
        self.paper_trading = paper_trading
        self._sdk = None
        self._account = None
        self._connected = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        if self.paper_trading:
            logger.info("[PAPER] Fubon client connected (paper trading mode)")
            self._connected = True
            return True

        try:
            from fubon_neo.sdk import FubonSDK
            self._sdk = FubonSDK()
            res = self._sdk.login(
                self.config.account_id,
                self.config.password,
                self.config.cert_path,
                self.config.cert_password,
            )
            if res.is_success:
                self._account = res.data[0]
                self._connected = True
                logger.info("Fubon SDK login successful: %s", self._account)
                return True
            else:
                logger.error("Fubon login failed: %s", res)
                return False
        except Exception as e:
            logger.error("Fubon connect error: %s", e)
            return False

    def disconnect(self):
        if self._sdk and not self.paper_trading:
            try:
                self._sdk.logout()
            except Exception as e:
                logger.warning("Logout error: %s", e)
        self._connected = False
        logger.info("Fubon client disconnected")

    # ------------------------------------------------------------------
    # Market data (snapshot / current price)
    # ------------------------------------------------------------------

    def get_price(self, symbol: str) -> Optional[float]:
        """Return the latest trade price for a symbol."""
        if self.paper_trading or not self._sdk:
            return None  # caller falls back to yfinance

        try:
            rest = self._sdk.marketdata.rest_client.stock
            res = rest.snapshot.quotes(market="TSE")
            if res and res.data:
                for item in res.data:
                    if item.get("symbol") == symbol:
                        return float(item.get("closePrice") or item.get("lastPrice", 0))
        except Exception as e:
            logger.warning("get_price(%s) error: %s", symbol, e)
        return None

    # ------------------------------------------------------------------
    # Order execution
    # ------------------------------------------------------------------

    def place_order(self, symbol: str, side: Side, price: float, quantity: int) -> OrderResult:
        tag = "[PAPER]" if self.paper_trading else "[LIVE]"
        logger.info("%s %s %s @ %.2f x %d", tag, side.value.upper(), symbol, price, quantity)

        if self.paper_trading:
            return OrderResult(
                success=True,
                order_id=f"PAPER-{symbol}-{side.value}",
                symbol=symbol,
                side=side,
                price=price,
                quantity=quantity,
                message="Paper order filled",
            )

        try:
            from fubon_neo.sdk import Order
            from fubon_neo.constant import TimeInForce, OrderType, PriceType, MarketType, BSAction

            bs = BSAction.Buy if side == Side.BUY else BSAction.Sell
            order = Order(
                buy_sell=bs,
                symbol=symbol,
                price=str(price),
                quantity=quantity,
                market_type=MarketType.Common,
                price_type=PriceType.Limit,
                time_in_force=TimeInForce.ROD,
                order_type=OrderType.Stock,
                user_def="AutoTrader",
            )
            res = self._sdk.stock.place_order(self._account, order)
            if res.is_success:
                return OrderResult(
                    success=True,
                    order_id=str(res.data.seq_no if hasattr(res.data, "seq_no") else ""),
                    symbol=symbol,
                    side=side,
                    price=price,
                    quantity=quantity,
                    message="Order placed",
                )
            else:
                return OrderResult(
                    success=False,
                    order_id=None,
                    symbol=symbol,
                    side=side,
                    price=price,
                    quantity=quantity,
                    message=str(res),
                )
        except Exception as e:
            logger.error("place_order error: %s", e)
            return OrderResult(
                success=False,
                order_id=None,
                symbol=symbol,
                side=side,
                price=price,
                quantity=quantity,
                message=str(e),
            )

    def cancel_order(self, order_id: str) -> bool:
        if self.paper_trading:
            logger.info("[PAPER] Cancel order %s", order_id)
            return True
        try:
            results = self._sdk.stock.get_order_results(self._account)
            for o in results.data or []:
                if str(getattr(o, "seq_no", "")) == order_id:
                    self._sdk.stock.cancel_order(self._account, o)
                    return True
        except Exception as e:
            logger.error("cancel_order error: %s", e)
        return False

    # ------------------------------------------------------------------
    # Account / portfolio
    # ------------------------------------------------------------------

    def get_positions(self) -> List[Position]:
        if self.paper_trading or not self._sdk:
            return []
        try:
            inv = self._sdk.accounting.inventories(self._account)
            pnl = self._sdk.accounting.unrealized_gains_and_loses(self._account)

            cost_map = {}
            if pnl.data:
                for item in pnl.data:
                    sym = item.get("stockNo") or item.get("symbol", "")
                    cost_map[sym] = float(item.get("holdingCost", 0) or 0)

            positions = []
            for item in (inv.data or []):
                sym = item.get("stockNo") or item.get("symbol", "")
                qty = int(item.get("todayBalance", 0) or 0)
                if qty > 0:
                    avg_cost = cost_map.get(sym, 0.0)
                    if qty > 0 and avg_cost > 0:
                        avg_cost = avg_cost / qty
                    positions.append(Position(
                        symbol=sym,
                        quantity=qty,
                        avg_cost=avg_cost,
                        current_price=self.get_price(sym) or avg_cost,
                    ))
            return positions
        except Exception as e:
            logger.error("get_positions error: %s", e)
            return []

    def get_account_value(self) -> float:
        """Return total portfolio value (cash + positions). Paper mode returns 0."""
        if self.paper_trading or not self._sdk:
            return 0.0
        try:
            settlement = self._sdk.accounting.query_settlement(self._account, "0d")
            if settlement.data:
                return float(settlement.data[0].get("totalAsset", 0) or 0)
        except Exception as e:
            logger.error("get_account_value error: %s", e)
        return 0.0
