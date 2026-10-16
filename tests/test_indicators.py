import pandas as pd
import pytest

from cbbot.indicators import rsi, sma


def test_sma():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    assert sma(s, 3).tolist()[2:] == [2.0, 3.0, 4.0]


def test_rsi_matches_wilder_reference():
    # Classic Wilder example closes; RSI(14) at index 14 is ~70.53
    closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
              45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64]
    r = rsi(pd.Series(closes), 14)
    assert r.iloc[:14].isna().all()
    # StockCharts reference values for this series
    assert [round(v, 2) for v in r.iloc[14:]] == pytest.approx([70.53, 66.32, 66.55, 69.41, 66.36, 57.97], abs=0.1)  # StockCharts rounds intermediates


def test_rsi_extremes():
    up = pd.Series(range(1, 40), dtype=float)
    down = pd.Series(range(40, 1, -1), dtype=float)
    assert rsi(up).iloc[-1] == pytest.approx(100)
    assert rsi(down).iloc[-1] == pytest.approx(0)
