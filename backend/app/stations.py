"""Latest station metadata, independent of the pinned training dataset."""

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import threading
from urllib.request import Request, urlopen

import pandas as pd

from .service import number

SOURCES = {
    "kgmt": "KazHydroMet", "openaq": "OpenAQ", "airgradient": "AirGradient",
    "airkaz": "AirKaz", "waqi": "WAQI",
}


def reporting_status(last_measurement: str, now: datetime) -> str:
    elapsed = (now - datetime.fromisoformat(last_measurement)).total_seconds()
    if elapsed < -3600:
        return "unknown"
    return "recent" if elapsed <= 48 * 3600 else "not_recent"


class StationCatalog:
    def __init__(self, root: Path):
        self.file = root / "data" / "station_status.json"
        self.lock = threading.Lock()

    def refresh(self):
        with self.lock:
            now = datetime.now(timezone.utc)
            if self.file.exists():
                cached = json.loads(self.file.read_text(encoding="utf-8"))
                if (now - datetime.fromisoformat(cached["checked_at"])).total_seconds() < 60:
                    return
            headers = {"User-Agent": "Breathe-Almaty-Research", "Accept": "application/json"}
            commit_request = Request("https://api.github.com/repos/qazybekb/AirDatakz-OpenData/commits/main", headers=headers)
            with urlopen(commit_request, timeout=15) as response:
                commit = json.load(response)["sha"]
            data_url = f"https://raw.githubusercontent.com/qazybekb/AirDatakz-OpenData/{commit}/almaty/pm25.csv.gz"
            with urlopen(Request(data_url, headers=headers), timeout=30) as response:
                frame = pd.read_csv(io.BytesIO(response.read()), compression="gzip", dtype={"station_id": "string"})
            frame["datetime_utc"] = pd.to_datetime(frame["datetime_utc"], utc=True, errors="coerce")
            frame["value_ugm3"] = pd.to_numeric(frame["value_ugm3"], errors="coerce")
            frame = frame.dropna(subset=["station_id", "datetime_utc", "value_ugm3"])
            frame = frame.loc[frame["value_ugm3"].ge(0)].sort_values("datetime_utc")
            summary = frame.groupby("station_id")["datetime_utc"].agg(["min", "size"])
            latest = frame.groupby("station_id").tail(1)
            stations = []
            for _, row in latest.iterrows():
                station_id = str(row["station_id"])
                stations.append({
                    "id": station_id, "name": str(row["station_name"]),
                    "source": str(row["source"]), "source_name": SOURCES.get(str(row["source"]), str(row["source"])),
                    "latitude": number(row["lat"]), "longitude": number(row["lon"]),
                    "latest_measurement": row["datetime_utc"].isoformat(),
                    "latest_pm25": number(row["value_ugm3"]),
                    "first_measurement": summary.loc[station_id, "min"].isoformat(),
                    "records": int(summary.loc[station_id, "size"]),
                })
            payload = {"checked_at": datetime.now(timezone.utc).isoformat(),
                       "dataset_commit": commit, "source_url": data_url, "stations": stations}
            temporary = self.file.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.file)

    def response(self, trained_station_id: str, refresh: bool = False):
        refresh_error = None
        if refresh or not self.file.exists():
            try:
                self.refresh()
            except (OSError, ValueError, KeyError):
                refresh_error = "Could not retrieve updated station data. Showing the last saved check if available."
        if not self.file.exists():
            return {"checked_at": None, "dataset_commit": None, "source_url": None,
                    "trained_station": None, "stations": [], "refresh_error": refresh_error}
        cached = json.loads(self.file.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc)
        stations = []
        for entry in cached["stations"]:
            stations.append({**entry, "reporting_status": reporting_status(entry["latest_measurement"], now),
                             "model_available": entry["id"] == trained_station_id})
        stations.sort(key=lambda entry: entry["latest_measurement"], reverse=True)
        return {**cached, "stations": stations,
                "trained_station": next((entry for entry in stations if entry["model_available"]), None),
                "refresh_error": refresh_error}

