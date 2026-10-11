# Breathe Almaty forecasting application

## Model trained on a currently reporting station

The separate `artifacts/current/` experiment trains 1-, 6-, and 24-hour PM2.5 forecasts for KazHydroMet PCP #31 (`kgmt_27`). The dashboard opens on **Latest forecast**, which runs those fitted models against the latest saved observations. **Refresh latest forecast** retrieves the current public dataset and runs inference again without retraining. Predictions begin at the latest measured hour; each card shows the actual target date/time and flags targets that have already passed. A stale-data warning appears after 24 hours, and forecasts are blocked when fewer than 18 of the latest 24 measured hours are present. Sparse weekly coverage is displayed explicitly. The original US Embassy experiment remains available under **Historical replay**.

To reproduce this experiment, run from the project root:

```powershell
backend/.venv/Scripts/python.exe -m backend.train_current
```

The default `--mode reproduce` verifies the SHA-256 of the immutable `data/current_training_pm25.csv.gz` snapshot against `data/current_training_experiment.json`. It uses the recorded station, random seed, feature definitions, candidate settings and validation/test boundaries without checking today's date or downloading data. This repeats the original validation search and both refits. Use the pinned dependencies in `backend/requirements.txt`; fit durations, run timestamps and serialized file bytes can vary across runs or platforms.

To download fresh measurements and train a new experiment:

```powershell
backend/.venv/Scripts/python.exe -m backend.train_current --mode update
```

Both modes save models, metrics, a training snapshot and provenance in `artifacts/<mode>/<UTC run ID>/`. Use `--output <empty-directory>` to choose a destination. Existing nonempty directories are rejected, including the deployed `artifacts/current/` directory. A new run does not automatically replace the dashboard's models. To reproduce an updated experiment later, pass its `training_pm25.csv.gz` with `--snapshot` and its `experiment.json` with `--reference` in reproduce mode. The legacy `--download` option is replaced by `--mode update`.

Refreshing observations changes only the inference snapshot and its `data/current_pm25.csv.source.json` provenance. The original frozen training snapshot and reference remain unchanged. The script emits no routine print output.

In update mode, station selection requires a reading within 24 hours, at least 6,000 observed training hours and 18 observations in the latest 24 hours. It ranks eligible stations by observed history. Features preserve hourly gaps; a median imputer with missingness indicators handles unavailable history. Targets are never imputed. New chronological validation and test boundaries use the 70th and 85th percentiles of eligible origins, with forecast targets purged across boundaries; reproduction reuses the recorded boundaries. Hyperparameters are selected on validation, evaluated after refitting on pre-test labels, then separately refitted on all available labels for deployment.

`artifacts/current/test_metrics.csv` reports independent test scores and persistence/seasonal baselines. `evaluation_*h.joblib` preserves evaluation models; `forecast_*h.joblib` contains final refitted models. `latest_forecast.json` contains forecasts from the latest measured hour. See `artifacts/current/training_report.md` for results and limitations. The public data is published with delays and has long gaps in 2026; these artifacts do not establish continuous live forecasting accuracy.

A React and TypeScript dashboard with a Python FastAPI backend, using the trained Ridge and XGBoost model pipelines from the experiment below. Choose a held-out hour, generate 1-, 6- and 24-hour PM2.5 forecasts, optionally reveal actual outcomes, compare test metrics and download forecasts as CSV.

The historical replay view uses the Almaty US Embassy station and its held-out 2024 observations. The latest forecast view uses PCP #31 and does not require future targets to be observed. Both views make fresh predictions from serialized model pipelines. The public dataset updates daily, so the latest view does not claim a continuous live sensor connection. Charts show gaps and individual forecast points rather than implying a continuous hourly forecast.

## Setup

Use Python 3.12 and Node.js 22.12 or newer. Run these commands from the project root:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
backend/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open [the dashboard](http://127.0.0.1:8000). After setup and a frontend build, `./start-app.ps1` can also launch the server in the background. It returns the server process ID; stop that process when finished. API documentation is available at [FastAPI docs](http://127.0.0.1:8000/docs).

On macOS/Linux, use `backend/.venv/bin/python` instead of the Windows Python path, and `npm` instead of `npm.cmd`.

## Development

Run the API in one terminal:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, run `npm.cmd run dev` from `frontend/` and open [the development dashboard](http://127.0.0.1:5173). Vite proxies API requests to FastAPI. Rebuild the frontend and restart the production server after changes. Navigation uses a single dashboard route.

## API and verification

- `GET /api/health`: readiness and loaded model count.
- `GET /api/overview`: station metadata, available dates and independent evaluation metrics.
- `GET /api/latest`: fresh inference from the saved latest PCP #31 observations, with measurement age, daily/weekly coverage, target times, and current-station test metrics.
- `POST /api/latest/refresh`: retrieve updated public observations and run inference; failed refreshes return the saved snapshot with an explicit warning.
- `GET /api/latest/export`: export the latest measured-hour forecast as CSV.
- `GET /api/stations`: last successful public station-data check, source, coordinates, latest PM2.5, and reporting freshness. A reading within 48 hours is labeled recently reporting; official operational status is not inferred.
- `POST /api/stations/refresh`: retrieve the latest public AirData.kz Almaty PM2.5 snapshot, independently from the immutable training dataset. A saved `data/station_status.json` snapshot remains usable if the external service is unavailable. Refreshes within 60 seconds reuse the last check.
- `GET /api/origins?date=2024-06-01`: eligible hours for an Almaty local calendar date.
- `POST /api/forecast`: `{"origin": "2024-06-01T12:00:00Z", "model": "XGBoost"}`. Use an origin returned by the API; timezone information is required. Returns model predictions, input history and separately identified observed outcomes.
- `POST /api/forecast/export`: same request, returns CSV.

Run backend integration and forecasting integrity checks:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -v
```

`npm.cmd run build` in `frontend/` checks TypeScript and builds the production interface. Backend tests compare both model families against notebook outputs across twelve origins and check causal features, missing-hour lags, timezone validation, date selection and exports.

The server expects `artifacts/experiment.json`, the six trusted `.joblib` pipelines, evaluation CSVs, and `data/almaty_pm25.csv.gz`. It checks dataset provenance and feature metadata at startup. To use another notebook experiment, replace these files together and restart the server. `AIRDATA_ROOT` may point to another project directory containing the same structure. Load model files only from trusted sources. This is a local research application; external hosting would need deployment-specific configuration.

## Training notebook

### Extended analysis of the current station

The [model failure discussion](MODEL_FAILURES.md) compares failures in both the US Embassy and PCP #31 experiments, documents concrete missed rises and declines, separates observations from causal hypotheses, and provides a defense explanation and proposed next experiments.

Install `backend/requirements-analysis.txt` and run `backend/.venv/Scripts/python.exe -m backend.analyze_current` from the project root. This performs no fitting and uses the checksum-verified immutable training snapshot and saved held-out predictions. It writes `artifacts/current/analysis/report.md`, five PNG figures, subgroup CSVs, the largest misses, and paired seven-day-block bootstrap comparisons. The report describes empty seasonal groups, sample counts, peak underprediction, sparse-history failures, and uncertainty. These diagnostics must not be used to tune the existing model against its test set.

Open [Google Colab](https://colab.research.google.com/), choose **File → Upload notebook**, and upload `Almaty_PM25_AirData_Training.ipynb`. Select **Runtime → Run all**. A CPU runtime is sufficient; no account-specific dataset credentials or Drive mount is needed.

The notebook downloads a fixed AirData.kz dataset version, audits source/station coverage, preserves missing hours, and trains forecasts for 1, 6 and 24 hours ahead. It compares persistence, a same-hour-yesterday baseline, Ridge regression and XGBoost. Settings are selected using 2023; 2024 is held out for final evaluation. The default is Almaty's US Embassy station, `oaq_25903`.

Useful output consists of data audit tables, charts, model comparisons, measured training times, error analysis and a historical replay demonstration. There are no print commands in the notebook. The final cells save fitted models, predictions, metrics and experiment provenance in `almaty_pm25_experiment.zip` and offer a Colab download.

Change `STATION_ID` and date boundaries in the configuration cell for another experiment. Check station coverage first. Do not choose settings based on held-out test results. Some source series are daily, some are low-cost sensors, and some values are reconstructed from AQI. The initial experiment uses PM2.5 history and calendar features; weather is a future extension.

Dataset: [AirData.kz open data](https://github.com/qazybekb/AirDatakz-OpenData), commit `119cf2c278def3129f14cef9380cced9de1f3161`. Credit AirData.kz / Global Shapers Almaty Hub and original measurement providers. Dataset use is subject to CC BY-NC 4.0 and applicable upstream terms. The cached dataset is stored under `data/`; the notebook can download it independently.

Concentrations are in µg/m³. The target is one future measured hour, rather than an average over the forecast horizon. These forecasts describe one station and are not a validated citywide alert service. Retrospective cleaning and unrecorded reporting delays limit how closely this experiment simulates live forecasting. Only load model files from trusted sources.
