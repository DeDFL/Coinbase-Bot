import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import STATE_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    product_id TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    quote_usd REAL NOT NULL,
    base_size REAL,
    price REAL,
    status TEXT NOT NULL,          -- filled | open | cancelled | rejected | submitted
    reason TEXT,
    exchange_order_id TEXT
);
CREATE TABLE IF NOT EXISTS paper_balances (
    currency TEXT PRIMARY KEY,
    amount REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    product_id TEXT NOT NULL,
    action TEXT NOT NULL,
    confidence TEXT,
    price REAL NOT NULL,
    summary TEXT
);
"""

COUNTED_STATUSES = ("filled", "open", "submitted")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class State:
    def __init__(self, path: Path | None = None, paper_starting_usd: float = 1000.0):
        path = path or STATE_DIR / "cbbot.sqlite"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        if not self.db.execute("SELECT 1 FROM paper_balances LIMIT 1").fetchone():
            self.db.execute("INSERT INTO paper_balances VALUES ('USD', ?)", (paper_starting_usd,))
        self.db.commit()

    # orders
    def log_order(self, **o) -> int:
        o.setdefault("ts", now_iso())
        cols = ",".join(o)
        cur = self.db.execute(f"INSERT INTO orders ({cols}) VALUES ({','.join('?' * len(o))})", tuple(o.values()))
        self.db.commit()
        return cur.lastrowid

    def update_order(self, order_id: int, **fields) -> None:
        sets = ",".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE orders SET {sets} WHERE id=?", (*fields.values(), order_id))
        self.db.commit()

    def get_order(self, order_id: int) -> dict | None:
        row = self.db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        return dict(row) if row else None

    def orders(self, limit: int = 50, mode: str | None = None, status: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM orders WHERE 1=1", []
        if mode:
            q, args = q + " AND mode=?", args + [mode]
        if status:
            q, args = q + " AND status=?", args + [status]
        q += " ORDER BY id DESC LIMIT ?"
        return [dict(r) for r in self.db.execute(q, (*args, limit))]

    def spent_today(self, mode: str) -> float:
        """Total notional of non-rejected orders in the last 24 hours (rolling)."""
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds")
        row = self.db.execute(
            f"SELECT COALESCE(SUM(quote_usd),0) FROM orders WHERE mode=? AND ts>=? "
            f"AND status IN ({','.join('?' * len(COUNTED_STATUSES))})",
            (mode, since, *COUNTED_STATUSES),
        ).fetchone()
        return float(row[0])

    # paper balances
    def balances(self) -> dict[str, float]:
        return {r["currency"]: r["amount"] for r in self.db.execute("SELECT * FROM paper_balances")}

    def adjust_balance(self, currency: str, delta: float) -> None:
        self.db.execute(
            "INSERT INTO paper_balances VALUES (?, ?) ON CONFLICT(currency) DO UPDATE SET amount = amount + excluded.amount",
            (currency, delta),
        )
        self.db.commit()

    # signals
    def log_signal(self, product_id: str, action: str, confidence: str, price: float, summary: str) -> int:
        cur = self.db.execute(
            "INSERT INTO signals (ts, product_id, action, confidence, price, summary) VALUES (?,?,?,?,?,?)",
            (now_iso(), product_id, action, confidence, price, summary),
        )
        self.db.commit()
        return cur.lastrowid

    def signals(self, days: int = 30, product_id: str | None = None) -> list[dict]:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        q, args = "SELECT * FROM signals WHERE ts>=?", [since]
        if product_id:
            q, args = q + " AND product_id=?", args + [product_id]
        return [dict(r) for r in self.db.execute(q + " ORDER BY id DESC", args)]
