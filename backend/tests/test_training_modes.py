"""Frozen reproduction must survive time passing; live updates require freshness."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from backend import train_current as training


class TrainingModeTests(unittest.TestCase):
    def test_reproduction_uses_fixed_station_even_with_a_future_clock(self):
        with patch.object(training.pd, 'Timestamp', wraps=pd.Timestamp) as timestamp:
            timestamp.now.return_value = pd.Timestamp('2030-01-01', tz='UTC')
            frame, station, reference = training.reproduction_input()
            timestamp.now.assert_not_called()
        self.assertEqual(station['station_id'], reference['station']['station_id'])
        self.assertTrue(frame.station_id.eq(station['station_id']).any())

    def test_reproduction_rejects_changed_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'changed.csv.gz'
            path.write_bytes(b'changed dataset')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                training.reproduction_input(path)

    def test_reproduction_rejects_missing_recorded_station(self):
        reference = json.loads(training.REFERENCE.read_text(encoding='utf-8'))
        reference['station']['station_id'] = 'missing-station'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'experiment.json'
            path.write_text(json.dumps(reference), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'absent'):
                training.reproduction_input(reference=path)

    def test_update_selection_still_rejects_stale_data(self):
        frame, _, reference = training.reproduction_input()
        latest = pd.Timestamp(reference['latest_measurement'])
        with tempfile.TemporaryDirectory() as directory:
            station = training.choose_station(frame, Path(directory), now=latest)
            self.assertEqual(station['station_id'], reference['station']['station_id'])
            with self.assertRaisesRegex(ValueError, 'No fresh station'):
                training.choose_station(frame, Path(directory), now=latest + pd.Timedelta(days=2))

    def test_training_cannot_overwrite_deployed_experiment(self):
        with patch.object(training, 'download') as download:
            with self.assertRaisesRegex(ValueError, 'must be empty'):
                training.train('update', output=training.OUTPUT)
            download.assert_not_called()


if __name__ == '__main__':
    unittest.main()
