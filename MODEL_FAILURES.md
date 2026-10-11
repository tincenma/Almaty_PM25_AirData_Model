# Model failures and implications for the defense

The models improve average forecasting error in several settings, but those gains do not establish reliable forecasts for every pollution episode or reporting condition. The original US Embassy model loses to persistence during high-pollution next-day targets. The currently connected PCP #31 model loses to persistence when recent weekly history is sparse and in spring. Both findings belong in the presentation alongside the overall scores.

This discussion uses fixed held-out predictions. It does not change models, select new settings, or introduce a new fallback policy using test outcomes. All concentrations and errors below are in µg/m³. Results describe the named station and eligible observed hours, not citywide performance.

## Where the original US Embassy model fails

For 24-hour forecasts on the 2024 test set, XGBoost's overall MAE is **12.16**, compared with **13.45** for persistence: a **9.6% average improvement**. On high-pollution targets, however, XGBoost's MAE is **54.62**, compared with **47.98** for persistence: approximately **13.8% worse**, over **360 examples**.

The high-pollution group begins at **87.00**, the pre-test 90th percentile of this station's measurements. This is a statistical subgroup, not a health threshold. The reversal demonstrates why a single average error cannot establish performance during the largest pollution episodes.

Evidence: [overall scores](artifacts/test_metrics.csv), [high-pollution scores](artifacts/peak_errors.csv), and [experiment definitions](artifacts/experiment.json).

## Where the connected PCP 31 model fails

| Evaluation group | Horizon | Examples | XGBoost MAE | Persistence MAE | Interpretation |
|---|---:|---:|---:|---:|---|
| All eligible test examples | 24 hours | 2,401 | 7.12 | 7.98 | Lower average error |
| At most 75% trailing-week coverage | 24 hours | 138 | 5.17 | 2.44 | XGBoost has approximately 112% higher error |
| Spring target hours | 24 hours | 334 | 4.30 | 3.05 | Persistence is better in this season |
| October 2026 origins | 24 hours | 3 | 3.55 | 3.12 | A baseline win on a sample too small for a general conclusion |

Weekly coverage counts actual observations in the 168 hours ending at the forecast origin. At most 75% means no more than 126 observations; every eligible origin still has at least 18 measurements in the latest 24 hours. The training-time latest snapshot had **44/168** observed hours, placing it in this sparse-history group.

In the sparse-history group, 24-hour signed bias is **+4.82**, indicating overprediction on average. During high-pollution targets, signed bias is **−20.56**, indicating underprediction. Opposite errors across groups can partially cancel in the overall bias; a small overall bias does not mean individual forecasts are accurate.

PCP #31's high-pollution group uses a different, station-specific pre-test cutoff of **30.39**. Its 24-hour peak MAE is **21.03**, versus **23.01** for persistence, over **195 examples**. The model beats persistence in this subgroup but still misses peaks substantially. Do not compare the two stations' peak-error magnitudes as evidence that one model is intrinsically better: their thresholds, measurement periods, and pollution distributions differ.

Evidence: [overall scores](artifacts/current/test_metrics.csv), [sparse-history scores](artifacts/current/analysis/sparse_history_errors.csv), [seasonal scores](artifacts/current/analysis/season_errors.csv), [recent-period scores](artifacts/current/analysis/recent_period_errors.csv), and [peak scores](artifacts/current/analysis/peak_errors.csv).

## Concrete misses despite well-covered history

Times in this table use Asia/Almaty local time. The origin concentration is the persistence input at the measured hour.

| Case | Measured origin | Target time | Origin concentration | Observed target | XGBoost prediction | Absolute error | Weekly observations |
|---|---|---|---:|---:|---:|---:|---:|
| Missed next-day rise | 6 Dec 2025, 18:00 | 7 Dec 2025, 18:00 | 48.75 | 121.75 | 31.62 | 90.13 | 166/168 |
| Missed one-hour decline | 20 Dec 2025, 18:00 | 20 Dec 2025, 19:00 | 62.75 | 10.57 | 57.41 | 46.84 | 168/168 |

The first case underpredicts an observed rise of **73.00** over the next day. The second remains near the previous reading after an observed decline of **52.18** in one hour. These are failures even with almost complete weekly input history, so missing data alone cannot explain all errors. Cases were selected retrospectively from the largest misses; they illustrate behavior rather than estimate its frequency. The dataset's quality checks do not independently establish the physical cause of either episode.

Evidence: [largest held-out errors](artifacts/current/analysis/largest_errors.csv).

## What the evidence does and does not explain

Observed evidence shows that longer-horizon predictions underpredict large targets, sparse-history predictions can overpredict, and some abrupt changes are missed. The model only sees pollution history and calendar patterns; it has no weather, emission, or event inputs. Its fitted objective is squared error, and test diagnostics show many ordinary readings alongside a smaller number of high-pollution targets.

It is plausible that forecasting from recent patterns tends to miss unusual changes and that imputed historical features provide less useful information after gaps. Those are hypotheses, not demonstrated causes. Sparse coverage coincides with different calendar periods and concentration distributions, so subgroup comparisons cannot isolate a causal effect of missingness. No weather observations or source-event records were analyzed to attribute the largest misses to meteorology or emissions.

## How strong are the reported improvements

The paired seven-calendar-day block bootstrap gives the following approximate 95% intervals for the MAE advantage over persistence. A positive advantage means lower XGBoost error.

| Horizon | Mean MAE advantage | Approximate 95% interval |
|---|---:|---|
| 1 hour | 0.09 | −0.04 to 0.24 |
| 6 hours | 2.85 | 1.41 to 4.30 |
| 24 hours | 0.86 | −0.04 to 1.64 |

The six-hour result has the clearest support under this procedure. The one- and 24-hour intervals include zero; their measured average gains are not clear evidence of improvement under this analysis. Only 19 observed weekly blocks are available, and reporting gaps and nonstationarity limit the intervals. These are intervals for aggregate error differences, not uncertainty bounds around tomorrow's prediction.

Summer has **no held-out PCP #31 examples**. October has **20, 20, and 3** examples at the 1-, 6-, and 24-hour horizons. These data do not support claims of all-season or robust current next-day accuracy.

Evidence: [paired uncertainty comparisons](artifacts/current/analysis/paired_block_bootstrap.csv), [analysis definitions](artifacts/current/analysis/summary.json), and [recent-period results](artifacts/current/analysis/recent_period_errors.csv).

## Implications and next experiments

The app already displays measurement time, target time, daily and weekly input coverage, and reporting-delay warnings. It blocks forecasts with fewer than 18 observed hours in the latest day. Those checks make data limitations visible; they do not solve peak errors or guarantee accuracy. A station-level point forecast should not be presented as a validated public health alert.

The following are proposed research steps, not implemented or validated improvements:

1. Collect a new, sufficiently continuous evaluation period covering seasons, pollution episodes, and reporting gaps. Keep it untouched while developing changes.
2. Test a predefined coverage-based fallback against persistence on that new period. Do not deploy a switch solely because it looks better on the subgroup results above.
3. Evaluate uncertainty intervals calibrated on separate validation data, reporting their coverage during peaks and sparse history.
4. Test weather and other explanatory inputs whose values are actually available at the forecast origin. Reevaluate average, peak, and missing-history performance together.

## Suggested explanation during the defense

Our models improve average error, but we found important failures. In the US Embassy experiment, the 24-hour model is about 14% worse than persistence during high-pollution episodes, despite an improvement overall. At PCP #31, the 24-hour model also loses to persistence when weekly history is sparse: MAE is 5.17 versus 2.44. It can miss large rises even with complete history. The strongest improvement is at six hours; the one- and 24-hour uncertainty comparisons include no improvement. We therefore present the app as a station-level research forecast, show input freshness and coverage, and do not claim reliable health alerts or all-season live accuracy. Any model changes require a new untouched test period.
