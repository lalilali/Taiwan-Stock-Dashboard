"""
Portfolio tracker using SQLite.

Stores every trade action the bot takes and computes:
  - Realized P&L per trade
  - Total realized P&L
  - Win rate
  - Open positions (paper trading)
"""

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

DB_PATH = "portfolio.db"


@contextmanager
def _db(path: str = DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db(path: str = DB_PATH):
    with _db(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                symbol      TEXT    NOT NULL,
                side        TEXT    NOT NULL,   -- BUY or SELL
                price       REAL    NOT NULL,
                quantity    INTEGER NOT NULL,
                order_id    TEXT,
                strategy    TEXT,
                reason      TEXT,
                pnl         REAL,               -- filled on SELL, NULL on BUY
                is_paper    INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS positions (
                symbol      TEXT    PRIMARY KEY,
                quantity    INTEGER NOT NULL,
                avg_cost    REAL    NOT NULL,
                opened_at   TEXT    NOT NULL
            );
        """)
    logger.info("Portfolio DB initialized at %s", path)


# ---------------------------------------------------------------------------
# Trade recording
# ---------------------------------------------------------------------------

@dataclass
class TradeRecord:
    timestamp: str
    symbol: str
    side: str
    price: float
    quantity: int
    order_id: Optional[str]
    strategy: str
    reason: str
    pnl: Optional[float]
    is_paper: bool


def record_trade(
    symbol: str,
    side: str,          # "BUY" or "SELL"
    price: float,
    quantity: int,
    order_id: Optional[str] = None,
    strategy: str = "",
    reason: str = "",
    is_paper: bool = True,
    db_path: str = DB_PATH,
) -> Optional[float]:
    """
    Persist a trade. For SELLs, calculates realized P&L from the open position.
    Returns realized P&L for SELL trades, else None.
    """
    ts = datetime.now().isoformat(timespec="seconds")
    pnl = None

    with _db(db_path) as conn:
        if side == "BUY":
            # Update or create position
            row = conn.execute("SELECT * FROM positions WHERE symbol=?", (symbol,)).fetchone()
            if row:
                total_qty = row["quantity"] + quantity
                avg_cost = (row["avg_cost"] * row["quantity"] + price * quantity) / total_qty
                conn.execute(
                    "UPDATE positions SET quantity=?, avg_cost=? WHERE symbol=?",
                    (total_qty, avg_cost, symbol),
                )
            else:
                conn.execute(
                    "INSERT INTO positions(symbol, quantity, avg_cost, opened_at) VALUES(?,?,?,?)",
                    (symbol, quantity, price, ts),
                )

        elif side == "SELL":
            row = conn.execute("SELECT * FROM positions WHERE symbol=?", (symbol,)).fetchone()
            if row:
                pnl = (price - row["avg_cost"]) * quantity
                new_qty = row["quantity"] - quantity
                if new_qty <= 0:
                    conn.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
                else:
                    conn.execute(
                        "UPDATE positions SET quantity=? WHERE symbol=?",
                        (new_qty, symbol),
                    )

        conn.execute(
            """INSERT INTO trades
               (timestamp, symbol, side, price, quantity, order_id, strategy, reason, pnl, is_paper)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ts, symbol, side, price, quantity, order_id, strategy, reason, pnl, int(is_paper)),
        )

    if pnl is not None:
        logger.info("Trade recorded: %s %s %s @ %.2f | P&L: %.2f", side, symbol, quantity, price, pnl)
    else:
        logger.info("Trade recorded: %s %s %s @ %.2f", side, symbol, quantity, price)

    return pnl


# ---------------------------------------------------------------------------
# Portfolio statistics
# ---------------------------------------------------------------------------

def get_all_trades(db_path: str = DB_PATH) -> List[dict]:
    with _db(db_path) as conn:
        rows = conn.execute("SELECT * FROM trades ORDER BY timestamp").fetchall()
    return [dict(r) for r in rows]


def get_open_positions(db_path: str = DB_PATH) -> List[dict]:
    with _db(db_path) as conn:
        rows = conn.execute("SELECT * FROM positions").fetchall()
    return [dict(r) for r in rows]


def get_stats(db_path: str = DB_PATH) -> dict:
    """Return a stats summary dict."""
    with _db(db_path) as conn:
        rows = conn.execute(
            "SELECT pnl FROM trades WHERE side='SELL' AND pnl IS NOT NULL"
        ).fetchall()

    if not rows:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
        }

    pnls = [r["pnl"] for r in rows]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    return {
        "total_trades": len(pnls),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "total_pnl": sum(pnls),
        "avg_pnl": sum(pnls) / len(pnls),
        "best_trade": max(pnls),
        "worst_trade": min(pnls),
    }


def print_summary(db_path: str = DB_PATH):
    stats = get_stats(db_path)
    positions = get_open_positions(db_path)

    print("\n" + "=" * 50)
    print("  PORTFOLIO SUMMARY")
    print("=" * 50)
    print(f"  Total closed trades : {stats['total_trades']}")
    print(f"  Winning trades      : {stats['winning_trades']}")
    print(f"  Losing trades       : {stats['losing_trades']}")
    print(f"  Win rate            : {stats['win_rate']:.1%}")
    print(f"  Total realized P&L  : {stats['total_pnl']:+.2f} TWD")
    print(f"  Avg P&L per trade   : {stats['avg_pnl']:+.2f} TWD")
    print(f"  Best trade          : {stats['best_trade']:+.2f} TWD")
    print(f"  Worst trade         : {stats['worst_trade']:+.2f} TWD")

    if positions:
        print("\n  OPEN POSITIONS")
        print(f"  {'Symbol':<8} {'Qty':>8} {'Avg Cost':>10}")
        print("  " + "-" * 30)
        for p in positions:
            print(f"  {p['symbol']:<8} {p['quantity']:>8} {p['avg_cost']:>10.2f}")
    else:
        print("\n  No open positions.")
    print("=" * 50 + "\n")
