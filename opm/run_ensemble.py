"""Run a compact OPM Flow ensemble and merge Gassum results into the site data.

Run this script inside the Ubuntu WSL distribution where ``flow`` and the OPM
Python bindings are installed. Raw simulator files stay outside the published
site; only pressure and gas-saturation quantiles are written to the browser JSON.
"""

from __future__ import annotations

import itertools
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from opm.io.ecl import ERst

from build_deck import build_deck


HERE = Path(__file__).resolve().parent
SITE_DATA = HERE.parent / "dist" / "data" / "pressure-model.json"
RUN_ROOT = HERE / "ensemble-runs"
NX, NY, NZ = 60, 50, 6
YEARS = (1, 5, 10, 20)

# An L9 orthogonal design spans low, central and high aquifer properties without
# pretending that nine generic realizations constitute a calibrated uncertainty model.
CASES = (
    (100.0, 0.18, 45.0), (100.0, 0.22, 72.0), (100.0, 0.26, 110.0),
    (250.0, 0.18, 72.0), (250.0, 0.22, 110.0), (250.0, 0.26, 45.0),
    (600.0, 0.18, 110.0), (600.0, 0.22, 45.0), (600.0, 0.26, 72.0),
)


def run_case(index: int, permeability: float, porosity: float, thickness: float) -> Path:
    case_name = f"GASSUM_L9_{index:02d}"
    case_dir = RUN_ROOT / case_name
    output_dir = case_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    deck = case_dir / f"{case_name}.DATA"
    deck.write_text(
        build_deck(case_name, 1.0, 20, permeability, porosity, thickness),
        encoding="utf-8",
    )
    log = case_dir / "flow.log"
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(
            ["flow", str(deck), f"--output-dir={output_dir}"],
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if result.returncode:
        raise RuntimeError(f"{case_name} failed; see {log}")
    return output_dir / f"{case_name}.UNRST"


def extract_case(path: Path) -> tuple[np.ndarray, np.ndarray]:
    restart = ERst(str(path))
    initial_pressure = np.asarray(restart["PRESSURE", 0], dtype=float).reshape(NZ, NY, NX)
    pressure_results = []
    saturation_results = []
    for year in YEARS:
        pressure = np.asarray(restart["PRESSURE", year], dtype=float).reshape(NZ, NY, NX)
        saturation = np.asarray(restart["SGAS", year], dtype=float).reshape(NZ, NY, NX)
        pressure_results.append(np.maximum(pressure - initial_pressure, 0.0).mean(axis=0))
        saturation_results.append(saturation.max(axis=0))
    return np.stack(pressure_results), np.stack(saturation_results)


def map_to_points(data: dict, pressure_cases: np.ndarray, saturation_cases: np.ndarray) -> None:
    reservoir = next(item for item in data["reservoirs"] if item["id"] == "gassum")
    points = reservoir["points"]
    lon_min, lon_max = min(p["lon"] for p in points), max(p["lon"] for p in points)
    lat_min, lat_max = min(p["lat"] for p in points), max(p["lat"] for p in points)

    for point in points:
        i = int(round((point["lon"] - lon_min) / (lon_max - lon_min) * (NX - 1)))
        j = int(round((point["lat"] - lat_min) / (lat_max - lat_min) * (NY - 1)))
        p_values = pressure_cases[:, :, j, i]
        s_values = saturation_cases[:, :, j, i]
        point["pressure_bar"] = [
            [round(float(value), 3) for value in np.quantile(p_values[:, t], (0.1, 0.5, 0.9))]
            for t in range(len(YEARS))
        ]
        point["co2_saturation"] = [
            [round(float(value * 100), 2) for value in np.quantile(s_values[:, t], (0.1, 0.5, 0.9))]
            for t in range(len(YEARS))
        ]

    # The OPM injector is in the centre grid cell.
    reservoir["reference_injector"] = {
        "lon": round((lon_min + lon_max) / 2, 6),
        "lat": round((lat_min + lat_max) / 2, 6),
    }
    reservoir.update({
        "engine": "OPM Flow 2026.04 CO2STORE",
        "is_opm_result": True,
        "ensemble_size": len(CASES),
        "ensemble_design": "L9 screening design over permeability, porosity and net thickness",
    })


def main() -> None:
    if not shutil.which("flow"):
        raise SystemExit("OPM Flow is not on PATH; run this script inside Ubuntu WSL")
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    restart_files: list[Path | None] = [None] * len(CASES)
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(run_case, index, *values): index - 1
            for index, values in enumerate(CASES, start=1)
        }
        for future in as_completed(futures):
            slot = futures[future]
            restart_files[slot] = future.result()
            print(f"completed {slot + 1}/{len(CASES)}", flush=True)

    extracted = [extract_case(path) for path in restart_files if path is not None]
    pressure_cases = np.stack([item[0] for item in extracted])
    saturation_cases = np.stack([item[1] for item in extracted])

    data = json.loads(SITE_DATA.read_text(encoding="utf-8"))
    data["times_years"] = list(YEARS)
    for reservoir in data["reservoirs"]:
        for point in reservoir["points"]:
            point["pressure_bar"] = point["pressure_bar"][: len(YEARS)]
        reservoir.setdefault("engine", "analytical radial-diffusivity ensemble")
        reservoir.setdefault("is_opm_result", False)
        reservoir.setdefault("ensemble_size", data.get("ensemble_size", 160))
    map_to_points(data, pressure_cases, saturation_cases)
    data.update({
        "model_version": "decode-pressure-opm-mvp-0.2.0",
        "engine": "mixed OPM Flow and analytical screening ensembles",
        "opm_engine": "OPM Flow 2026.04 CO2STORE",
        "reference_rate_mt_yr": 1.0,
    })
    data["limitations"] = [
        "Gassum is an OPM Flow screening ensemble, not a history-matched or permitting model.",
        "Other formations remain analytical screening proxies until their OPM grids are populated.",
        "Fault thresholds and geomechanical coupling are illustrative until calibrated data are supplied.",
    ]
    SITE_DATA.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(SITE_DATA)


if __name__ == "__main__":
    main()
