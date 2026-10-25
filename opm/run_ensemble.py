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

from build_deck import build_deck, load_geology, nearest_grid_cell


HERE = Path(__file__).resolve().parent
SITE_DATA = HERE.parent / "dist" / "data" / "pressure-model.json"
RUN_ROOT = HERE / "ensemble-runs"
GEOLOGY = load_geology()
NX, NY, NZ = GEOLOGY["nx"], GEOLOGY["ny"], GEOLOGY["nz"]
# Published response-function samples.  The reference cases inject continuously
# for 60 years; the browser derives a finite injection period by subtracting a
# time-shifted unit response after shut-in.
YEARS = (1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60)

# An L9 orthogonal design perturbs the mapped geological properties rather than
# replacing them with homogeneous values. Permeability uses the supplied 0.7
# log-space uncertainty, porosity +/-10%, and thickness +/- one supplied SD.
CASES = (
    (0.4966, 0.9, -1.0), (0.4966, 1.0, 0.0), (0.4966, 1.1, 1.0),
    (1.0, 0.9, 0.0), (1.0, 1.0, 1.0), (1.0, 1.1, -1.0),
    (2.0138, 0.9, 1.0), (2.0138, 1.0, -1.0), (2.0138, 1.1, 0.0),
)


def run_case(index: int, permeability: float, porosity: float, thickness: float) -> Path:
    case_name = f"GASSUM_L9_{index:02d}"
    case_dir = RUN_ROOT / case_name
    output_dir = case_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    deck = case_dir / f"{case_name}.DATA"
    deck.write_text(
        build_deck(case_name, 1.0, max(YEARS), permeability, porosity, thickness),
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
    active = np.asarray(GEOLOGY["active"] * NZ, dtype=bool).reshape(NZ, NY, NX)

    def expand(values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        if values.size == active.size:
            return values.reshape(NZ, NY, NX)
        result = np.zeros((NZ, NY, NX), dtype=float)
        result[active] = values
        return result

    initial_pressure = expand(restart["PRESSURE", 0])
    pressure_results = []
    saturation_results = []
    for year in YEARS:
        pressure = expand(restart["PRESSURE", year])
        saturation = expand(restart["SGAS", year])
        pressure_results.append(np.maximum(pressure - initial_pressure, 0.0).mean(axis=0))
        saturation_results.append(saturation.max(axis=0))
    return np.stack(pressure_results), np.stack(saturation_results)


def map_to_points(data: dict, pressure_cases: np.ndarray, saturation_cases: np.ndarray) -> None:
    reservoir = next(item for item in data["reservoirs"] if item["id"] == "gassum")
    points = reservoir["points"]
    for point in points:
        grid_i, grid_j = nearest_grid_cell(point["lon"], point["lat"], GEOLOGY)
        i, j = grid_i - 1, grid_j - 1
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

    reservoir.update({
        "engine": "OPM Flow 2026.04 CO2STORE",
        "is_opm_result": True,
        "ensemble_size": len(CASES),
        "ensemble_design": "L9 perturbations around mapped permeability, porosity and gross thickness",
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
    previous_times = list(data["times_years"])
    data["times_years"] = list(YEARS)
    for reservoir in data["reservoirs"]:
        if reservoir["id"] != "gassum":
            existing_length = len(reservoir["points"][0]["pressure_bar"])
            reservoir.setdefault("times_years", previous_times[:existing_length])
        for point in reservoir["points"]:
            point["pressure_bar"] = point["pressure_bar"][: len(YEARS)]
        reservoir.setdefault("engine", "analytical radial-diffusivity ensemble")
        reservoir.setdefault("is_opm_result", False)
        reservoir.setdefault("ensemble_size", data.get("ensemble_size", 160))
    map_to_points(data, pressure_cases, saturation_cases)
    next(item for item in data["reservoirs"] if item["id"] == "gassum")["times_years"] = list(YEARS)
    data.update({
        "model_version": "pressure-space-opm-geological-0.12.0",
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
