import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'artifacts/current/analysis'


@unittest.skipUnless((OUTPUT / 'summary.json').exists(), 'Extended analysis has not been generated')
class CurrentAnalysisTests(unittest.TestCase):
    def test_subgroups_cover_exactly_the_same_held_out_rows(self):
        overall = pd.read_csv(ROOT / 'artifacts/current/test_metrics.csv').set_index(['horizon_hours', 'model'])
        for filename in ('season_errors', 'monthly_errors', 'year_errors', 'coverage_errors', 'missing_feature_errors', 'peak_errors', 'hour_errors'):
            groups = pd.read_csv(OUTPUT / f'{filename}.csv')
            for keys, group in groups.groupby(['horizon_hours', 'model']):
                reference = overall.loc[keys]
                self.assertEqual(int(group.samples.sum()), int(reference.samples))
                self.assertAlmostEqual(float(np.average(group.MAE, weights=group.samples)), reference.MAE)
                rmse = np.sqrt(np.average(group.RMSE ** 2, weights=group.samples))
                self.assertAlmostEqual(float(rmse), reference.RMSE)

    def test_recent_sample_counts_and_missing_season_are_reported(self):
        summary = json.loads((OUTPUT / 'summary.json').read_text())
        recent = pd.read_csv(OUTPUT / 'recent_period_errors.csv')
        source = pd.read_csv(ROOT / 'artifacts/current/test_predictions.csv')
        month = pd.to_datetime(source.origin, utc=True).dt.tz_convert('Asia/Almaty').dt.strftime('%Y-%m')
        for horizon, group in recent.groupby('horizon_hours'):
            expected = int((source.horizon_hours.eq(horizon) & month.eq(summary['recent_month'])).sum())
            self.assertTrue(group.samples.eq(expected).all())
        self.assertIn('Summer', summary['missing_seasons'])

    def test_equivalent_baselines_have_identical_uncertainty_results(self):
        confidence = pd.read_csv(OUTPUT / 'paired_block_bootstrap.csv')
        same = confidence.loc[confidence.horizon_hours.eq(24)]
        np.testing.assert_allclose(same[['MAE_gain', 'lower_95', 'upper_95']].iloc[0], same[['MAE_gain', 'lower_95', 'upper_95']].iloc[1])
        self.assertTrue(confidence.lower_95.le(confidence.upper_95).all())

    def test_peak_cutoff_uses_pretest_observations(self):
        summary = json.loads((OUTPUT / 'summary.json').read_text())
        manifest = json.loads((ROOT / 'artifacts/current/experiment.json').read_text())
        raw = pd.read_csv(ROOT / 'data/current_training_pm25.csv.gz', compression='gzip')
        raw = raw.loc[raw.station_id.eq(manifest['station']['station_id'])].copy()
        raw['datetime_utc'] = pd.to_datetime(raw.datetime_utc, utc=True)
        series = raw.loc[raw.value_ugm3.ge(0)].groupby('datetime_utc').value_ugm3.mean().sort_index()
        start = series.index.max() - pd.Timedelta(days=3 * 365)
        pretest = series.loc[(series.index >= start) & (series.index < pd.Timestamp(manifest['test_start']))]
        self.assertAlmostEqual(summary['peak_cutoff_ugm3'], pretest.quantile(.9))


if __name__ == '__main__':
    unittest.main()
