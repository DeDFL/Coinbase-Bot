import pytest

from cbbot.config import Limits
from cbbot.risk import RiskError, check_order

LIM = Limits(max_order_usd=25, daily_cap_usd=100, allowed_products=["BTC-USD"])


def ok(**kw):
    args = dict(product_id="BTC-USD", side="BUY", quote_usd=10, mode="paper", confirm=False, spent_today=0, limits=LIM)
    check_order(**{**args, **kw})


def test_valid_paper_order():
    ok()


@pytest.mark.parametrize("kw", [
    {"quote_usd": 26},
    {"quote_usd": 0},
    {"product_id": "DOGE-USD"},
    {"spent_today": 95},
    {"side": "HODL"},
    {"mode": "live", "confirm": False},
])
def test_rejections(kw):
    with pytest.raises(RiskError):
        ok(**kw)


def test_live_with_confirm():
    ok(mode="live", confirm=True)
