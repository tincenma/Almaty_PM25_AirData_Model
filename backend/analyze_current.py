"""Post-hoc diagnostics for fixed held-out PCP #31 predictions; no model fitting."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backend.app.features import make_features

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'artifacts' / 'current'
OUTPUT = DIRECTORY / 'analysis'
HORIZONS = (1, 6, 24)
MODELS = {'XGBoost': 'predicted', 'Persistence': 'persistence', 'Same hour yesterday': 'seasonal'}


def grouped_errors(frame, dimensions):
    rows = []
    for keys, group in frame.groupby(dimensions, observed=True, dropna=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        for name, column in MODELS.items():
            residual = group[column] - group.target
            rows.append({**dict(zip(dimensions, keys)), 'model': name, 'samples': len(group),
                         'MAE': float(residual.abs().mean()), 'RMSE': float(np.sqrt((residual ** 2).mean())),
                         'bias': float(residual.mean()), 'p90_absolute_error': float(residual.abs().quantile(.9))})
    return pd.DataFrame(rows)


def table(frame, columns):
    selected = frame[columns].copy()
    for column in selected.select_dtypes('number'):
        if not pd.api.types.is_integer_dtype(selected[column]):
            selected[column] = selected[column].map(lambda value: f'{value:.2f}')
    return '| ' + ' | '.join(columns) + ' |\n|' + '|'.join(['---'] * len(columns)) + '|\n' + '\n'.join(
        '| ' + ' | '.join(str(value) for value in row) + ' |' for row in selected.itertuples(index=False, name=None))


def comparison_plot(metrics, category, filename, title, order=None):
    categories = order or list(metrics[category].drop_duplicates())
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True, constrained_layout=True)
    for axis, horizon in zip(axes, HORIZONS):
        part = metrics.loc[metrics.horizon_hours.eq(horizon)]
        for offset, (name, color) in enumerate([('XGBoost', '#315f50'), ('Persistence', '#a5ad72')]):
            values = part.loc[part.model.eq(name)].set_index(category).reindex(categories)
            axis.bar(np.arange(len(categories)) + (offset - .5) * .36, values.MAE, .36, label=name, color=color)
        axis.set_xticks(range(len(categories)), categories, rotation=25, ha='right', fontsize=8)
        axis.set_title(f'{horizon}-hour forecast')
        axis.grid(axis='y', alpha=.2)
    axes[0].set_ylabel('MAE (µg/m³)')
    axes[-1].legend(fontsize=8)
    fig.suptitle(title)
    fig.savefig(OUTPUT / filename, dpi=160)
    plt.close(fig)


def analyze():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((DIRECTORY / 'experiment.json').read_text(encoding='utf-8'))
    if any(settings['family'] != 'XGBoost' for settings in manifest['selected_models'].values()):
        raise ValueError('These diagnostics label the fitted model XGBoost; update model labels for a different experiment.')
    source = ROOT / 'data' / 'current_training_pm25.csv.gz'
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['dataset']['sha256']:
        raise ValueError('Training snapshot differs from experiment provenance.')
    raw = pd.read_csv(source, compression='gzip')
    raw = raw.loc[raw.station_id.eq(manifest['station']['station_id'])].copy()
    raw['datetime_utc'] = pd.to_datetime(raw.datetime_utc, utc=True, errors='coerce')
    raw['value_ugm3'] = pd.to_numeric(raw.value_ugm3, errors='coerce')
    raw = raw.dropna(subset=['datetime_utc', 'value_ugm3']).loc[lambda df: df.value_ugm3.ge(0)]
    measured = raw.groupby('datetime_utc').value_ugm3.mean().sort_index()
    latest = measured.index.max()
    series = measured.reindex(pd.date_range(max(measured.index.min(), latest - pd.Timedelta(days=3 * 365)), latest, freq='h'))
    features = make_features(series)
    frame = pd.read_csv(DIRECTORY / 'test_predictions.csv')
    frame['origin'] = pd.to_datetime(frame.origin, utc=True)
    frame['target_time'] = frame.origin + pd.to_timedelta(frame.horizon_hours, unit='h')
    actual = series.reindex(pd.DatetimeIndex(frame.target_time)).to_numpy()
    if not np.allclose(frame.target, actual):
        raise ValueError('Saved test targets do not match the immutable measurements.')
    if not frame.origin.ge(pd.Timestamp(manifest['test_start'])).all():
        raise ValueError('Prediction table contains pre-test origins.')
    frame['observed_168h'] = features.observed_168h.reindex(frame.origin).to_numpy().astype(int)
    frame['observed_24h'] = features.observed_24h.reindex(frame.origin).to_numpy().astype(int)
    frame['missing_features'] = features.isna().sum(axis=1).reindex(frame.origin).to_numpy().astype(int)
    frame['coverage_group'] = pd.cut(frame.observed_168h, [-1, 42, 126, 168], labels=['0–25%', '25–75%', '75–100%'])
    frame['missing_group'] = pd.cut(frame.missing_features, [-1, 0, 5, 100], labels=['None', '1–5', '6 or more'])
    local_target = frame.target_time.dt.tz_convert('Asia/Almaty')
    frame['season'] = local_target.dt.month.map({12:'Winter',1:'Winter',2:'Winter',3:'Spring',4:'Spring',5:'Spring',6:'Summer',7:'Summer',8:'Summer',9:'Autumn',10:'Autumn',11:'Autumn'})
    frame['month'] = frame.origin.dt.tz_convert('Asia/Almaty').dt.strftime('%Y-%m')
    frame['year'] = frame.origin.dt.year
    frame['target_hour'] = local_target.dt.hour
    cutoff = float(series.loc[series.index < pd.Timestamp(manifest['test_start'])].quantile(.9))
    frame['pollution_group'] = np.where(frame.target.ge(cutoff), 'High pollution', 'Below cutoff')
    frame['absolute_error'] = (frame.predicted - frame.target).abs()
    frame['signed_error'] = frame.predicted - frame.target
    frame.to_csv(OUTPUT / 'diagnostic_predictions.csv', index=False)
    outputs = {}
    for name, dimension in [('season_errors', 'season'), ('monthly_errors', 'month'), ('year_errors', 'year'),
                            ('coverage_errors', 'coverage_group'), ('missing_feature_errors', 'missing_group'),
                            ('peak_errors', 'pollution_group'), ('hour_errors', 'target_hour')]:
        metrics = grouped_errors(frame, ['horizon_hours', dimension])
        metrics.to_csv(OUTPUT / f'{name}.csv', index=False)
        outputs[name] = metrics
    overall = grouped_errors(frame, ['horizon_hours'])
    overall.to_csv(OUTPUT / 'overall_errors.csv', index=False)
    recent_month = frame.month.max()
    recent = outputs['monthly_errors'].loc[outputs['monthly_errors'].month.eq(recent_month)]
    recent.to_csv(OUTPUT / 'recent_period_errors.csv', index=False)
    sparse = grouped_errors(frame.loc[frame.observed_168h.le(126)], ['horizon_hours'])
    sparse.to_csv(OUTPUT / 'sparse_history_errors.csv', index=False)
    misses = pd.concat([group.nlargest(10, 'absolute_error') for _, group in frame.groupby('horizon_hours')], ignore_index=True)
    misses[['horizon_hours', 'origin', 'target_time', 'target', 'predicted', 'persistence', 'seasonal', 'absolute_error', 'signed_error', 'observed_168h', 'missing_features']].to_csv(OUTPUT / 'largest_errors.csv', index=False)
    monthly = series.to_frame('pm25').resample('MS').agg(observed=('pm25', 'count'), total=('pm25', 'size'), mean_pm25=('pm25', 'mean'))
    monthly['coverage_pct'] = monthly.observed / monthly.total * 100
    monthly.to_csv(OUTPUT / 'monthly_data_coverage.csv', index_label='month')
    # Paired weekly-block bootstrap preserves dependence within seven calendar days.
    rng = np.random.default_rng(manifest['random_seed'])
    confidence = []
    for horizon in HORIZONS:
        part = frame.loc[frame.horizon_hours.eq(horizon)].copy()
        part['block'] = ((part.origin - pd.Timestamp(manifest['test_start'])).dt.total_seconds() // (7 * 86400)).astype(int)
        block_count = part.block.nunique()
        choices = rng.integers(0, block_count, size=(2000, block_count))
        for baseline in ('Persistence', 'Same hour yesterday'):
            part['gain'] = (part[MODELS[baseline]] - part.target).abs() - part.absolute_error
            blocks = part.groupby('block').agg(gain_sum=('gain', 'sum'), samples=('gain', 'size'))
            gains = blocks.gain_sum.to_numpy()[choices].sum(axis=1) / blocks.samples.to_numpy()[choices].sum(axis=1)
            confidence.append({'horizon_hours': horizon, 'baseline': baseline, 'samples': len(part), 'blocks': len(blocks),
                               'MAE_gain': float(part.gain.mean()), 'lower_95': float(np.quantile(gains, .025)),
                               'upper_95': float(np.quantile(gains, .975))})
    confidence = pd.DataFrame(confidence)
    confidence.to_csv(OUTPUT / 'paired_block_bootstrap.csv', index=False)
    plt.rcParams.update({'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), constrained_layout=True)
    daily = series.resample('D').mean().where(series.resample('D').count().ge(18))
    axes[0].plot(daily.index, daily.values, color='#315f50', linewidth=1)
    axes[0].set_ylabel('Daily mean PM2.5 (µg/m³)')
    axes[0].set_title('PCP #31 observations; daily means require 18 measured hours')
    axes[1].bar(monthly.index, monthly.coverage_pct, width=20, color='#899955')
    axes[1].set_ylabel('Observed hours (%)')
    axes[1].set_ylim(0, 105)
    axes[1].set_title('Monthly coverage; missing hours remain missing')
    for axis in axes:
        axis.axvline(pd.Timestamp(manifest['test_start']), color='#a7794b', linestyle='--', label='Test begins')
        axis.grid(axis='y', alpha=.2)
    axes[0].legend(fontsize=8)
    fig.savefig(OUTPUT / 'data_coverage.png', dpi=160)
    plt.close(fig)
    comparison_plot(outputs['season_errors'], 'season', 'seasonal_errors.png', 'Held-out MAE by target season', ['Autumn', 'Winter', 'Spring', 'Summer'])
    comparison_plot(outputs['coverage_errors'], 'coverage_group', 'coverage_errors.png', 'Held-out MAE by observed trailing-week coverage', ['0–25%', '25–75%', '75–100%'])
    comparison_plot(outputs['peak_errors'], 'pollution_group', 'peak_errors.png', f'Held-out MAE by pollution level; pre-test 90th percentile = {cutoff:.2f} µg/m³', ['Below cutoff', 'High pollution'])
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
    for axis, horizon in zip(axes, HORIZONS):
        part = frame.loc[frame.horizon_hours.eq(horizon)]
        cells = axis.hexbin(part.target, part.predicted, gridsize=25, mincnt=1, cmap='viridis', bins='log')
        fig.colorbar(cells, ax=axis, label='Cell count', shrink=.8)
        bound = max(part.target.max(), part.predicted.max())
        axis.plot([0, bound], [0, bound], '--', color='#a7794b')
        axis.set_title(f'{horizon}-hour forecast, n={len(part):,}')
        axis.set_xlabel('Observed PM2.5 (µg/m³)')
        axis.set_ylabel('Predicted PM2.5 (µg/m³)')
    fig.savefig(OUTPUT / 'predicted_vs_observed.png', dpi=160)
    plt.close(fig)
    xgb = overall.loc[overall.model.eq('XGBoost')]
    peaks = outputs['peak_errors'].loc[outputs['peak_errors'].pollution_group.eq('High pollution')]
    thin = outputs['coverage_errors'].loc[outputs['coverage_errors'].coverage_group.eq('0–25%')]
    summary = {'station_id': manifest['station']['station_id'], 'dataset_sha256': manifest['dataset']['sha256'],
               'peak_cutoff_ugm3': cutoff, 'recent_month': recent_month, 'bootstrap_iterations': 2000,
               'bootstrap_block_days': 7, 'test_examples': len(frame),
               'missing_seasons': sorted(set(['Winter', 'Spring', 'Summer', 'Autumn']) - set(frame.season)),
               'analysis_changes_models': False}
    (OUTPUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    narrative = [
        '# Extended held-out analysis for PCP 31\n',
        'This analysis uses the immutable training snapshot and fixed held-out evaluation predictions. No models were trained, parameters changed, or deployment predictions used as test results. All errors are in µg/m³. Positive bias means overprediction; negative bias means underprediction.\n',
        'The clearest result is the six-hour improvement. The paired weekly-block interval versus persistence excludes zero at six hours, but includes zero at one and 24 hours. Winter errors are larger than autumn or spring errors, summer is absent from the test set, and spring MAE is worse than persistence at all three horizons. Sparse-history examples also expose a next-day weakness despite the lower overall average error.\n',
        '## Overall performance\n', table(xgb, ['horizon_hours', 'samples', 'MAE', 'RMSE', 'bias', 'p90_absolute_error']),
        '\nCompare MAE to both persistence and the same-hour-yesterday baseline. The latter equals persistence at the 24-hour horizon, so those are not independent benchmarks.\n',
        '## Data coverage\n', '![](data_coverage.png)\n',
        f'The three-year grid contains {series.count():,} observations out of {len(series):,} hours ({series.notna().mean():.1%}). The latest month represented in the test predictions is {recent_month}. Calendar gaps are not evidence of zero pollution. Selection excludes unobserved targets and poorly covered days, so these scores describe eligible examples rather than continuous operational coverage.\n',
        'The first and last coverage months are partial, bounded by the experiment grid rather than full calendar months. Monthly CSV denominators show the number of hours actually covered by that grid.\n',
        '## Seasonal errors\n', table(outputs['season_errors'].loc[outputs['season_errors'].model.eq('XGBoost')], ['horizon_hours', 'season', 'samples', 'MAE', 'RMSE', 'bias']),
        '\n![](seasonal_errors.png)\n',
        f'Seasons are assigned using target time in Asia/Almaty. Unrepresented test seasons: {", ".join(summary["missing_seasons"]) or "none"}. Blank bars mean no eligible test examples, not zero error. Seasons have unequal sample sizes and pollution distributions; comparisons do not isolate a causal seasonal effect.\n',
        '## Pollution peaks\n',
        f'The high-pollution cutoff is the 90th percentile of observed pre-test station concentrations: **{cutoff:.2f} µg/m³**. This is a statistical threshold, not a health guideline. It is fixed without using test concentration quantiles.\n',
        table(peaks, ['horizon_hours', 'model', 'samples', 'MAE', 'RMSE', 'bias']), '\n![](peak_errors.png)\n',
        f'For high-pollution 24-hour targets, XGBoost MAE is {peaks.loc[peaks.horizon_hours.eq(24) & peaks.model.eq("XGBoost"), "MAE"].iloc[0]:.2f}, with bias {peaks.loc[peaks.horizon_hours.eq(24) & peaks.model.eq("XGBoost"), "bias"].iloc[0]:.2f}. This indicates substantial underprediction during large episodes even though its peak MAE is lower than persistence.\n',
        'Compare the high-pollution subgroup to the overall average and baselines. A lower overall MAE does not guarantee better forecasts during pollution episodes. Negative peak bias indicates systematic underprediction of high concentrations.\n',
        '## Missing history\n', table(thin, ['horizon_hours', 'model', 'samples', 'MAE', 'RMSE', 'bias']), '\n![](coverage_errors.png)\n',
        'Coverage groups count actual observations in the trailing 168 hours: 0–25% means at most 42 observations, 25–75% means 43–126, and 75–100% means 127–168. Daily eligibility still requires at least 18 of 24 hours. The latest inference snapshot at training had 44/168 observations, putting it in the middle group. These comparisons are observational: pollution levels, calendar period, and missingness change together. They do not prove that missing data causes the differences. The separate missing_feature_errors.csv groups examples by missing feature count before imputation.\n',
        'Aggregating all examples with at most 75% weekly coverage gives the following comparison. The 24-hour model loses to persistence in both individual sparse-coverage bins. This failure must be presented alongside overall gains.\n',
        table(sparse, ['horizon_hours', 'model', 'samples', 'MAE', 'RMSE', 'bias']),
        '## Recent period\n', table(recent, ['horizon_hours', 'model', 'samples', 'MAE', 'RMSE', 'bias']),
        '\nThe most recent month is a very small, narrow sample. In particular, three 24-hour examples cannot establish robust next-day performance or accuracy across pollution regimes. Monthly and yearly CSVs allow the commission to inspect where the overall results come from.\n',
        '## Paired uncertainty in baseline improvement\n', table(confidence, ['horizon_hours', 'baseline', 'samples', 'blocks', 'MAE_gain', 'lower_95', 'upper_95']),
        '\nPositive MAE gain means XGBoost has lower absolute error than the baseline. The approximate 95% interval resamples 2,000 sets of seven-calendar-day blocks with replacement and compares forecasts on identical test rows. Intervals spanning zero do not clearly establish an improvement under this procedure. Gaps, unequal block sizes, few blocks, nonstationarity, and dependence beyond one week limit interpretation. These intervals describe aggregate error differences; they are not prediction intervals for tomorrow.\n',
        '## Largest misses\n', table(misses.groupby('horizon_hours').head(3), ['horizon_hours', 'origin', 'target_time', 'target', 'predicted', 'absolute_error', 'signed_error', 'observed_168h']),
        '\nTimes in this table are UTC. largest_errors.csv saves ten misses per horizon. Inspect whether the model lags rapid rises, overpredicts after declines, or misses large episodes. These cases are selected retrospectively and are not representative random examples.\n',
        '![](predicted_vs_observed.png)\n',
        '## Interpretation for the defense\n',
        'See the project-wide [model failure discussion](../../../MODEL_FAILURES.md) for the original US Embassy peak-error reversal, PCP #31 baseline losses, concrete misses, interpretation, and a suggested defense explanation.\n',
        'Present average gains together with subgroup failures and sample counts. Explain that these are station-level PM2.5 point forecasts from the latest published measured hour, with daily publication delays and sparse recent history. Do not claim citywide, continuous live, health-alert, or all-season validation. No weather is used. Any future changes motivated by these test diagnostics require a new untouched evaluation period; do not reuse this test set for tuning.\n',
        '## Reproduction\n',
        'Run `backend/.venv/Scripts/python.exe -m backend.analyze_current` from the project root. This uses data/current_training_pm25.csv.gz, artifacts/current/experiment.json, and artifacts/current/test_predictions.csv. Refreshing the inference snapshot does not change these analysis inputs. Install backend/requirements-analysis.txt for plotting dependencies. Outputs include machine-readable subgroup metrics, enriched test predictions, confidence comparisons, five figures, and this report.\n',
    ]
    (OUTPUT / 'report.md').write_text('\n'.join(narrative), encoding='utf-8')


if __name__ == '__main__':
    analyze()
