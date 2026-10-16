import uuid
from decimal import ROUND_DOWN, Decimal

from .client import Coinbase
from .state import State


def _base_currency(product_id: str) -> str:
    return product_id.split("-")[0]


def _round_down(value: float, increment: str) -> str:
    inc = Decimal(increment)
    return str((Decimal(str(value)) / inc).to_integral_value(rounding=ROUND_DOWN) * inc)


class PaperBroker:
    """Simulated fills at live Coinbase prices against balances in SQLite."""

    mode = "paper"

    def __init__(self, cb: Coinbase, state: State, fee_pct: float):
        self.cb, self.state, self.fee = cb, state, fee_pct / 100

    def place(self, product_id: str, side: str, quote_usd: float, order_type: str, limit_price: float | None) -> dict:
        price = self.cb.price(product_id)
        base_ccy = _base_currency(product_id)
        bal = self.state.balances()
        order = dict(mode="paper", product_id=product_id, side=side, order_type=order_type, quote_usd=quote_usd)

        if order_type == "limit":
            if not limit_price or limit_price <= 0:
                raise ValueError("limit orders need a positive limit_price")
            exec_price = limit_price
            marketable = (side == "BUY" and limit_price >= price) or (side == "SELL" and limit_price <= price)
        else:
            exec_price, marketable = price, True

        base_size = quote_usd / exec_price
        if side == "BUY" and bal.get("USD", 0) < quote_usd:
            raise ValueError(f"Insufficient paper USD: have ${bal.get('USD', 0):.2f}, need ${quote_usd:.2f}")
        if side == "SELL" and bal.get(base_ccy, 0) < base_size:
            raise ValueError(f"Insufficient paper {base_ccy}: have {bal.get(base_ccy, 0):.8f}, need {base_size:.8f}")

        # Reserve funds now; a resting limit order keeps them held until fill or cancel.
        if side == "BUY":
            self.state.adjust_balance("USD", -quote_usd)
        else:
            self.state.adjust_balance(base_ccy, -base_size)

        if marketable:
            fill_price = price if order_type == "market" else min(limit_price, price) if side == "BUY" else max(limit_price, price)
            oid = self.state.log_order(**order, base_size=base_size, price=fill_price, status="open")
            self._fill(oid)
        else:
            oid = self.state.log_order(**order, base_size=base_size, price=limit_price, status="open",
                                       reason=f"resting limit; market at {price}")
        return self.state.get_order(oid)

    def _fill(self, oid: int) -> None:
        o = self.state.get_order(oid)
        base_ccy = _base_currency(o["product_id"])
        if o["side"] == "BUY":
            received = o["quote_usd"] / o["price"] * (1 - self.fee)
            self.state.adjust_balance(base_ccy, received)
            self.state.update_order(oid, status="filled", base_size=received)
        else:
            self.state.adjust_balance("USD", o["base_size"] * o["price"] * (1 - self.fee))
            self.state.update_order(oid, status="filled")

    def settle_open_orders(self) -> None:
        """Fill resting paper limit orders whose price the market has reached (checked against current price)."""
        for o in self.state.orders(limit=500, mode="paper", status="open"):
            price = self.cb.price(o["product_id"])
            if (o["side"] == "BUY" and price <= o["price"]) or (o["side"] == "SELL" and price >= o["price"]):
                self._fill(o["id"])

    def cancel(self, order_id: str) -> dict:
        o = self.state.get_order(int(order_id))
        if not o or o["mode"] != "paper":
            raise ValueError(f"No paper order {order_id}")
        if o["status"] != "open":
            raise ValueError(f"Order {order_id} is {o['status']}, not open")
        if o["side"] == "BUY":
            self.state.adjust_balance("USD", o["quote_usd"])
        else:
            self.state.adjust_balance(_base_currency(o["product_id"]), o["base_size"])
        self.state.update_order(o["id"], status="cancelled")
        return self.state.get_order(o["id"])


class LiveBroker:
    """Real orders on Coinbase Advanced Trade."""

    mode = "live"

    def __init__(self, cb: Coinbase, state: State):
        self.cb, self.state = cb, state

    def place(self, product_id: str, side: str, quote_usd: float, order_type: str, limit_price: float | None) -> dict:
        client = self.cb.require_key()
        product = self.cb.product(product_id)
        price = float(product["price"])
        coid = str(uuid.uuid4())

        if order_type == "market":
            if side == "BUY":
                base_size = None
                resp = client.market_order_buy(coid, product_id, quote_size=_round_down(quote_usd, product["quote_increment"]))
            else:
                base_size = _round_down(quote_usd / price, product["base_increment"])
                resp = client.market_order_sell(coid, product_id, base_size=base_size)
        else:
            if not limit_price or limit_price <= 0:
                raise ValueError("limit orders need a positive limit_price")
            lp = _round_down(limit_price, product["price_increment"])
            base_size = _round_down(quote_usd / float(lp), product["base_increment"])
            fn = client.limit_order_gtc_buy if side == "BUY" else client.limit_order_gtc_sell
            resp = fn(coid, product_id, base_size=base_size, limit_price=lp)
            price = float(lp)

        r = resp.to_dict()
        ok = r.get("success", False)
        oid = self.state.log_order(
            mode="live", product_id=product_id, side=side, order_type=order_type, quote_usd=quote_usd,
            base_size=float(base_size) if base_size else None, price=price,
            status="submitted" if ok else "rejected",
            reason=None if ok else str(r.get("error_response") or r),
            exchange_order_id=(r.get("success_response") or {}).get("order_id"),
        )
        return {**self.state.get_order(oid), "exchange_response": r}

    def settle_open_orders(self) -> None:
        pass

    def cancel(self, order_id: str) -> dict:
        client = self.cb.require_key()
        local = self.state.db.execute("SELECT id FROM orders WHERE exchange_order_id=? OR id=?", (order_id, order_id)).fetchone()
        exchange_id = order_id
        if local:
            exchange_id = self.state.get_order(local["id"])["exchange_order_id"] or order_id
        r = client.cancel_orders(order_ids=[exchange_id]).to_dict()
        if local:
            self.state.update_order(local["id"], status="cancelled")
        return r
