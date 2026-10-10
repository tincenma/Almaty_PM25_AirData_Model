"""Load trusted local artifacts and perform historical model inference."""

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd

from .features import make_features


def number(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None


class ModelService:
    def __init__(self, root: Path):
        artifacts = root / "artifacts"
        self.manifest = json.loads((artifacts / "experiment.json").read_text(encoding="utf-8"))
        data_file = root / "data" / "almaty_pm25.csv.gz"
        checksum = hashlib.sha256(data_file.read_bytes()).hexdigest()
        if checksum != self.manifest["dataset_sha256"]:
            raise ValueError("Dataset checksum differs from the training experiment.")
        self.horizons = self.manifest["horizons_hours"]
        self.station_id = self.manifest["station_id"]
        raw = pd.read_csv(data_file, compression="gzip", dtype={"station_id": "string"})
        selected = raw.loc[raw["station_id"].eq(self.station_id)].copy()
        selected["datetime_utc"] = pd.to_datetime(selected["datetime_utc"], utc=True, errors="coerce")
        selected["value_ugm3"] = pd.to_numeric(selected["value_ugm3"], errors="coerce")
        selected = selected.dropna(subset=["datetime_utc", "value_ugm3"])
        selected = selected.loc[selected["value_ugm3"].ge(0)]
        self.coordinates = {"latitude": number(selected["lat"].median()),
                            "longitude": number(selected["lon"].median())}
        periods = self.manifest["periods"]
        grid = pd.date_range(pd.Timestamp(periods["start"]), pd.Timestamp(periods["test_end"]),
                             freq="h", inclusive="left", name="datetime_utc")
        self.series = selected.groupby("datetime_utc")["value_ugm3"].mean().sort_index().reindex(grid)
        self.features = make_features(self.series)
        self.bundles = {}
        for family in ("XGBoost", "Ridge"):
            for h in self.horizons:
                bundle = joblib.load(artifacts / f"{family.lower()}_{h}h.joblib")
                if (bundle["station_id"] != self.station_id or bundle["horizon_hours"] != h
                        or bundle["features"] != self.manifest["features"]):
                    raise ValueError("Model metadata differs from the training experiment.")
                self.bundles[(family, h)] = bundle
        self.metrics = pd.read_csv(artifacts / "test_metrics.csv")
        self.seasons = pd.read_csv(artifacts / "season_errors.csv")
        self.ablation = pd.read_csv(artifacts / "validation_feature_ablation.csv")
        self.peaks = pd.read_csv(artifacts / "peak_errors.csv")
        eligible = (self.series.notna() & self.features["observed_24h"].ge(18)
                    & self.features["pm25_lag_168h"].notna())
        valid_end = pd.Timestamp(periods["validation_end"])
        test_end = pd.Timestamp(periods["test_end"])
        eligible &= self.series.index >= valid_end
        for h in self.horizons:
            eligible &= (self.series.shift(-h).notna() & self.series.shift(24 - h).notna()
                         & ((self.series.index + pd.Timedelta(hours=h)) < test_end))
        self.origins = self.series.index[eligible]
        if self.origins.empty:
            raise ValueError("No eligible replay timestamps found.")
        self.origin_set = set(self.origins)
        self.origin_groups = {}
        for timestamp in self.origins:
            date = timestamp.tz_convert("Asia/Almaty").date().isoformat()
            self.origin_groups.setdefault(date, []).append(timestamp.isoformat())
        # Prefer an origin with an observable next day for a useful first demonstration.
        future_count = pd.concat([self.series.shift(-h).notna() for h in range(1, 25)], axis=1).sum(axis=1)
        complete = self.origins[future_count.reindex(self.origins).ge(20)]
        self.default_origin = complete[len(complete) // 2] if len(complete) else self.origins[0]

    def overview(self):
        return {
            "station": {"id": self.station_id, "name": self.manifest["station_name"],
                        "city": "Almaty", **self.coordinates},
            "mode": "historical_replay", "timezone": "Asia/Almaty",
            "horizons": self.horizons, "models": ["XGBoost", "Ridge"],
            "default_origin": self.default_origin.isoformat(),
            "available_dates": sorted(self.origin_groups),
            "eligible_origins": len(self.origins),
            "observed_hours": int(self.series.notna().sum()),
            "coverage_pct": round(self.series.notna().mean() * 100, 1),
            "periods": self.manifest["periods"],
            "metrics": self.metrics.to_dict(orient="records"),
            "seasons": self.seasons.to_dict(orient="records"),
            "ablation": self.ablation.to_dict(orient="records"),
            "peaks": self.peaks.to_dict(orient="records"),
            "dataset": {"commit": self.manifest["dataset_commit"],
                        "sha256": self.manifest["dataset_sha256"],
                        "attribution": self.manifest["attribution"], "license": self.manifest["license"]},
        }

    def forecast(self, origin: datetime, family: str):
        timestamp = pd.Timestamp(origin).tz_convert("UTC")
        if timestamp not in self.origin_set:
            raise ValueError("This hour has insufficient history or falls outside the held-out replay period. Choose an available hour.")
        row = self.features.loc[[timestamp]]
        estimates = []
        for h in self.horizons:
            bundle = self.bundles[(family, h)]
            estimate = max(float(bundle["pipeline"].predict(row[bundle["features"]])[0]), bundle["clip_min"])
            target = timestamp + pd.Timedelta(hours=h)
            estimates.append({"horizon_hours": h, "target_time": target.isoformat(),
                              "predicted": estimate, "observed": number(self.series.loc[target])})
        past = self.series.loc[timestamp - pd.Timedelta(hours=48):timestamp]
        future = self.series.loc[timestamp + pd.Timedelta(hours=1):timestamp + pd.Timedelta(hours=24)]
        return {
            "origin": timestamp.isoformat(), "model": family, "station_id": self.station_id,
            "current_pm25": number(self.series.loc[timestamp]),
            "history": [{"time": t.isoformat(), "value": number(value)} for t, value in past.items()],
            "outcomes": [{"time": t.isoformat(), "value": number(value)} for t, value in future.items()],
            "forecasts": estimates,
            "input_coverage_24h": int(row["observed_24h"].iloc[0]),
        }

