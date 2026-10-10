"""Exact inference feature definitions from the training notebook."""

import numpy as np
import pandas as pd


def make_features(series: pd.Series) -> pd.DataFrame:
    features = pd.DataFrame({"pm25_now": series})
    for lag in (1, 2, 3, 6, 12, 24, 48, 72, 168):
        features[f"pm25_lag_{lag}h"] = series.shift(lag)
    for window in (6, 24, 72, 168):
        roll = series.rolling(window, min_periods=max(2, window // 4))
        features[f"mean_{window}h"] = roll.mean()
        features[f"std_{window}h"] = roll.std()
        features[f"observed_{window}h"] = series.rolling(window, min_periods=1).count()
    local_time = series.index.tz_convert("Asia/Almaty")
    for name, values, period in (
        ("hour", local_time.hour, 24),
        ("weekday", local_time.dayofweek, 7),
        ("year_day", local_time.dayofyear - 1, 365.25),
    ):
        features[f"{name}_sin"] = np.sin(2 * np.pi * values / period)
        features[f"{name}_cos"] = np.cos(2 * np.pi * values / period)
    return features.astype("float32")

