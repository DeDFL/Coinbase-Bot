"""Coinbase trading + signals MCP server for Claude Code."""

from datetime import datetime

from mcp.server.mcpserver import MCPServer

from .broker import LiveBroker, PaperBroker
from .client import GRANULARITY_SECONDS, Coinbase
from .config import BRIEFINGS_DIR, load_config
from .risk import RiskError, check_order
from .state import State
from .strategies import STRATEGIES

cfg = load_config()
cb = Coinbase()
state = State(paper_starting_usd=cfg.paper_starting_usd)
broker = LiveBroker(cb, state) if cfg.mode == "live" else PaperBroker(cb, state, cfg.paper_fee_pct)

mcp = MCPServer(
    "coinbase",
    instructions=(
        f"Coinbase trading bot. Mode: {cfg.mode.upper()}. "
        "Paper mode simulates fills at live prices. In live mode, never set confirm=true unless the user "
        "explicitly approved that specific order in this conversation. Signals from evaluate_signal and "
        "get_market_snapshot are advisory; do not trade on them unless the user asks."
    ),
)


def _pid(product_id: str) -> str:
    return product_id.strip().upper()


def _evaluate(product_id: str, strategy: str, params: dict | None = None) -> dict:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy {strategy!r}. Options: {list(STRATEGIES)}")
    p = {**cfg.strategies.get(strategy, {}), **(params or {})}
    granularity = p.pop("granularity", "ONE_HOUR")
    candles = cb.candles(product_id, granularity, limit=300)
    sig = STRATEGIES[strategy](candles, **p).to_dict()
    sig.update(product_id=product_id, granularity=granularity)
    return sig


# ---------- read-only ----------

@mcp.tool()
def get_status() -> dict:
    """Trading mode, whether an API key is configured, risk limits, and how much has been traded in the last 24h."""
    return {
        "mode": cfg.mode,
        "api_key_configured": cb.has_key,
        "limits": vars(cfg.limits),
        "spent_last_24h_usd": round(state.spent_today(cfg.mode), 2),
        "watchlist": cfg.watchlist,
        "strategies": cfg.strategies,
    }


@mcp.tool()
def get_accounts() -> dict:
    """Balances. Paper mode: simulated balances valued at live prices. Live mode: real non-zero Coinbase balances."""
    if cfg.mode == "paper":
        broker.settle_open_orders()
        out, total = {}, 0.0
        for ccy, amt in state.balances().items():
            if abs(amt) < 1e-12:
                continue
            usd = amt if ccy == "USD" else amt * cb.price(f"{ccy}-USD")
            out[ccy] = {"amount": round(amt, 8), "value_usd": round(usd, 2)}
            total += usd
        return {"mode": "paper", "balances": out, "total_usd": round(total, 2)}
    accts = []
    for a in cb.accounts():
        avail = float(a["available_balance"]["value"])
        hold = float((a.get("hold") or {}).get("value", 0))
        if avail or hold:
            accts.append({"currency": a["currency"], "available": avail, "hold": hold})
    return {"mode": "live", "balances": accts}


@mcp.tool()
def get_price(product_id: str) -> dict:
    """Current price and 24h stats for a product like BTC-USD."""
    p = cb.product(_pid(product_id))
    keys = ["product_id", "price", "price_percentage_change_24h", "volume_24h", "high_24h", "low_24h",
            "best_bid_price", "best_ask_price"]
    return {k: p.get(k) for k in keys}


@mcp.tool()
def get_candles(product_id: str, granularity: str = "ONE_HOUR", limit: int = 100) -> dict:
    """Closed OHLCV candles, oldest first. granularity: ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, THIRTY_MINUTE,
    ONE_HOUR, TWO_HOUR, SIX_HOUR, ONE_DAY. limit up to 1000."""
    if granularity not in GRANULARITY_SECONDS:
        return {"error": f"granularity must be one of {list(GRANULARITY_SECONDS)}"}
    df = cb.candles(_pid(product_id), granularity, min(limit, 1000))
    df["time"] = df["time"].dt.strftime("%Y-%m-%dT%H:%MZ")
    return {"product_id": _pid(product_id), "granularity": granularity,
            "candles": df[["time", "open", "high", "low", "close", "volume"]].to_dict("records")}


@mcp.tool()
def evaluate_signal(product_id: str, strategy: str = "ma_crossover", params: dict | None = None) -> dict:
    """Run a strategy (ma_crossover or rsi_threshold) and return BUY/SELL/HOLD with reason and indicator values.
    params overrides config.yaml, e.g. {"fast": 10, "slow": 30, "granularity": "ONE_DAY"}."""
    return _evaluate(_pid(product_id), strategy, params)


@mcp.tool()
def get_market_snapshot(products: list[str] | None = None) -> dict:
    """Technical snapshot for briefings: price, 24h/7d change, volume vs 30-day average, distance from 30-day
    high/low, and every strategy on both hourly and daily candles. Defaults to the watchlist."""
    results = {}
    for pid in [_pid(p) for p in (products or cfg.watchlist)]:
        try:
            prod = cb.product(pid)
            price = float(prod["price"])
            daily = cb.candles(pid, "ONE_DAY", 90)
            hourly = cb.candles(pid, "ONE_HOUR", 300)
            last30 = daily.tail(30)
            hi, lo = float(last30["high"].max()), float(last30["low"].min())
            vol_24h = float(hourly.tail(24)["volume"].sum())
            avg_daily_vol = float(last30["volume"].mean())
            signals = {}
            for name, fn in STRATEGIES.items():
                params = {k: v for k, v in cfg.strategies.get(name, {}).items() if k != "granularity"}
                signals[f"{name}_hourly"] = fn(hourly, **params).to_dict()
                signals[f"{name}_daily"] = fn(daily, **params).to_dict()
            results[pid] = {
                "price": price,
                "change_24h_pct": round(float(prod.get("price_percentage_change_24h") or 0), 2),
                "change_7d_pct": round((price / float(daily["close"].iloc[-7]) - 1) * 100, 2) if len(daily) >= 7 else None,
                "change_30d_pct": round((price / float(daily["close"].iloc[-30]) - 1) * 100, 2) if len(daily) >= 30 else None,
                "volume_24h_vs_30d_avg": round(vol_24h / avg_daily_vol, 2) if avg_daily_vol else None,
                "high_30d": hi,
                "low_30d": lo,
                "pct_below_30d_high": round((1 - price / hi) * 100, 2),
                "pct_above_30d_low": round((price / lo - 1) * 100, 2),
                "signals": signals,
            }
        except Exception as e:  # keep other products in the snapshot
            results[pid] = {"error": str(e)}
    return {"as_of": datetime.now().astimezone().isoformat(timespec="minutes"), "products": results}


@mcp.tool()
def get_order_history(limit: int = 20) -> dict:
    """Recent orders for the current mode, including rejected attempts."""
    broker.settle_open_orders()
    return {"mode": cfg.mode, "orders": state.orders(limit=limit, mode=cfg.mode)}


# ---------- trading ----------

@mcp.tool()
def place_order(
    product_id: str,
    side: str,
    quote_size_usd: float,
    order_type: str = "market",
    limit_price: float | None = None,
    confirm: bool = False,
) -> dict:
    """Place a BUY or SELL order sized in USD. order_type: market or limit (limit needs limit_price).
    Enforces max order size, daily cap and allowed products. In LIVE mode, confirm=true is required and must
    only be set after the user explicitly approves this exact order."""
    pid, side, order_type = _pid(product_id), side.strip().upper(), order_type.strip().lower()
    if order_type not in ("market", "limit"):
        return {"rejected": True, "reason": "order_type must be market or limit"}
    try:
        check_order(product_id=pid, side=side, quote_usd=quote_size_usd, mode=cfg.mode, confirm=confirm,
                    spent_today=state.spent_today(cfg.mode), limits=cfg.limits)
        return {"mode": cfg.mode, "order": broker.place(pid, side, quote_size_usd, order_type, limit_price)}
    except (RiskError, ValueError, RuntimeError) as e:
        state.log_order(mode=cfg.mode, product_id=pid, side=side, order_type=order_type,
                        quote_usd=quote_size_usd, price=limit_price, status="rejected", reason=str(e))
        return {"mode": cfg.mode, "rejected": True, "reason": str(e)}


@mcp.tool()
def cancel_order(order_id: str) -> dict:
    """Cancel an open order. Paper: the local order id. Live: the Coinbase order id or local id."""
    try:
        return {"mode": cfg.mode, "result": broker.cancel(order_id)}
    except (ValueError, RuntimeError) as e:
        return {"mode": cfg.mode, "error": str(e)}


@mcp.tool()
def run_strategy(product_id: str, strategy: str, quote_size_usd: float, confirm: bool = False) -> dict:
    """Evaluate a strategy and, only if it says BUY or SELL, place a market order of quote_size_usd.
    Only use when the user explicitly asks to trade on a strategy."""
    sig = _evaluate(_pid(product_id), strategy)
    if sig["action"] == "HOLD":
        return {"mode": cfg.mode, "signal": sig, "order": None}
    return {"mode": cfg.mode, "signal": sig,
            "order": place_order(product_id, sig["action"], quote_size_usd, "market", None, confirm)}


# ---------- signal tracking + briefings ----------

@mcp.tool()
def log_signal(product_id: str, action: str, confidence: str, summary: str) -> dict:
    """Record an advisory signal (BUY/SELL/HOLD, confidence low/medium/high, one-line summary) with the current
    price so its accuracy can be reviewed later."""
    pid = _pid(product_id)
    price = cb.price(pid)
    sid = state.log_signal(pid, action.strip().upper(), confidence.strip().lower(), price, summary)
    return {"id": sid, "product_id": pid, "price": price}


@mcp.tool()
def get_signal_history(days: int = 30, product_id: str | None = None) -> dict:
    """Past signals with price change since each one and whether the call was right so far
    (BUY right if price rose, SELL right if it fell; HOLD and unchanged prices not scored)."""
    rows = state.signals(days, _pid(product_id) if product_id else None)
    prices: dict[str, float] = {}
    scored = right = 0
    for r in rows:
        now = prices.setdefault(r["product_id"], cb.price(r["product_id"]))
        chg = (now / r["price"] - 1) * 100
        r["price_now"], r["change_since_pct"] = now, round(chg, 2)
        if r["action"] in ("BUY", "SELL") and chg != 0:
            r["correct"] = chg > 0 if r["action"] == "BUY" else chg < 0
            scored += 1
            right += r["correct"]
    return {"signals": rows, "scored": scored, "correct": right,
            "hit_rate_pct": round(right / scored * 100, 1) if scored else None}


@mcp.tool()
def save_briefing(markdown: str) -> dict:
    """Save a briefing to briefings/YYYY-MM-DD.md (adds -HHMM if one already exists today)."""
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    now = datetime.now()
    path = BRIEFINGS_DIR / f"{now:%Y-%m-%d}.md"
    if path.exists():
        path = BRIEFINGS_DIR / f"{now:%Y-%m-%d-%H%M}.md"
    path.write_text(markdown)
    return {"saved": str(path)}


@mcp.tool()
def get_latest_briefing() -> dict:
    """Return the most recent saved briefing."""
    files = sorted(BRIEFINGS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime)
    if not files:
        return {"briefing": None, "note": "No briefings yet. Run /briefing in ~/coinbase-bot."}
    return {"file": files[-1].name, "briefing": files[-1].read_text()}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
