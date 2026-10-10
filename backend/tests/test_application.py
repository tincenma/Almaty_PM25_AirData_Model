import csv
import io
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.app.features import make_features
from backend.app.main import app, ROOT
from backend.app.stations import reporting_status
from datetime import datetime, timezone, timedelta


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = TestClient(app)
        cls.client = cls.context.__enter__()
        cls.service = app.state.models
        cls.reference = pd.read_csv(ROOT / "artifacts" / "test_predictions.csv")

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_health_and_overview(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ready", "models_loaded": 6})
        result = self.client.get("/api/overview")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["station"]["id"], "oaq_25903")
        self.assertGreater(result.json()["eligible_origins"], 1000)

    def test_station_status_and_catalog_do_not_change_the_model_station(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(reporting_status((now - timedelta(hours=2)).isoformat(), now), "recent")
        self.assertEqual(reporting_status((now - timedelta(days=3)).isoformat(), now), "not_recent")
        self.assertEqual(reporting_status((now + timedelta(days=1)).isoformat(), now), "unknown")
        response = self.client.get("/api/stations")
        self.assertEqual(response.status_code, 200)
        catalog = response.json()
        self.assertEqual(catalog["trained_station"]["id"], self.service.station_id)
        self.assertTrue(catalog["trained_station"]["model_available"])
        self.assertGreater(len(catalog["stations"]), 20)
        self.assertTrue(all(not row["model_available"] for row in catalog["stations"] if row["id"] != self.service.station_id))

    def test_predictions_match_notebook_for_both_model_families(self):
        # Compare origins across the held-out year, not just the default replay example.
        indices = np.linspace(0, len(self.service.origins) - 1, 12, dtype=int)
        for index in indices:
            origin = self.service.origins[index]
            for family in ("XGBoost", "Ridge"):
                with self.subTest(origin=origin, family=family):
                    response = self.client.post("/api/forecast", json={"origin": origin.isoformat(), "model": family})
                    self.assertEqual(response.status_code, 200)
                    for estimate in response.json()["forecasts"]:
                        match = self.reference.loc[
                            self.reference["origin_time"].eq(str(origin))
                            & self.reference["model"].eq(family)
                            & self.reference["horizon_hours"].eq(estimate["horizon_hours"])]
                        self.assertEqual(len(match), 1)
                        self.assertAlmostEqual(estimate["predicted"], match["prediction"].iloc[0], places=4)
                        self.assertEqual(estimate["observed"], match["actual"].iloc[0])

    def test_changing_future_observations_does_not_change_input_features(self):
        origin = self.service.default_origin
        changed = self.service.series.copy()
        changed.loc[changed.index > origin] = 9999
        pd.testing.assert_series_equal(make_features(changed).loc[origin], self.service.features.loc[origin])

    def test_hourly_lags_preserve_missing_hours(self):
        index = pd.date_range("2024-01-01", periods=200, freq="h", tz="UTC")
        series = pd.Series(np.arange(200, dtype=float), index=index)
        series.iloc[100] = np.nan
        features = make_features(series)
        self.assertTrue(pd.isna(features.iloc[101]["pm25_lag_1h"]))
        self.assertEqual(features.iloc[101]["pm25_lag_24h"], 77)

    def test_rejects_invalid_origin_and_model(self):
        for payload in (
            {"origin": "2024-01-01T00:00:00"},
            {"origin": "2020-01-01T00:00:00Z"},
            {"origin": self.service.default_origin.isoformat(), "model": "Other"},
            {"origin": self.service.default_origin.isoformat(), "unexpected": True},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/api/forecast", json=payload).status_code, 422)

    def test_accepts_equivalent_local_timezone_origin(self):
        origin = self.service.default_origin
        response = self.client.post("/api/forecast", json={"origin": origin.tz_convert("Asia/Almaty").isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["origin"], origin.isoformat())

    def test_date_filter_matches_almaty_calendar(self):
        date = self.service.default_origin.tz_convert("Asia/Almaty").date().isoformat()
        result = self.client.get("/api/origins", params={"date": date}).json()
        self.assertTrue(all(pd.Timestamp(t).tz_convert("Asia/Almaty").date().isoformat() == date for t in result["origins"]))
        self.assertEqual(self.client.get("/api/origins", params={"date": "2000-01-01"}).status_code, 404)

    def test_csv_export_matches_inference(self):
        payload = {"origin": self.service.default_origin.isoformat(), "model": "Ridge"}
        forecast = self.client.post("/api/forecast", json=payload).json()
        response = self.client.post("/api/forecast/export", json=payload)
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.text)))
        self.assertEqual(len(rows), 3)
        for row, estimate in zip(rows, forecast["forecasts"]):
            self.assertEqual(row["station_id"], self.service.station_id)
            self.assertEqual(float(row["predicted"]), estimate["predicted"])


if __name__ == "__main__":
    unittest.main()

