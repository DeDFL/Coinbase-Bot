import pandas as pd

from cbbot.strategies import ma_crossover, rsi_threshold


def df(closes):
    return pd.DataFrame({"close": [float(c) for c in closes]})


def test_ma_cross_up():
    closes = [10] * 10 + [9] * 5 + [20]  # fast(3) jumps above slow(10) on last candle
    assert ma_crossover(df(closes), fast=3, slow=10).action == "BUY"


def test_ma_cross_down():
    closes = [10] * 10 + [11] * 5 + [0]
    assert ma_crossover(df(closes), fast=3, slow=10).action == "SELL"


def test_ma_hold_trend():
    sig = ma_crossover(df(range(1, 30)), fast=3, slow=10)
    assert sig.action == "HOLD" and sig.metrics["trend"] == "bullish"


def test_ma_not_enough_data():
    assert ma_crossover(df([1, 2, 3]), fast=3, slow=10).action == "HOLD"


def test_rsi_signals():
    assert rsi_threshold(df(range(40, 1, -1))).action == "BUY"
    assert rsi_threshold(df(range(1, 40))).action == "SELL"
