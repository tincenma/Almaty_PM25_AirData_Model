import csv
import io
import json
from unittest.mock import patch
import unittest
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app, ROOT


class LatestApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = TestClient(app)
        cls.client = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_latest_inference_matches_training_forecast(self):
        result = self.client.get('/api/latest')
        self.assertEqual(result.status_code, 200)
        data = result.json()
        reference = json.loads((ROOT / 'artifacts/current/latest_forecast.json').read_text())
        self.assertEqual(data['station']['station_id'], 'kgmt_27')
        self.assertEqual(data['origin'], reference['origin'])
        np.testing.assert_allclose([row['predicted'] for row in data['forecasts']],
                                   [row['predicted_pm25'] for row in reference['forecasts']], rtol=1e-5)
        self.assertGreaterEqual(data['input_coverage_24h'], 18)
        self.assertLessEqual(data['input_coverage_168h'], 168)
        for row in data['forecasts']:
            self.assertEqual(pd.Timestamp(row['target_time']), pd.Timestamp(data['origin']) + pd.Timedelta(hours=row['horizon_hours']))
            self.assertEqual(row['target_is_past'], pd.Timestamp(row['target_time']) <= pd.Timestamp(data['generated_at']))

    def test_export_matches_current_inference(self):
        expected = self.client.get('/api/latest').json()
        response = self.client.get('/api/latest/export')
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.text)))
        self.assertEqual(len(rows), 3)
        for row, prediction in zip(rows, expected['forecasts']):
            self.assertEqual(row['station_id'], 'kgmt_27')
            self.assertEqual(row['origin_utc'], expected['origin'])
            self.assertAlmostEqual(float(row['predicted']), prediction['predicted'])

    def test_refresh_failure_keeps_saved_data_and_models(self):
        service = app.state.current
        before = self.client.get('/api/latest').json()
        with patch.object(service, 'refresh_data', side_effect=OSError('offline')):
            response = self.client.post('/api/latest/refresh')
        self.assertEqual(response.status_code, 200)
        after = response.json()
        self.assertIsNotNone(after['refresh_error'])
        self.assertEqual(after['origin'], before['origin'])
        self.assertEqual(after['forecasts'], before['forecasts'])

    def test_missing_measurements_are_not_turned_into_a_forecast(self):
        original = pd.read_csv(ROOT / 'data/current_pm25.csv.gz', compression='gzip')
        original = original.loc[original.station_id.eq('kgmt_27')].tail(1)
        with patch('backend.app.current.pd.read_csv', return_value=original):
            result = self.client.get('/api/latest')
        self.assertEqual(result.status_code, 422)
        self.assertIn('18 observed hours', result.json()['detail'])

    def test_model_station_is_exposed_in_directory(self):
        data = self.client.get('/api/stations').json()
        self.assertEqual(data['current_model_station']['id'], 'kgmt_27')

    def test_raw_data_refresh_when_commit_api_is_unavailable(self):
        content = (ROOT / 'data/current_pm25.csv.gz').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            (destination / 'data').mkdir()
            with patch.object(app.state.current, 'root', destination), patch('urllib.request.urlopen', side_effect=[OSError('API unavailable'), io.BytesIO(content)]) as network:
                app.state.current.refresh_data()
            metadata = json.loads((destination / 'data/current_pm25.csv.source.json').read_text())
            self.assertIsNone(metadata['commit'])
            self.assertIn('/main/', metadata['url'])
            self.assertEqual(network.call_count, 2)
            self.assertEqual((destination / 'data/current_pm25.csv.gz').read_bytes(), content)


if __name__ == '__main__':
    unittest.main()
