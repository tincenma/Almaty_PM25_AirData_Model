# Short term PM2 5 forecasting in Almaty using open station data

## Abstract

This study develops and evaluates a reproducible system for forecasting station-level hourly fine particulate matter concentrations in Almaty, Kazakhstan. Two experiments use versioned AirData.kz observations: a historical US Embassy benchmark with a 2024 test period and an updated KazHydroMet PCP #31 experiment. Separate models predict concentrations one, six and 24 hours after an observed origin using pollution history, rolling summaries, observation counts and cyclic calendar features. Ridge regression and XGBoost are selected through chronological validation and compared with persistence and daily seasonal baselines. On the PCP #31 test set, selected XGBoost models achieve mean absolute errors of 2.94, 6.33 and 7.12 µg/m³, respectively. The six-hour improvement over persistence is 2.85 µg/m³, with an approximate paired weekly-block 95% interval of 1.41–4.30. Corresponding one- and 24-hour intervals include zero. Subgroup analysis identifies substantial peak underprediction, weaker spring performance and a reversal of average gains under sparse weekly history. A React and TypeScript interface and FastAPI backend expose historical replay and forecasts from the latest published measured hour, including timestamp and coverage warnings. Frozen snapshots, checksums and separate reproduction and update modes support repeatable evaluation. The results support a practical research prototype, while limited recent coverage and station-specific evaluation constrain claims about continuous operational reliability.

Keywords: PM2.5; Almaty; air quality forecasting; XGBoost; chronological validation; missing data; reproducibility

## 1 Introduction

Open monitoring data make local pollution forecasting accessible to researchers and students, but a working prediction interface alone does not establish forecast reliability. An evaluation must establish which observations were available at the prediction origin, whether training and test periods are separated, and whether a learned model improves on simple alternatives. Missing observations and publication delays further affect the relationship between a displayed forecast and the current environment.

This work investigates hourly PM2.5 forecasting for individual Almaty monitoring stations. PM2.5 denotes fine particulate matter with an aerodynamic diameter of approximately 2.5 micrometres or smaller; the prediction target is concentration in micrograms per cubic metre. The system predicts a future hourly station concentration rather than a citywide average, a daily average or a composite air quality index.

The research questions are whether history and calendar features improve forecasts over persistence, how performance changes with horizon and data coverage, and how an application can communicate the actual temporal basis of its forecasts. The contribution is an integrated empirical and engineering study: chronological benchmarks, reproducible data handling, deployment of the fitted feature pipeline, and explicit investigation of conditions in which the selected model fails. No new learning algorithm is proposed.

## 2 Background and methodological context

Persistence and seasonal naïve forecasting provide important reference methods because complex models must demonstrate value beyond repeating recent observations. A persistence forecast repeats the origin value, while a seasonal forecast repeats the corresponding position in an earlier cycle. Forecast accuracy should be measured on observations withheld from fitting and selection; absolute and squared error summaries answer different questions about forecast quality (Hyndman & Athanasopoulos, 2021).

Ridge regression is a linear estimator with an L2 penalty on coefficients, offering a computationally inexpensive comparison model (scikit-learn developers, n.d.). XGBoost implements regularized gradient tree boosting and provides an efficient approach for structured feature representations (Chen & Guestrin, 2016). These methods allow a direct comparison between linear relationships and nonlinear combinations of historical concentration and calendar features. Their use here does not establish superiority over untested neural, spatial or meteorological models.

AirData.kz publishes harmonized observations from government and independent monitoring networks and describes a daily update process (AirData.kz, n.d.). This supports a workflow based on public snapshots, although publication frequency should not be confused with continuous sensor delivery. The present experiments use station measurements from the repository, not its citywide daily summaries.

## 3 Data and preprocessing

### 3.1 Historical and updated experiments

The historical experiment uses the Almaty US Embassy station, identifier oaq_25903. Its analysis begins on 1 April 2020 UTC. Training ends before 1 January 2023, validation occupies 2023 and testing occupies 2024. The dataset is pinned to repository commit 119cf2c278def3129f14cef9380cced9de1f3161. A recorded SHA-256 identifies the exact compressed input file.

The updated experiment uses KazHydroMet PCP #31, identifier kgmt_27, from commit 06f3772f7ad5000032d2d31592c88a4311276aa0. Its latest recorded measurement is 10 October 2026 at 08:00 UTC. The grid extends back at most three times 365 days from that measurement and contains 26,281 hourly positions, of which 17,246 are observed, giving 65.6% coverage. The latest 24 hours contain 24 observations, but the latest 168 hours contain only 44. Adequate daily coverage therefore coexists with sparse weekly history.

The experiments involve different stations, periods and concentration distributions. Their errors are reported separately. Lower absolute errors at PCP #31 cannot be interpreted as evidence that its model is intrinsically better than the US Embassy model, and the experiments do not constitute transfer learning between stations.

### 3.2 Cleaning and missing observations

The training workflow parses timestamps as UTC and concentrations as numeric values. Rows without valid station identifiers, timestamps or concentrations are removed, and negative concentrations are excluded. Multiple valid values for a station and timestamp are averaged. Each selected series is reindexed to an hourly grid so a missing timestamp remains a missing hour rather than shifting subsequent lag values.

Historical feature gaps are handled with median imputation and missingness indicators. Imputation parameters are fitted within each training pipeline rather than estimated from the full dataset. Targets are never imputed. This preserves a distinction between supplying incomplete historical inputs and inventing evaluation outcomes.

For PCP #31, a prediction origin requires an observed current value and at least 18 observed hours in the trailing 24 hours. A training or evaluation row additionally requires the target and daily seasonal baseline to be observed. The historical experiment also requires the 168-hour lag to be observed. These eligibility rules restrict the reported scores to usable examples; they do not measure accuracy across every calendar hour.

### 3.3 Selection of a reporting station

In update mode, candidate stations require a latest reading no more than 24 hours old, at least 6,000 observed training hours, a grid of at least 180 days and at least 18 readings in the latest 24 hours. Eligible stations are ranked by observed history, overall coverage and recent coverage. This procedure selected PCP #31 for the recorded updated experiment. Selection reflects reporting availability and training support, and does not establish spatial representativeness for all Almaty residents.

## 4 Forecasting methods and evaluation design

### 4.1 Features and direct horizons

Separate estimators predict the concentrations one, six and 24 hours after each origin. The 28 inputs include current concentration; lags of 1, 2, 3, 6, 12, 24, 48, 72 and 168 hours; and trailing means, standard deviations and observation counts over 6, 24, 72 and 168 hours. Six additional features encode hour of day, weekday and day of year as sine and cosine pairs using Asia/Almaty local time.

All pollution features use observations at or before the origin. Rolling means and standard deviations require at least the greater of two observations or one quarter of the window length. Count features retain information about incomplete history. UTC indexing preserves temporal alignment, while timezone conversion supplies local calendar features. Weather, emissions, traffic and neighbouring station observations are not included.

### 4.2 Models and baselines

Both model families use a median imputer with missingness indicators. Ridge additionally standardizes its inputs. For PCP #31, Ridge candidates use penalty strengths 1, 10 and 100. XGBoost candidates use either 200 trees with maximum depth 3 and learning rate 0.05, or 350 trees with maximum depth 5 and learning rate 0.04. Both use regularization parameter 10, row subsampling 0.85, column subsampling 0.9, histogram tree construction, four worker threads and random seed 42. Predictions are clipped below at zero.

The historical quick-run search uses Ridge penalty strengths 1 and 100 and the same two XGBoost configurations. Candidate selection minimizes validation MAE. PCP #31 selects the 350-tree configuration at all three horizons. The historical experiment selects this configuration at one hour and the 200-tree configuration at six and 24 hours.

Persistence predicts the origin concentration at every horizon. The daily seasonal baseline predicts the observation 24 hours before the target: 23 hours before the origin for a one-hour forecast and 18 hours before the origin for a six-hour forecast. At a 24-hour horizon, the seasonal baseline equals persistence. Its identical next-day scores therefore do not provide an independent benchmark.

### 4.3 Chronological separation and refitting

The historical benchmark uses fixed calendar partitions. PCP #31 uses the 70th and 85th percentiles of eligible origin timestamps to set validation and test boundaries, respectively. Its recorded validation begins on 6 June 2025 at 05:00 UTC and testing begins on 26 September 2025 at 06:00 UTC. Quantile boundaries accommodate substantial calendar gaps but produce unequal calendar durations and seasonal representation.

Rows whose targets cross a partition boundary are purged. For example, a training origin is excluded if its future target falls inside validation. Models are chosen on validation, then refitted using pre-test labelled examples for held-out evaluation. PCP #31 preserves these evaluation pipelines separately from deployment pipelines, which are subsequently refitted on all eligible labelled data. Deployment predictions are not used to calculate held-out accuracy.

This design uses a single chronological holdout rather than rolling-origin cross-validation. Test-set failure analysis is retrospective. Any model changes motivated by that analysis require a new untouched evaluation period to avoid converting the current test set into another selection set.

### 4.4 Metrics and uncertainty

Mean absolute error is the primary selection metric and summarizes the average magnitude of a miss. Root mean squared error gives greater weight to large misses. R² compares squared error with variation around the evaluation mean. MAE and RMSE are reported in µg/m³; R² is dimensionless. Bias is defined as mean predicted minus observed concentration, so negative bias indicates underprediction.

For PCP #31, uncertainty in baseline improvement is assessed using paired resampling of seven-calendar-day blocks. Each of 2,000 replicates samples blocks with replacement and compares model and baseline errors on identical rows. There are 19 blocks containing eligible test observations. The 2.5th and 97.5th percentiles form approximate 95% intervals for the MAE difference, defined as baseline MAE minus model MAE. These intervals concern average performance differences and are not intervals for individual forecasts. Unequal block sizes, gaps, nonstationarity and dependence extending beyond one week limit their interpretation.

## 5 Results

### 5.1 Historical benchmark

Table 1 reports the US Embassy test results. XGBoost reduces MAE relative to persistence by 1.9%, 22.2% and 9.6% at one, six and 24 hours. Ridge remains competitive. At one and 24 hours, Ridge has lower RMSE than XGBoost despite its higher MAE, showing that selection by MAE does not optimize every aspect of error.

Table 1. US Embassy held-out performance during 2024

| Horizon | Model | MAE | RMSE | R² |
|---|---|---|---|---|
| 1 h | Ridge | 5.49 | 10.27 | 0.875 |
| 1 h | XGBoost | 5.40 | 10.32 | 0.874 |
| 1 h | Persistence | 5.50 | 10.84 | 0.861 |
| 6 h | Ridge | 11.80 | 20.09 | 0.524 |
| 6 h | XGBoost | 11.01 | 19.75 | 0.540 |
| 6 h | Persistence | 14.15 | 27.19 | 0.128 |
| 24 h | Ridge | 12.32 | 20.75 | 0.492 |
| 24 h | XGBoost | 12.16 | 21.18 | 0.470 |
| 24 h | Persistence | 13.45 | 24.21 | 0.309 |

The history-versus-calendar validation ablation gives additional context. At six hours, XGBoost MAE decreases from 13.97 with pollution history alone to 11.66 with calendar inputs. The corresponding one-hour change is 5.12 to 5.05. At 24 hours, calendar inputs slightly worsen MAE from 11.86 to 11.97, although RMSE improves. Calendar information therefore offers horizon-dependent value. This ablation belongs to the historical experiment and was not repeated for PCP #31.

### 5.2 Updated station experiment

Table 2 reports PCP #31 performance. Relative to persistence, XGBoost reduces MAE by approximately 3.1%, 31.0% and 10.8% at one, six and 24 hours. Sample counts vary because target and seasonal observations must be available separately for each horizon. Ridge candidates were evaluated during validation, but the saved updated test results report the selected XGBoost family and the baselines.

Table 2. PCP #31 held-out performance

| Horizon | Model | Samples | MAE | RMSE | R² |
|---|---|---|---|---|---|
| 1 h | XGBoost | 2,491 | 2.94 | 5.27 | 0.829 |
| 1 h | Persistence | 2,491 | 3.03 | 5.62 | 0.805 |
| 1 h | Daily seasonal | 2,491 | 7.81 | 13.07 | −0.056 |
| 6 h | XGBoost | 2,485 | 6.33 | 9.79 | 0.408 |
| 6 h | Persistence | 2,485 | 9.18 | 15.29 | −0.443 |
| 6 h | Daily seasonal | 2,485 | 7.81 | 13.09 | −0.056 |
| 24 h | XGBoost | 2,401 | 7.12 | 10.79 | 0.298 |
| 24 h | Persistence and seasonal | 2,401 | 7.98 | 13.30 | −0.068 |

The six-hour paired MAE gain over persistence is 2.85, with an approximate 95% interval of 1.41–4.30 µg/m³. The one-hour gain is 0.09 with an interval of −0.04–0.24; the 24-hour gain is 0.86 with an interval of −0.04–1.64. Only the six-hour interval excludes zero under this procedure. Thus, positive point estimates at all horizons should not be presented as equally strong evidence of improvement.

### 5.3 Seasonal and coverage differences

PCP #31 has no eligible summer test examples. At 24 hours, XGBoost MAE is 5.84 in autumn, 12.81 in winter and 4.30 in spring, with 1,552, 515 and 334 examples, respectively. Spring persistence MAE is 3.05, outperforming XGBoost. Spring losses to persistence also occur at one and six hours. These comparisons are descriptive: seasonal differences in concentration, observation coverage and sample size occur together.

Sparse weekly history produces another important reversal. Among 138 next-day examples with at most 126 of the preceding 168 hours observed, XGBoost MAE is 5.17 compared with persistence MAE of 2.44, approximately 112% higher. Mean bias is +4.82 for XGBoost. An acceptable daily coverage check therefore does not guarantee strong next-day performance when weekly context is incomplete.

The most recent represented month, October 2026, contains 20 one-hour examples, 20 six-hour examples and only three next-day examples. Next-day MAE is 3.55 for XGBoost and 3.12 for persistence. This very small sample cannot establish robust current-condition performance.

### 5.4 Pollution peaks and concrete failures

High concentrations are defined using each station's pre-test 90th percentile, giving thresholds of 87.00 µg/m³ for the US Embassy experiment and 30.39 µg/m³ for PCP #31. These are statistical subgroup thresholds, not health guidance. Their difference prevents direct interpretation of the two peak groups as equivalent exposure regimes.

For 360 historical next-day peak targets, XGBoost MAE is 54.62 compared with 47.98 for persistence, approximately 13.8% worse. This reverses its average next-day advantage. For 195 PCP #31 next-day peak targets, XGBoost MAE is 21.03 compared with 23.01 for persistence. Nevertheless, XGBoost bias is −20.56, showing substantial peak underprediction despite its relative improvement.

One PCP #31 next-day forecast issued at 13:00 UTC on 6 December 2025 predicts 31.62 for the following day's corresponding hour, when the observed concentration is 121.75. Its absolute error is 90.13. The history contains 166 of 168 preceding hourly observations, so sparse coverage alone cannot explain this miss. Conversely, a one-hour forecast issued at 13:00 UTC on 20 December predicts 57.41 while the subsequent observation is 10.57, an overprediction of 46.84 despite complete weekly coverage. These retrospectively selected cases show failures during both rises and declines; they are not representative random samples.

## 6 Application and reproducibility

The application uses React and TypeScript for presentation and FastAPI for prediction services. Historical replay allows a user to choose a held-out origin and compare predictions with observed outcomes. The latest-forecast view loads the deployed PCP #31 pipelines and reconstructs the same features from the latest saved station history. Refreshing retrieves public observations and reruns inference without retraining.

The forecast origin is the latest measured hour, not the time at which the interface is opened. Each horizon has an explicit target timestamp. The interface flags stale input after 24 hours and identifies targets already in the past; inference is blocked when fewer than 18 of the latest 24 hours are observed. Daily and weekly observation counts and station identity help users interpret the available context. These controls do not establish a continuously connected live sensor service or validated health-alert system.

Training now separates two modes. Reproduce mode verifies the frozen compressed dataset against its recorded SHA-256, uses the saved station, candidate configurations, random seed and split boundaries, and does not require historical observations to be recent relative to today's date. Update mode downloads a new versioned snapshot and applies the freshness and coverage checks before selecting a station. Both modes save a separate experiment directory containing models, metrics, provenance and the training snapshot; they do not automatically replace deployed models.

A full reproduction of PCP #31 produced exactly matching held-out predictions, test metrics and latest-origin forecasts in the tested environment. The backend suite passed 26 tests, including pipeline parity, temporal feature checks, snapshot mismatch rejection, future-clock reproduction and preservation of update-mode freshness checks. These checks support implementation correctness; they do not substitute for future predictive evaluation. Runtime timestamps, fit durations and serialized bytes need not be identical across machines.

## 7 Discussion and limitations

The recurring six-hour advantage in both experiments suggests that the selected history and calendar representation offers useful information beyond the latest reading at that horizon. PCP #31 provides the strongest uncertainty evidence for this comparison. One-hour persistence is already competitive, and next-day forecasting exposes weaknesses that average scores conceal.

Large concentration changes can depend on information absent from a history-only model. Weather and changes in emissions are plausible additional predictors, but this study did not measure their contribution or attribute individual errors to them. Missing history and imputation may also influence model behaviour. The subgroup results establish association, not a causal effect of missingness, because concentration levels and calendar periods differ between groups.

Data availability creates selection bias. Evaluation excludes unavailable targets and poorly covered origins, while deployment may encounter less complete weekly history. PCP #31 testing lacks summer examples and contains few observations close to the training date. Consequently, the aggregate results support claims about eligible held-out station examples rather than year-round operational coverage. Multi-station validation, transfer to other cities and robustness to changes in measurement practices remain untested.

The outputs are point forecasts without calibrated individual prediction intervals. A statistical peak cutoff should not be converted into a clinical or regulatory claim. Station measurements also cannot determine the exposure of every person across the city. Responsible presentation requires station attribution, concentration units, origin and target times, observed coverage, and explicit evidence limits. The repository declares CC BY-NC 4.0 and applicable upstream conditions; reuse should retain the stated data attribution (AirData.kz, n.d.).

Future work should predefine a new evaluation period before modifying models. Candidate improvements include weather features available at issuance time, rolling-origin validation, calibrated forecast intervals, and a coverage-aware choice between a learned estimator and persistence. A fallback motivated by the present sparse-history failures is a proposal, not an implemented or independently validated result. Testing new features and fallback rules on fresh data is necessary before claiming an operational improvement.

## 8 Conclusion

The project demonstrates a reproducible approach to short-term station-level PM2.5 forecasting in Almaty and connects evaluation artifacts to an interactive application. Selected XGBoost models improve average MAE over persistence at all three horizons in both recorded experiments, with the clearest updated-station evidence at six hours. Peak underprediction, spring losses and sparse-history failures limit broader claims. Preserving frozen evaluation inputs, separating evaluation and deployment fits, and displaying the actual forecast origin are essential parts of the resulting research system. The prototype provides a foundation for further prospective testing rather than evidence of reliable continuous citywide forecasting.

## References

AirData.kz. (n.d.). AirDatakz OpenData: Open air quality data for Kazakhstan [Data set and repository]. Global Shapers Almaty Hub. https://github.com/qazybekb/AirDatakz-OpenData

Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, 785–794. https://doi.org/10.1145/2939672.2939785

Hyndman, R. J., & Athanasopoulos, G. (2021). Forecasting: Principles and practice (3rd ed.). OTexts. https://otexts.com/fpp3/

scikit-learn developers. (n.d.). Ridge. scikit-learn documentation. https://scikit-learn.org/1.7/modules/generated/sklearn.linear_model.Ridge.html

## Appendix A Experiment traceability

Historical data commit: 119cf2c278def3129f14cef9380cced9de1f3161. Compressed dataset SHA-256: 300541cb3196b697b4bf676363e7b9eb59044631898bdcb47a75fb15cd9bac50. The experiment manifest, test metrics, peak errors and validation feature ablation are stored in artifacts/experiment.json, artifacts/test_metrics.csv, artifacts/peak_errors.csv and artifacts/validation_feature_ablation.csv.

PCP #31 data commit: 06f3772f7ad5000032d2d31592c88a4311276aa0. Compressed dataset SHA-256: 538ab2f4750adfa7c65b7f2dd106f5729bc46212016c57cc9965c0ae77b325f9. Its frozen snapshot and reproduction reference are data/current_training_pm25.csv.gz and data/current_training_experiment.json. Held-out metrics, predictions, subgroup comparisons and paired intervals are stored under artifacts/current and artifacts/current/analysis. The verified reproduction is stored under artifacts/reproduce/verified-run.

The pinned environment records Python 3.12, NumPy 2.2.0, pandas 2.2.3, scikit-learn 1.7.2, XGBoost 3.1.1 and joblib 1.5.2. Reproduction runs backend.train_current with its default mode; a new experiment uses --mode update. Extended analysis runs backend.analyze_current against the preserved original inputs. These commands are documented in the project README.
