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
SEED = 42


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


def load():
    frame = pd.read_csv(DATA, compression='gzip', dtype={'station_id': 'string'})
    frame['datetime_utc'] = pd.to_datetime(frame['datetime_utc'], utc=True, errors='coerce')
    frame['value_ugm3'] = pd.to_numeric(frame['value_ugm3'], errors='coerce')
    return frame.dropna(subset=['station_id', 'datetime_utc', 'value_ugm3']).loc[lambda df: df.value_ugm3.ge(0)]


def choose_station(frame):
    now = pd.Timestamp.now(tz='UTC')
    candidates = []
    for station_id, group in frame.groupby('station_id'):
        latest = group.datetime_utc.max()
        if not pd.Timedelta(0) <= now - latest <= pd.Timedelta(hours=24):
            continue
        series = group.groupby('datetime_utc').value_ugm3.mean().sort_index()
        grid = pd.date_range(max(series.index.min(), latest - pd.Timedelta(days=365)), latest, freq='h')
        series = series.reindex(grid)
        coverage = series.notna().mean()
        recent = series.tail(168).notna().mean()
        if len(series) < 180 * 24 or coverage < .7 or recent < .8 or series.tail(24).count() < 18 or pd.isna(series.iloc[-169]):
            continue
        candidates.append({'station_id': str(station_id), 'station_name': group.iloc[-1].station_name,
                           'source': group.iloc[-1].source, 'hours': len(series),
                           'coverage': coverage, 'recent_coverage': recent, 'latest': latest.isoformat()})
    ranked = pd.DataFrame(candidates)
    if ranked.empty:
        raise ValueError('No fresh station has sufficient training and recent history.')
    ranked = ranked.sort_values(['coverage', 'hours', 'recent_coverage'], ascending=False)
    ranked.to_csv(OUTPUT / 'station_candidates.csv', index=False)
    return ranked.iloc[0].to_dict()


def scores(y, prediction):
    return {'MAE': float(mean_absolute_error(y, prediction)),
            'RMSE': float(np.sqrt(mean_squared_error(y, prediction))), 'R2': float(r2_score(y, prediction))}


def model(family, settings):
    steps = [('imputer', SimpleImputer(strategy='median', add_indicator=True))]
    if family == 'Ridge':
        steps += [('scale', StandardScaler()), ('model', Ridge(**settings))]
    else:
        steps += [('model', XGBRegressor(objective='reg:squarederror', tree_method='hist', n_jobs=4,
                                        random_state=SEED, verbosity=0, subsample=.85, colsample_bytree=.9, **settings))]
    return Pipeline(steps)


def train():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame = load()
    station = choose_station(frame)
    selected = frame.loc[frame.station_id.eq(station['station_id'])]
    measured = selected.groupby('datetime_utc').value_ugm3.mean().sort_index()
    latest = measured.index.max()
    grid = pd.date_range(max(measured.index.min(), latest - pd.Timedelta(days=365)), latest, freq='h')
    series = measured.reindex(grid)
    features = make_features(series)
    columns = list(features.columns)
    eligible = features.observed_24h.ge(18) & features.pm25_lag_168h.notna() & series.notna()
    test_start = latest - pd.Timedelta(days=28)
    valid_start = test_start - pd.Timedelta(days=28)
    validation_rows, test_rows, predictions, forecast = [], [], [], []
    candidates = {'Ridge': [{'alpha': value} for value in (1., 10., 100.)],
                  'XGBoost': [{'n_estimators': 200, 'max_depth': 3, 'learning_rate': .05, 'reg_lambda': 10.},
                              {'n_estimators': 350, 'max_depth': 5, 'learning_rate': .04, 'reg_lambda': 10.}]}
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
                estimator = model(family, settings)
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
        estimator = model(family, settings)
        estimator.fit(features.loc[evaluation_mask, columns], target.loc[evaluation_mask])
        prediction = np.maximum(estimator.predict(features.loc[test_mask, columns]), 0)
        bundle = {'pipeline': estimator, 'features': columns, 'station_id': station['station_id'],
                  'horizon_hours': horizon, 'clip_min': 0., 'family': family}
        joblib.dump(bundle, OUTPUT / f'evaluation_{horizon}h.joblib')
        for name, values in [(family, prediction), ('Persistence', series.loc[test_mask]), ('Same hour yesterday', seasonal.loc[test_mask])]:
            test_rows.append({'horizon_hours': horizon, 'model': name, 'samples': int(test_mask.sum()), **scores(target.loc[test_mask], values)})
        predictions.append(pd.DataFrame({'origin': series.index[test_mask], 'horizon_hours': horizon,
                                         'target': target.loc[test_mask].values, 'predicted': prediction,
                                         'persistence': series.loc[test_mask].values, 'seasonal': seasonal.loc[test_mask].values}))
        # Deployment refit includes all available labeled data AFTER independent evaluation.
        estimator = model(family, settings)
        estimator.fit(features.loc[usable, columns], target.loc[usable])
        bundle['pipeline'] = estimator
        joblib.dump(bundle, OUTPUT / f'forecast_{horizon}h.joblib')
        estimate = max(float(estimator.predict(features.iloc[[-1]][columns])[0]), 0.)
        forecast.append({'horizon_hours': horizon, 'model': family, 'target_time': (latest + pd.Timedelta(hours=horizon)).isoformat(), 'predicted_pm25': estimate})
        settings_selected[str(horizon)] = {'family': family, 'settings': settings, 'training_examples': int(usable.sum())}
    pd.DataFrame(validation_rows).to_csv(OUTPUT / 'validation_metrics.csv', index=False)
    pd.DataFrame(test_rows).to_csv(OUTPUT / 'test_metrics.csv', index=False)
    pd.concat(predictions, ignore_index=True).to_csv(OUTPUT / 'test_predictions.csv', index=False)
    manifest = {'station': station, 'dataset': json.loads(SOURCE.read_text(encoding='utf-8')),
                'trained_at': pd.Timestamp.now(tz='UTC').isoformat(), 'features': columns,
                'horizons_hours': [1, 6, 24], 'validation_start': valid_start.isoformat(),
                'test_start': test_start.isoformat(), 'latest_measurement': latest.isoformat(),
                'measurement_pm25': float(series.iloc[-1]), 'recent_observed_hours': int(series.tail(24).count()),
                'selected_models': settings_selected, 'random_seed': SEED,
                'note': 'Forecast horizons begin at the latest measured hour, not the current wall-clock time. Data publications can be delayed.'}
    (OUTPUT / 'experiment.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTPUT / 'latest_forecast.json').write_text(json.dumps({'origin': latest.isoformat(), 'forecasts': forecast}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true', help='Download a pinned snapshot of the current public dataset before training.')
    args = parser.parse_args()
    if args.download:
        download()
    train()
