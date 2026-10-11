"""Reproducible training for a currently reporting Almaty PM2.5 station."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from backend.app.features import make_features

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts' / 'current'
DATA = ROOT / 'data' / 'current_pm25.csv.gz'
SOURCE = DATA.with_suffix('.source.json')
SNAPSHOT = ROOT / 'data' / 'current_training_pm25.csv.gz'
REFERENCE = ROOT / 'data' / 'current_training_experiment.json'
SEED = 42
CANDIDATES = {'Ridge': [{'alpha': value} for value in (1., 10., 100.)],
              'XGBoost': [{'n_estimators': 200, 'max_depth': 3, 'learning_rate': .05, 'reg_lambda': 10.},
                          {'n_estimators': 350, 'max_depth': 5, 'learning_rate': .04, 'reg_lambda': 10.}]}


def download():
    headers = {'User-Agent': 'Breathe-Almaty-Research'}
    with urlopen(Request('https://api.github.com/repos/qazybekb/AirDatakz-OpenData/commits/main', headers=headers), timeout=30) as response:
        commit = json.load(response)['sha']
    url = f'https://raw.githubusercontent.com/qazybekb/AirDatakz-OpenData/{commit}/almaty/pm25.csv.gz'
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        content = response.read()
    pd.read_csv(io.BytesIO(content), compression='gzip', nrows=1)
    DATA.write_bytes(content)
    SOURCE.write_text(json.dumps({'commit': commit, 'url': url, 'sha256': hashlib.sha256(content).hexdigest()}, indent=2), encoding='utf-8')


def load(path=DATA):
    frame = pd.read_csv(path, compression='gzip', dtype={'station_id': 'string'})
    frame['datetime_utc'] = pd.to_datetime(frame['datetime_utc'], utc=True, errors='coerce')
    frame['value_ugm3'] = pd.to_numeric(frame['value_ugm3'], errors='coerce')
    return frame.dropna(subset=['station_id', 'datetime_utc', 'value_ugm3']).loc[lambda df: df.value_ugm3.ge(0)]


def choose_station(frame, output, now=None):
    now = pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    candidates = []
    for station_id, group in frame.groupby('station_id'):
        latest = group.datetime_utc.max()
        if not pd.Timedelta(0) <= now - latest <= pd.Timedelta(hours=24):
            continue
        series = group.groupby('datetime_utc').value_ugm3.mean().sort_index()
        grid = pd.date_range(max(series.index.min(), latest - pd.Timedelta(days=3 * 365)), latest, freq='h')
        series = series.reindex(grid)
        coverage = series.notna().mean()
        recent = series.tail(168).notna().mean()
        if len(series) < 180 * 24 or series.count() < 6000 or series.tail(24).count() < 18:
            continue
        candidates.append({'station_id': str(station_id), 'station_name': group.iloc[-1].station_name,
                           'source': group.iloc[-1].source, 'hours': len(series),
                           'coverage': coverage, 'observed_hours': int(series.count()), 'recent_coverage': recent, 'latest': latest.isoformat()})
    ranked = pd.DataFrame(candidates)
    if ranked.empty:
        raise ValueError('No fresh station has sufficient training and recent history.')
    ranked = ranked.sort_values(['observed_hours', 'coverage', 'recent_coverage'], ascending=False)
    ranked.to_csv(output / 'station_candidates.csv', index=False)
    return ranked.iloc[0].to_dict()


def reproduction_input(snapshot=SNAPSHOT, reference=REFERENCE):
    """Validate the frozen input before training; never consult the wall clock."""
    manifest = json.loads(reference.read_text(encoding='utf-8'))
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    if digest != manifest['dataset']['sha256']:
        raise ValueError('Training snapshot checksum does not match the recorded experiment.')
    frame = load(snapshot)
    station = manifest['station'].copy()
    selected = frame.loc[frame.station_id.eq(station['station_id'])]
    if selected.empty:
        raise ValueError('Recorded station is absent from the training snapshot.')
    if selected.datetime_utc.max() != pd.Timestamp(manifest['latest_measurement']):
        raise ValueError('Recorded latest measurement does not match the training snapshot.')
    return frame, station, manifest


def scores(y, prediction):
    return {'MAE': float(mean_absolute_error(y, prediction)),
            'RMSE': float(np.sqrt(mean_squared_error(y, prediction))), 'R2': float(r2_score(y, prediction))}


def model(family, settings, seed=SEED):
    steps = [('imputer', SimpleImputer(strategy='median', add_indicator=True))]
    if family == 'Ridge':
        steps += [('scale', StandardScaler()), ('model', Ridge(**settings))]
    else:
        steps += [('model', XGBRegressor(objective='reg:squarederror', tree_method='hist', n_jobs=4,
                                        random_state=seed, verbosity=0, subsample=.85, colsample_bytree=.9, **settings))]
    return Pipeline(steps)


def train(mode='reproduce', output=None, snapshot=SNAPSHOT, reference=REFERENCE):
    if mode not in ('reproduce', 'update'):
        raise ValueError('Training mode must be reproduce or update.')
    run_id = pd.Timestamp.now(tz='UTC').strftime('%Y%m%dT%H%M%S%fZ')
    output = Path(output) if output else ROOT / 'artifacts' / mode / run_id
    # Keep completed experiments and the app's deployed models intact.
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty; use a new directory for each experiment.')
    recorded = None
    if mode == 'reproduce':
        frame, station, recorded = reproduction_input(snapshot, reference)
        source = recorded['dataset']
        input_path = snapshot
    else:
        download()
        frame = load()
        source = json.loads(SOURCE.read_text(encoding='utf-8'))
        input_path = DATA
    output.mkdir(parents=True, exist_ok=True)
    if mode == 'update':
        station = choose_station(frame, output)
    (output / 'training_pm25.csv.gz').write_bytes(input_path.read_bytes())
    seed = recorded['random_seed'] if recorded else SEED
    selected = frame.loc[frame.station_id.eq(station['station_id'])]
    measured = selected.groupby('datetime_utc').value_ugm3.mean().sort_index()
    latest = measured.index.max()
    grid = pd.date_range(max(measured.index.min(), latest - pd.Timedelta(days=3 * 365)), latest, freq='h')
    series = measured.reindex(grid)
    features = make_features(series)
    columns = list(features.columns)
    if recorded and columns != recorded['features']:
        raise ValueError('Feature definitions differ from the recorded experiment.')
    eligible = features.observed_24h.ge(18) & series.notna()
    # Split chronologically by observed origins because calendar periods contain long gaps.
    origins = series.index[eligible]
    test_start = pd.Timestamp(recorded['test_start']) if recorded else origins[int(len(origins) * .85)]
    valid_start = pd.Timestamp(recorded['validation_start']) if recorded else origins[int(len(origins) * .70)]
    validation_rows, test_rows, predictions, forecast = [], [], [], []
    candidates = recorded.get('model_candidates', CANDIDATES) if recorded else CANDIDATES
    settings_selected = {}
    for horizon in (1, 6, 24):
        target = series.shift(-horizon)
        seasonal = series.shift(24 - horizon)
        usable = eligible & target.notna() & seasonal.notna()
        target_time = series.index + pd.Timedelta(hours=horizon)
        train_mask = usable & (target_time < valid_start)
        valid_mask = usable & (series.index >= valid_start) & (target_time < test_start)
        test_mask = usable & (series.index >= test_start)
        if min(train_mask.sum(), valid_mask.sum(), test_mask.sum()) < 100:
            raise ValueError(f'Insufficient examples at horizon {horizon}.')
        best = None
        for family, configurations in candidates.items():
            for settings in configurations:
                estimator = model(family, settings, seed)
                started = time.perf_counter()
                estimator.fit(features.loc[train_mask, columns], target.loc[train_mask])
                duration = time.perf_counter() - started
                prediction = np.maximum(estimator.predict(features.loc[valid_mask, columns]), 0)
                result = scores(target.loc[valid_mask], prediction)
                validation_rows.append({'horizon_hours': horizon, 'model': family, 'settings': json.dumps(settings),
                                        'fit_seconds': duration, **result})
                if best is None or result['MAE'] < best[0]:
                    best = (result['MAE'], family, settings.copy())
        _, family, settings = best
        # Refit on pre-test observations only, including validation, with horizon purging.
        evaluation_mask = usable & (target_time < test_start)
        estimator = model(family, settings, seed)
        estimator.fit(features.loc[evaluation_mask, columns], target.loc[evaluation_mask])
        prediction = np.maximum(estimator.predict(features.loc[test_mask, columns]), 0)
        bundle = {'pipeline': estimator, 'features': columns, 'station_id': station['station_id'],
                  'horizon_hours': horizon, 'clip_min': 0., 'family': family}
        joblib.dump(bundle, output / f'evaluation_{horizon}h.joblib')
        for name, values in [(family, prediction), ('Persistence', series.loc[test_mask]), ('Same hour yesterday', seasonal.loc[test_mask])]:
            test_rows.append({'horizon_hours': horizon, 'model': name, 'samples': int(test_mask.sum()), **scores(target.loc[test_mask], values)})
        predictions.append(pd.DataFrame({'origin': series.index[test_mask], 'horizon_hours': horizon,
                                         'target': target.loc[test_mask].values, 'predicted': prediction,
                                         'persistence': series.loc[test_mask].values, 'seasonal': seasonal.loc[test_mask].values}))
        # Deployment refit includes all available labeled data AFTER independent evaluation.
        estimator = model(family, settings, seed)
        estimator.fit(features.loc[usable, columns], target.loc[usable])
        bundle['pipeline'] = estimator
        joblib.dump(bundle, output / f'forecast_{horizon}h.joblib')
        estimate = max(float(estimator.predict(features.iloc[[-1]][columns])[0]), 0.)
        forecast.append({'horizon_hours': horizon, 'model': family, 'target_time': (latest + pd.Timedelta(hours=horizon)).isoformat(), 'predicted_pm25': estimate})
        settings_selected[str(horizon)] = {'family': family, 'settings': settings, 'training_examples': int(usable.sum())}
    if recorded and settings_selected != recorded['selected_models']:
        raise ValueError('Selected models differ from the reference; check pinned dependency versions.')
    pd.DataFrame(validation_rows).to_csv(output / 'validation_metrics.csv', index=False)
    pd.DataFrame(test_rows).to_csv(output / 'test_metrics.csv', index=False)
    pd.concat(predictions, ignore_index=True).to_csv(output / 'test_predictions.csv', index=False)
    manifest = {'station': station, 'dataset': source,
                'trained_at': pd.Timestamp.now(tz='UTC').isoformat(), 'features': columns,
                'horizons_hours': [1, 6, 24], 'validation_start': valid_start.isoformat(),
                'test_start': test_start.isoformat(), 'latest_measurement': latest.isoformat(),
                'measurement_pm25': float(series.iloc[-1]), 'recent_observed_hours': int(series.tail(24).count()),
                'selected_models': settings_selected, 'random_seed': seed,
                'model_candidates': candidates, 'training_mode': mode,
                'reference_trained_at': recorded['trained_at'] if recorded else None,
                'note': 'Forecast horizons begin at the latest measured hour, not the current wall-clock time. Long data gaps exist, including sparse 2026 coverage. Missing history is imputed with indicators; rows without targets are excluded. Accuracy on sparse current conditions is not established.',
                'recent_observed_hours_168': int(series.tail(168).count()),
                'test_origin_start': predictions[0].origin.min().isoformat(),
                'test_origin_end': predictions[0].origin.max().isoformat()}
    (output / 'experiment.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'latest_forecast.json').write_text(json.dumps({'origin': latest.isoformat(), 'forecasts': forecast}, indent=2), encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('reproduce', 'update'), default='reproduce',
                        help='Reproduce the frozen experiment (default), or download fresh data and train a new one.')
    parser.add_argument('--output', type=Path, help='Empty output directory; defaults to artifacts/<mode>/<UTC run ID>.')
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT, help='Frozen dataset for reproduce mode.')
    parser.add_argument('--reference', type=Path, default=REFERENCE, help='Recorded experiment for reproduce mode.')
    args = parser.parse_args()
    train(args.mode, args.output, args.snapshot, args.reference)
