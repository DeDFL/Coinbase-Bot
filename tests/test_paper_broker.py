import pytest

from cbbot.broker import PaperBroker
from cbbot.state import State


class FakeCB:
    def __init__(self, price):
        self.p = price

    def price(self, _):
        return self.p


@pytest.fixture
def setup(tmp_path):
    state = State(tmp_path / "t.sqlite", paper_starting_usd=1000)
    cb = FakeCB(50_000)
    return cb, state, PaperBroker(cb, state, fee_pct=0)


def test_market_buy_and_sell(setup):
    cb, state, b = setup
    o = b.place("BTC-USD", "BUY", 100, "market", None)
    assert o["status"] == "filled"
    assert state.balances()["USD"] == pytest.approx(900)
    assert state.balances()["BTC"] == pytest.approx(0.002)
    cb.p = 100_000
    b.place("BTC-USD", "SELL", 100, "market", None)
    assert state.balances()["BTC"] == pytest.approx(0.001)
    assert state.balances()["USD"] == pytest.approx(1000)


def test_insufficient_funds(setup):
    _, _, b = setup
    with pytest.raises(ValueError):
        b.place("BTC-USD", "SELL", 10, "market", None)


def test_resting_limit_fill_and_cancel(setup):
    cb, state, b = setup
    o = b.place("BTC-USD", "BUY", 100, "limit", 40_000)
    assert o["status"] == "open" and state.balances()["USD"] == pytest.approx(900)
    o2 = b.place("BTC-USD", "BUY", 100, "limit", 30_000)
    b.cancel(str(o2["id"]))
    assert state.balances()["USD"] == pytest.approx(900)
    cb.p = 39_000
    b.settle_open_orders()
    assert state.get_order(o["id"])["status"] == "filled"
    assert state.balances()["BTC"] == pytest.approx(100 / 40_000)


def test_spent_today_counts_fills_not_rejections(setup):
    _, state, b = setup
    b.place("BTC-USD", "BUY", 20, "market", None)
    state.log_order(mode="paper", product_id="BTC-USD", side="BUY", order_type="market", quote_usd=50, status="rejected")
    assert state.spent_today("paper") == pytest.approx(20)
