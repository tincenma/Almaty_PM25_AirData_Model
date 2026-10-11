"""Publication figures from saved evidence; no model fitting or data refresh."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'paper' / 'figures'
OUT.mkdir(exist_ok=True)
ANALYSIS = ROOT / 'artifacts/current/analysis'
plt.rcParams.update({'font.family': 'Times New Roman', 'font.size': 12,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.titlesize': 12, 'axes.labelsize': 12,
                     'legend.fontsize': 12, 'figure.dpi': 150, 'savefig.dpi': 300})
GREEN, GRAY = '#216657', '#AEBAB4'

def save(fig, name):
    fig.savefig(OUT / name, bbox_inches='tight', facecolor='white')
    plt.close(fig)

def bars(ax, labels, first, second, counts=None):
    x = np.arange(len(labels))
    ax.bar(x-.18, first, width=.36, label='XGBoost', color=GREEN)
    ax.bar(x+.18, second, width=.36, label='Persistence', color=GRAY)
    ax.set_xticks(x, labels)
    ax.set_ylim(bottom=0)
    ax.set_axisbelow(True)
    ax.grid(axis='y', color='#E4E8E5', linewidth=.6)
    if counts is not None:
        bound = max(max(first), max(second))
        ax.set_ylim(0, bound*1.3)
        for pos, n in zip(x, counts):
            ax.text(pos, bound*1.16, f'n = {n:,}', ha='center', va='bottom')

monthly = pd.read_csv(ANALYSIS / 'monthly_data_coverage.csv')
monthly['month'] = pd.to_datetime(monthly.month, utc=True)
fig, ax = plt.subplots(figsize=(6.5, 2.7), layout='constrained')
ax.bar(monthly.month, monthly.coverage_pct, width=22, color=GREEN)
ax.set_ylim(0, 105)
ax.set_ylabel('Observed hours (%)')
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.set_axisbelow(True)
ax.grid(axis='y', color='#E4E8E5')
save(fig, '01_data_coverage.png')

fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.1), layout='constrained', sharey=True)
for ax, relative, title in zip(axes, ('artifacts', 'artifacts/current'), ('US Embassy', 'PCP #31')):
    metrics = pd.read_csv(ROOT / relative / 'test_metrics.csv').set_index(['model','horizon_hours'])
    bars(ax, ['1 h','6 h','24 h'],
         [metrics.loc[('XGBoost', h), 'MAE'] for h in (1,6,24)],
         [metrics.loc[('Persistence', h), 'MAE'] for h in (1,6,24)])
    ax.set_title(title)
axes[0].set_ylabel('MAE (µg/m³)')
axes[0].legend(loc='upper left', frameon=False, fontsize=10)
save(fig, '02_overall_mae.png')

confidence = pd.read_csv(ANALYSIS / 'paired_block_bootstrap.csv')
confidence = confidence.loc[confidence.baseline.eq('Persistence')].sort_values('horizon_hours')
fig, ax = plt.subplots(figsize=(6.5, 2.7), layout='constrained')
positions = np.arange(3)
ax.errorbar(confidence.MAE_gain, positions,
            xerr=np.vstack([confidence.MAE_gain-confidence.lower_95,
                            confidence.upper_95-confidence.MAE_gain]),
            fmt='o', color=GREEN, ecolor=GREEN, capsize=5, markersize=6)
ax.axvline(0, color='#B46B3A', linestyle='--', linewidth=1)
ax.set_yticks(positions, ['1 hour','6 hours','24 hours'])
ax.invert_yaxis()
ax.set_xlabel('Persistence MAE minus XGBoost MAE (µg/m³)')
ax.set_xlim(-.4, 4.6)
ax.grid(axis='x', color='#E4E8E5')
save(fig, '03_uncertainty.png')

season = pd.read_csv(ANALYSIS / 'season_errors.csv')
season = season.loc[season.horizon_hours.eq(24)].set_index(['model','season'])
labels = ['Autumn','Winter','Spring']
fig, ax = plt.subplots(figsize=(6.5, 3), layout='constrained')
bars(ax, labels, [season.loc[('XGBoost', c), 'MAE'] for c in labels],
     [season.loc[('Persistence', c), 'MAE'] for c in labels],
     [int(season.loc[('XGBoost', c), 'samples']) for c in labels])
ax.set_ylabel('24-hour MAE (µg/m³)')
ax.legend(frameon=False, loc='lower center', bbox_to_anchor=(.5, 1.02), ncol=2)
save(fig, '04_season_errors.png')

coverage = pd.read_csv(ANALYSIS / 'coverage_errors.csv')
coverage = coverage.loc[coverage.horizon_hours.eq(24)].set_index(['model','coverage_group'])
labels = ['0–25%', '25–75%', '75–100%']
fig, ax = plt.subplots(figsize=(6.5, 3), layout='constrained')
bars(ax, labels, [coverage.loc[('XGBoost', c), 'MAE'] for c in labels],
     [coverage.loc[('Persistence', c), 'MAE'] for c in labels],
     [int(coverage.loc[('XGBoost', c), 'samples']) for c in labels])
ax.set_ylabel('24-hour MAE (µg/m³)')
ax.set_xlabel('Observed hours in the trailing 168 hours')
ax.legend(frameon=False, loc='lower center', bbox_to_anchor=(.5, 1.02), ncol=2)
save(fig, '05_coverage_errors.png')

original = pd.read_csv(ROOT / 'artifacts/peak_errors.csv')
current = pd.read_csv(ANALYSIS / 'peak_errors.csv')
fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.1), layout='constrained')
original = original.loc[original.horizon_hours.eq(24)].copy()
original['group'] = np.where(original.concentration_group.str.startswith('High'), 'Peaks', 'Below cutoff')
current = current.loc[current.horizon_hours.eq(24)].copy()
current['group'] = np.where(current.pollution_group.eq('High pollution'), 'Peaks', 'Below cutoff')
for ax, frame, title in zip(axes, (original,current), ('US Embassy\nCutoff 87.00 µg/m³', 'PCP #31\nCutoff 30.39 µg/m³')):
    values = frame.set_index(['model','group'])
    bars(ax, ['Below cutoff','Peaks'], [values.loc[('XGBoost', c), 'MAE'] for c in ('Below cutoff','Peaks')],
         [values.loc[('Persistence', c), 'MAE'] for c in ('Below cutoff','Peaks')])
    ax.set_title(title)
    ax.set_ylabel('24-hour MAE (µg/m³)')
axes[0].legend(frameon=False, loc='upper left', fontsize=10)
save(fig, '06_peak_errors.png')
