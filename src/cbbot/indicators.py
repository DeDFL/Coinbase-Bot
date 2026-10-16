import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI: first average is a simple mean of `period` changes, then Wilder smoothing."""
    delta = series.diff().to_numpy()
    out = [float("nan")] * len(series)
    if len(series) <= period:
        return pd.Series(out, index=series.index)
    gains = [max(d, 0.0) for d in delta[1:]]
    losses = [max(-d, 0.0) for d in delta[1:]]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(series)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return pd.Series(out, index=series.index)
