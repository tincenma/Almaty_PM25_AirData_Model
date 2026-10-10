# Breathe Almaty forecasting application

A React and TypeScript dashboard with a Python FastAPI backend, using the trained Ridge and XGBoost model pipelines from the experiment below. Choose a held-out hour, generate 1-, 6- and 24-hour PM2.5 forecasts, optionally reveal actual outcomes, compare test metrics and download forecasts as CSV.

The application is a historical replay of the Almaty US Embassy station. It makes fresh model predictions; it does not substitute saved test predictions or claim to provide live measurements. Only dates with sufficient history and observed future targets are offered. Charts show gaps and individual forecast points rather than implying a continuous hourly forecast.

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

Open [Google Colab](https://colab.research.google.com/), choose **File → Upload notebook**, and upload `Almaty_PM25_AirData_Training.ipynb`. Select **Runtime → Run all**. A CPU runtime is sufficient; no account-specific dataset credentials or Drive mount is needed.

The notebook downloads a fixed AirData.kz dataset version, audits source/station coverage, preserves missing hours, and trains forecasts for 1, 6 and 24 hours ahead. It compares persistence, a same-hour-yesterday baseline, Ridge regression and XGBoost. Settings are selected using 2023; 2024 is held out for final evaluation. The default is Almaty's US Embassy station, `oaq_25903`.

Useful output consists of data audit tables, charts, model comparisons, measured training times, error analysis and a historical replay demonstration. There are no print commands in the notebook. The final cells save fitted models, predictions, metrics and experiment provenance in `almaty_pm25_experiment.zip` and offer a Colab download.

Change `STATION_ID` and date boundaries in the configuration cell for another experiment. Check station coverage first. Do not choose settings based on held-out test results. Some source series are daily, some are low-cost sensors, and some values are reconstructed from AQI. The initial experiment uses PM2.5 history and calendar features; weather is a future extension.

Dataset: [AirData.kz open data](https://github.com/qazybekb/AirDatakz-OpenData), commit `119cf2c278def3129f14cef9380cced9de1f3161`. Credit AirData.kz / Global Shapers Almaty Hub and original measurement providers. Dataset use is subject to CC BY-NC 4.0 and applicable upstream terms. The cached dataset is stored under `data/`; the notebook can download it independently.

Concentrations are in µg/m³. The target is one future measured hour, rather than an average over the forecast horizon. These forecasts describe one station and are not a validated citywide alert service. Retrospective cleaning and unrecorded reporting delays limit how closely this experiment simulates live forecasting. Only load model files from trusted sources.
