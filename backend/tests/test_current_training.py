"""Check saved predictions against serialized models and independent metrics."""
import hashlib
import json
from pathlib import Path
import unittest

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from backend.app.features import make_features

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'artifacts' / 'current'


@unittest.skipUnless((DIRECTORY / 'experiment.json').exists(), 'Current-station experiment has not been trained')
class CurrentTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((DIRECTORY / 'experiment.json').read_text(encoding='utf-8'))
        cls.predictions = pd.read_csv(DIRECTORY / 'test_predictions.csv')
        cls.predictions['origin'] = pd.to_datetime(cls.predictions.origin, utc=True)
        data = ROOT / 'data' / 'current_training_pm25.csv.gz'
        assert hashlib.sha256(data.read_bytes()).hexdigest() == cls.manifest['dataset']['sha256']
        raw = pd.read_csv(data, compression='gzip')
        selected = raw.loc[raw.station_id.eq(cls.manifest['station']['station_id'])].copy()
        selected['datetime_utc'] = pd.to_datetime(selected.datetime_utc, utc=True)
        selected = selected.dropna(subset=['datetime_utc', 'value_ugm3'])
        selected = selected.loc[selected.value_ugm3.ge(0)]
        measured = selected.groupby('datetime_utc').value_ugm3.mean().sort_index()
        latest = measured.index.max()
        grid = pd.date_range(max(measured.index.min(), latest - pd.Timedelta(days=3 * 365)), latest, freq='h')
        cls.series = measured.reindex(grid)
        cls.features = make_features(cls.series)

    def test_evaluation_predictions_match_saved_pipelines_and_actual_targets(self):
        metrics = pd.read_csv(DIRECTORY / 'test_metrics.csv')
        for horizon in self.manifest['horizons_hours']:
            saved = self.predictions.loc[self.predictions.horizon_hours.eq(horizon)]
            self.assertTrue(saved.origin.ge(pd.Timestamp(self.manifest['test_start'])).all())
            actual = self.series.reindex(pd.DatetimeIndex(saved.origin) + pd.Timedelta(hours=horizon))
            np.testing.assert_allclose(actual.values, saved.target.values)
            sample = saved.iloc[np.linspace(0, len(saved) - 1, 20, dtype=int)]
            bundle = joblib.load(DIRECTORY / f'evaluation_{horizon}h.joblib')
            estimate = np.maximum(bundle['pipeline'].predict(self.features.loc[sample.origin, bundle['features']]), 0)
            np.testing.assert_allclose(estimate, sample.predicted, rtol=1e-5)
            result = metrics.loc[metrics.horizon_hours.eq(horizon) & metrics.model.eq(bundle['family'])].iloc[0]
            self.assertAlmostEqual(mean_absolute_error(saved.target, saved.predicted), result.MAE)

    def test_latest_forecasts_match_refitted_pipelines(self):
        latest = json.loads((DIRECTORY / 'latest_forecast.json').read_text(encoding='utf-8'))
        self.assertEqual(pd.Timestamp(latest['origin']), self.series.index[-1])
        for forecast in latest['forecasts']:
            horizon = forecast['horizon_hours']
            bundle = joblib.load(DIRECTORY / f'forecast_{horizon}h.joblib')
            prediction = max(float(bundle['pipeline'].predict(self.features.iloc[[-1]][bundle['features']])[0]), 0.)
            self.assertAlmostEqual(prediction, forecast['predicted_pm25'])
            self.assertEqual(pd.Timestamp(forecast['target_time']), self.series.index[-1] + pd.Timedelta(hours=horizon))


if __name__ == '__main__':
    unittest.main()
