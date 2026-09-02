"""Technical indicators computed with pandas/numpy only (no ta-lib dependency)."""
import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    return result.fillna(50)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return pd.DataFrame({"upper": upper, "mid": mid, "lower": lower})


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                k_period: int = 14, k_smooth: int = 3, d_smooth: int = 3) -> pd.DataFrame:
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    raw_k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    k = raw_k.rolling(window=k_smooth).mean().fillna(50)
    d = k.rolling(window=d_smooth).mean().fillna(50)
    return pd.DataFrame({"k": k, "d": d})


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    avg_volume = volume.rolling(window=period).mean()
    return (volume / avg_volume.replace(0, np.nan)).fillna(1.0)


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Standard ATR-band-flip Supertrend. Stateful by construction (each bar's final band depends
    on the previous bar's final band and trend direction), so — like heikin_ashi below — this is a
    sequential loop, not a vectorized one-liner. Returns the trend line itself (`supertrend`) and
    `direction` (+1 = uptrend / price above the line, -1 = downtrend / price below it)."""
    hl2 = (high + low) / 2
    atr_series = atr(high, low, close, period=period)
    basic_upper = hl2 + multiplier * atr_series
    basic_lower = hl2 - multiplier * atr_series

    n = len(close)
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    direction = np.ones(n)  # +1 uptrend, -1 downtrend
    st = np.zeros(n)

    close_v = close.to_numpy()
    basic_upper_v = basic_upper.to_numpy()
    basic_lower_v = basic_lower.to_numpy()

    for i in range(n):
        if i == 0 or np.isnan(basic_upper_v[i - 1]):
            final_upper[i] = basic_upper_v[i]
            final_lower[i] = basic_lower_v[i]
            direction[i] = 1
            st[i] = final_lower[i]
            continue

        final_upper[i] = (
            basic_upper_v[i] if (basic_upper_v[i] < final_upper[i - 1] or close_v[i - 1] > final_upper[i - 1])
            else final_upper[i - 1]
        )
        final_lower[i] = (
            basic_lower_v[i] if (basic_lower_v[i] > final_lower[i - 1] or close_v[i - 1] < final_lower[i - 1])
            else final_lower[i - 1]
        )

        if direction[i - 1] == 1:
            direction[i] = -1 if close_v[i] < final_lower[i] else 1
        else:
            direction[i] = 1 if close_v[i] > final_upper[i] else -1

        st[i] = final_lower[i] if direction[i] == 1 else final_upper[i]

    return pd.DataFrame({"supertrend": st, "direction": direction}, index=close.index)


def chaikin_money_flow(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
                        period: int = 20) -> pd.Series:
    """Standard CMF: rolling sum of (money-flow-multiplier * volume) over rolling sum of volume.
    Positive = buying pressure dominant over the window, negative = selling pressure."""
    range_ = (high - low).replace(0, np.nan)
    money_flow_multiplier = ((close - low) - (high - close)) / range_
    money_flow_volume = (money_flow_multiplier * volume).fillna(0.0)
    return (money_flow_volume.rolling(period).sum() / volume.rolling(period).sum().replace(0, np.nan)).fillna(0.0)


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
         session_date: pd.Series) -> pd.Series:
    """Session-anchored VWAP: cumulative(typical_price * volume) / cumulative(volume), resetting at
    the start of each trading day (session_date changing) rather than accumulating across days —
    an intraday VWAP is meaningless carried over from a prior session's close."""
    typical_price = (high + low + close) / 3
    tp_vol = typical_price * volume
    grouped_tp_vol = tp_vol.groupby(session_date).cumsum()
    grouped_vol = volume.groupby(session_date).cumsum()
    return (grouped_tp_vol / grouped_vol.replace(0, np.nan)).fillna(close)


def bollinger_bandwidth(series: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.Series:
    """(upper - lower) / mid — normalized band width. A 'squeeze' is this ratio compressed well
    below its own recent average (low volatility coiling); an 'explosion' is it expanding sharply
    right after a squeeze (the breakout the squeeze was building toward)."""
    bands = bollinger_bands(series, period=period, num_std=num_std)
    return ((bands["upper"] - bands["lower"]) / bands["mid"].replace(0, np.nan)).fillna(0.0)


def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Converts a regular OHLC DataFrame (columns: Open, High, Low, Close) into Heikin Ashi
    candles — a smoothed, lagging transform (ha_open averages the PREVIOUS ha_open/ha_close),
    not an independent snapshot of that bar. ha_open seeds from the first bar's own open+close
    average, the standard convention when there's no prior HA candle to average from. ha_high/
    ha_low are synthetic (not real traded prices) — never use them as an actual stop level."""
    ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4

    ha_open = pd.Series(index=df.index, dtype=float)
    ha_open.iloc[0] = (df["Open"].iloc[0] + df["Close"].iloc[0]) / 2
    for i in range(1, len(df)):
        ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2

    ha_high = pd.concat([df["High"], ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([df["Low"], ha_open, ha_close], axis=1).min(axis=1)
    return pd.DataFrame({"ha_open": ha_open, "ha_high": ha_high, "ha_low": ha_low, "ha_close": ha_close})
