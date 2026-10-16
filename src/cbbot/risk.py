from .config import Limits


class RiskError(Exception):
    pass


def check_order(
    *,
    product_id: str,
    side: str,
    quote_usd: float,
    mode: str,
    confirm: bool,
    spent_today: float,
    limits: Limits,
) -> None:
    """Raise RiskError if the order violates any limit. Runs before every order, paper or live."""
    if side not in ("BUY", "SELL"):
        raise RiskError(f"side must be BUY or SELL, got {side!r}")
    if product_id not in limits.allowed_products:
        raise RiskError(f"{product_id} is not in allowed_products {limits.allowed_products}")
    if quote_usd <= 0:
        raise RiskError("order size must be positive")
    if quote_usd > limits.max_order_usd:
        raise RiskError(f"${quote_usd:.2f} exceeds max_order_usd ${limits.max_order_usd:.2f}")
    if spent_today + quote_usd > limits.daily_cap_usd:
        raise RiskError(
            f"${quote_usd:.2f} would bring today's total to ${spent_today + quote_usd:.2f}, "
            f"over daily_cap_usd ${limits.daily_cap_usd:.2f}"
        )
    if mode == "live" and not confirm:
        raise RiskError("LIVE mode: this places a real order. Re-send with confirm=true after the user approves.")
