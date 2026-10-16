from dataclasses import asdict, dataclass

import pandas as pd

from .indicators import rsi, sma


@dataclass
class Signal:
    strategy: str
    action: str  # BUY | SELL | HOLD
    reason: str
    metrics: dict

    def to_dict(self) -> dict:
        return asdict(self)


def ma_crossover(candles: pd.DataFrame, fast: int = 20, slow: int = 50, **_) -> Signal:
    """BUY when fast SMA crosses above slow SMA on the last closed candle, SELL on the opposite cross."""
    if len(candles) < slow + 1:
        return Signal("ma_crossover", "HOLD", f"Not enough data ({len(candles)} candles, need {slow + 1})", {})
    close = candles["close"]
    f, s = sma(close, fast), sma(close, slow)
    prev_diff, diff = f.iloc[-2] - s.iloc[-2], f.iloc[-1] - s.iloc[-1]
    metrics = {
        "close": round(float(close.iloc[-1]), 8),
        f"sma_{fast}": round(float(f.iloc[-1]), 8),
        f"sma_{slow}": round(float(s.iloc[-1]), 8),
        "gap_pct": round(float(diff / s.iloc[-1] * 100), 3),
        "trend": "bullish" if diff > 0 else "bearish",
    }
    if prev_diff <= 0 < diff:
        return Signal("ma_crossover", "BUY", f"SMA{fast} just crossed above SMA{slow}", metrics)
    if prev_diff >= 0 > diff:
        return Signal("ma_crossover", "SELL", f"SMA{fast} just crossed below SMA{slow}", metrics)
    side = "above" if diff > 0 else "below"
    return Signal("ma_crossover", "HOLD", f"No new cross; SMA{fast} remains {side} SMA{slow}", metrics)


def rsi_threshold(candles: pd.DataFrame, period: int = 14, oversold: float = 30, overbought: float = 70, **_) -> Signal:
    """BUY when RSI is below `oversold`, SELL when above `overbought`."""
    if len(candles) < period + 1:
        return Signal("rsi_threshold", "HOLD", f"Not enough data ({len(candles)} candles)", {})
    value = float(rsi(candles["close"], period).iloc[-1])
    metrics = {"rsi": round(value, 2), "oversold": oversold, "overbought": overbought}
    if value < oversold:
        return Signal("rsi_threshold", "BUY", f"RSI {value:.1f} is below {oversold} (oversold)", metrics)
    if value > overbought:
        return Signal("rsi_threshold", "SELL", f"RSI {value:.1f} is above {overbought} (overbought)", metrics)
    return Signal("rsi_threshold", "HOLD", f"RSI {value:.1f} is neutral", metrics)


STRATEGIES = {"ma_crossover": ma_crossover, "rsi_threshold": rsi_threshold}
