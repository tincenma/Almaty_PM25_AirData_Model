# Current-station PM2.5 training results

The extended [held-out analysis](analysis/report.md) adds seasonal, monthly, pollution-peak, missing-history, and recent-period comparisons, weekly-block uncertainty estimates, largest misses, and five figures. It shows that the overall gains do not hold in every subgroup: sparse-history next-day forecasts and spring forecasts can be worse than persistence. Summer has no held-out examples. One- and 24-hour average gains are not clearly established by the paired weekly-block bootstrap used in this analysis.

Three XGBoost models were trained for KazHydroMet PCP #31 (`kgmt_27`) in Almaty. Station selection compared currently reporting stations and selected the one with the most usable observed history. The three-year hourly grid contains 17,246 observed hours (65.6% coverage).

| Forecast horizon | XGBoost test MAE (µg/m³) | Persistence test MAE | Improvement over persistence | Test examples |
|---|---:|---:|---:|---:|
| 1 hour | 2.94 | 3.03 | 3.1% | 2,491 |
| 6 hours | 6.33 | 9.18 | 31.0% | 2,485 |
| 24 hours | 7.12 | 7.98 | 10.8% | 2,401 |

Ridge and two XGBoost configurations were compared on chronological validation data. XGBoost with 350 trees and depth 5 won at every horizon. Evaluation models were fitted only on observations whose target precedes the test boundary of 26 September 2025, 06:00 UTC. Test examples extend through October 2026 but contain long calendar gaps. Final forecasting models were refitted on all available labeled examples after independent evaluation.

## Latest measured-hour forecast

Origin: **10 October 2026, 13:00 Almaty time** (08:00 UTC). Measured PM2.5: **3.87 µg/m³**.

| Target time in Almaty | Predicted PM2.5 (µg/m³) |
|---|---:|
| 10 October 2026, 14:00 | 4.73 |
| 10 October 2026, 19:00 | 5.66 |
| 11 October 2026, 13:00 | 9.77 |

The forecast origin is the latest measured hour, not the current wall-clock time. The first forecast target may already be in the past when this report is viewed.

## Limits

The project-wide [model failure discussion](../../MODEL_FAILURES.md) explains the baseline losses, peak underprediction, concrete missed rises and declines, and uncertainty in average gains. It compares both experiments and separates observed failures from possible causes.

The station has 24 observed hours in the latest day but only 44 in the trailing 168 hours. Missing history is handled with training-set median imputation and missingness indicators; targets remain actual observations. Most test observations precede the sparse current reporting regime. Overall test MAE must not be interpreted as demonstrated accuracy for today's sparse inputs. Forecasts describe this monitoring location, not city-wide air quality.

The app opens on Latest forecast and runs these newly trained pipelines against the latest available PCP #31 observations. Its refresh control downloads updated public measurements without retraining. The original US Embassy models remain available in the Historical replay view.

## Reproduction and outputs

Run `backend/.venv/Scripts/python.exe -m backend.train_current` from the project root to reproduce this experiment using the checksum-verified frozen snapshot and recorded station, seed, candidate settings and split dates. Reproduction does not depend on today's date. Use `--mode update` to download fresh data and train a new experiment with station freshness checks. Each run saves its own snapshot and manifest under `artifacts/<mode>/<UTC run ID>/`; it does not replace the deployed models. See the root README for custom snapshot/reference and output options. Dataset commit: `06f3772f7ad5000032d2d31592c88a4311276aa0`. SHA-256: `538ab2f4750adfa7c65b7f2dd106f5729bc46212016c57cc9965c0ae77b325f9`.

The experiment manifest, station ranking, validation metrics, test metrics, test predictions, evaluation pipelines, final forecasting pipelines and latest forecast are saved alongside this report.
