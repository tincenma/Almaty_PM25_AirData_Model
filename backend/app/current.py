"""Inference from latest published observations using the current-station models."""
import json
from pathlib import Path
import threading

import joblib
import pandas as pd

from .features import make_features
from .service import number


class CurrentModelService:
    def __init__(self, root: Path):
        self.root = root
        directory = root / 'artifacts' / 'current'
        self.manifest = json.loads((directory / 'experiment.json').read_text(encoding='utf-8'))
        self.station_id = self.manifest['station']['station_id']
        self.bundles = {h: joblib.load(directory / f'forecast_{h}h.joblib') for h in self.manifest['horizons_hours']}
        for h, bundle in self.bundles.items():
            if bundle['station_id'] != self.station_id or bundle['horizon_hours'] != h or bundle['features'] != self.manifest['features']:
                raise ValueError('Current model metadata mismatch.')
        self.metrics = pd.read_csv(directory / 'test_metrics.csv').to_dict(orient='records')
        self.lock = threading.Lock()

    def forecast(self, refresh=False):
        with self.lock:
            error = None
            if refresh:
                try:
                    self.refresh_data()
                except (OSError, ValueError, KeyError):
                    error = 'Unable to retrieve updated measurements. Showing the saved dataset; check its measurement time.'
            raw = pd.read_csv(self.root / 'data' / 'current_pm25.csv.gz', compression='gzip')
            frame = raw.loc[raw.station_id.eq(self.station_id)].copy()
            frame['datetime_utc'] = pd.to_datetime(frame.datetime_utc, utc=True, errors='coerce')
            frame['value_ugm3'] = pd.to_numeric(frame.value_ugm3, errors='coerce')
            frame = frame.dropna(subset=['datetime_utc', 'value_ugm3']).loc[lambda df: df.value_ugm3.ge(0)]
            measured = frame.groupby('datetime_utc').value_ugm3.mean().sort_index()
            if measured.empty:
                raise ValueError('No measurements are available for the trained station.')
            origin = measured.index[-1]
            series = measured.reindex(pd.date_range(origin - pd.Timedelta(hours=168), origin, freq='h'))
            features = make_features(series).iloc[[-1]]
            count = int(series.tail(24).count())
            if count < 18:
                raise ValueError('The trained station needs at least 18 observed hours in the latest day to issue a forecast.')
            now = pd.Timestamp.now(tz='UTC')
            age = (now - origin).total_seconds() / 3600
            if age < -1:
                raise ValueError('Station measurement time is in the future; no forecast can be issued.')
            estimates = []
            for horizon, bundle in self.bundles.items():
                predicted = max(float(bundle['pipeline'].predict(features[bundle['features']])[0]), 0.)
                target = origin + pd.Timedelta(hours=horizon)
                estimates.append({'horizon_hours': horizon, 'target_time': target.isoformat(),
                                  'predicted': predicted, 'target_is_past': target <= now, 'model': bundle['family']})
            return {'mode': 'latest_measurements', 'station': self.manifest['station'],
                    'origin': origin.isoformat(), 'generated_at': now.isoformat(), 'age_hours': round(max(age, 0), 1),
                    'stale': age > 24, 'current_pm25': float(series.iloc[-1]),
                    'input_coverage_24h': count, 'input_coverage_168h': int(series.tail(168).count()),
                    'history': [{'time': t.isoformat(), 'value': number(v)} for t, v in series.tail(25).items()],
                    'forecasts': estimates, 'metrics': self.metrics, 'refresh_error': error,
                    'trained_at': self.manifest['trained_at'], 'test_start': self.manifest['test_start'],
                    'dataset': json.loads((self.root / 'data' / 'current_pm25.csv.source.json').read_text(encoding='utf-8'))}

    def refresh_data(self):
        # Refresh observations only; fitted model artifacts and test scores stay fixed.
        from urllib.request import Request, urlopen
        import hashlib
        import io
        headers = {'User-Agent': 'Breathe-Almaty-Research'}
        try:
            with urlopen(Request('https://api.github.com/repos/qazybekb/AirDatakz-OpenData/commits/main', headers=headers), timeout=8) as response:
                commit = json.load(response)['sha']
        except OSError:
            # Raw public data can remain reachable when the commit API is unavailable.
            commit = None
        url = f'https://raw.githubusercontent.com/qazybekb/AirDatakz-OpenData/{commit or "main"}/almaty/pm25.csv.gz'
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            content = response.read()
        frame = pd.read_csv(io.BytesIO(content), compression='gzip')
        if not {'station_id', 'datetime_utc', 'value_ugm3'}.issubset(frame.columns) or not frame.station_id.eq(self.station_id).any():
            raise ValueError('Updated dataset does not contain the trained station.')
        destination = self.root / 'data' / 'current_pm25.csv.gz'
        temporary = destination.with_suffix('.tmp')
        temporary.write_bytes(content)
        temporary.replace(destination)
        metadata = {'commit': commit, 'url': url, 'sha256': hashlib.sha256(content).hexdigest()}
        destination.with_suffix('.source.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
