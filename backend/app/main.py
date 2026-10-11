from contextlib import asynccontextmanager
from datetime import datetime
import io
import os
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, field_validator

from .service import ModelService
from .stations import StationCatalog
from .current import CurrentModelService

ROOT = Path(os.getenv("AIRDATA_ROOT", Path(__file__).resolve().parents[2])).resolve()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.models = ModelService(ROOT)
    app.state.stations = StationCatalog(ROOT)
    app.state.current = CurrentModelService(ROOT) if (ROOT / 'artifacts/current/experiment.json').exists() else None
    yield
    del app.state.models
    del app.state.stations
    del app.state.current


app = FastAPI(title="Breathe Almaty API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: datetime
    model: Literal["XGBoost", "Ridge"] = "XGBoost"

    @field_validator("origin")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Include a timezone offset or Z in the forecast origin.")
        return value


def predict(request: Request, payload: ForecastRequest):
    try:
        return request.app.state.models.forecast(payload.origin, payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/health")
def health(request: Request):
    return {"status": "ready", "models_loaded": len(request.app.state.models.bundles)}


@app.get("/api/overview")
def overview(request: Request):
    return request.app.state.models.overview()


@app.get("/api/stations")
def stations(request: Request):
    return station_response(request)


@app.post("/api/stations/refresh")
def refresh_stations(request: Request):
    return station_response(request, refresh=True)


def station_response(request: Request, refresh=False):
    result = request.app.state.stations.response(request.app.state.models.station_id, refresh=refresh)
    current = request.app.state.current
    result['current_model_station'] = next((station for station in result['stations'] if current and station['id'] == current.station_id), None)
    return result


def current_prediction(request: Request, refresh=False):
    service = request.app.state.current
    if service is None:
        raise HTTPException(status_code=503, detail='Latest forecasting models have not been trained yet.')
    try:
        return service.forecast(refresh)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get('/api/latest')
def latest(request: Request):
    return current_prediction(request)


@app.post('/api/latest/refresh')
def refresh_latest(request: Request):
    return current_prediction(request, refresh=True)


@app.get('/api/latest/export')
def export_latest(request: Request):
    result = current_prediction(request)
    frame = pd.DataFrame(result['forecasts'])
    frame.insert(0, 'station_id', result['station']['station_id'])
    frame.insert(1, 'origin_utc', result['origin'])
    return StreamingResponse(io.StringIO(frame.to_csv(index=False)), media_type='text/csv',
                             headers={'Content-Disposition': 'attachment; filename="latest_forecast.csv"'})


@app.get("/api/origins")
def origins(request: Request, date: str):
    values = request.app.state.models.origin_groups.get(date)
    if not values:
        raise HTTPException(status_code=404, detail="No eligible replay hours on this date.")
    return {"date": date, "origins": values}


@app.post("/api/forecast")
def forecast(request: Request, payload: ForecastRequest):
    return predict(request, payload)


@app.post("/api/forecast/export")
def export_forecast(request: Request, payload: ForecastRequest):
    result = predict(request, payload)
    frame = pd.DataFrame(result["forecasts"])
    frame.insert(0, "station_id", result["station_id"])
    frame.insert(1, "origin_utc", result["origin"])
    frame.insert(2, "model", result["model"])
    return StreamingResponse(io.StringIO(frame.to_csv(index=False)), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="almaty_forecast.csv"'})


# After the React production build, FastAPI serves the dashboard from the same address.
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(DIST / "index.html")

