"""Run OPM ensembles for two-site interference and three fault states."""

from __future__ import annotations

import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from opm.io.ecl import ERst

from build_deck import build_deck
from run_ensemble import CASES, NX, NY, NZ, SITE_DATA, YEARS


HERE = Path(__file__).resolve().parent
RUN_ROOT = HERE / "scenario-runs"
FAULT_STATES = ("open", "semi-open", "closed")


def run_case(index: int, properties: tuple[float, float, float], fault_state: str, second_site: bool) -> tuple[str, Path]:
    permeability, porosity, thickness = properties
    site_key = "alpha_beta" if second_site else "alpha"
    scenario_key = f"{fault_state}_{site_key}"
    case_name = f"GASSUM_{fault_state.replace('-', '_').upper()}_{site_key.upper()}_{index:02d}"
    case_dir = RUN_ROOT / case_name
    output_dir = case_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    deck = case_dir / f"{case_name}.DATA"
    deck.write_text(
        build_deck(
            case_name,
            1.0,
            20,
            permeability,
            porosity,
            thickness,
            fault_state=fault_state,
            second_site=second_site,
        ),
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
    return scenario_key, output_dir / f"{case_name}.UNRST"


def extract(path: Path) -> tuple[np.ndarray, np.ndarray]:
    restart = ERst(str(path))
    initial = np.asarray(restart["PRESSURE", 0], dtype=float).reshape(NZ, NY, NX)
    pressure, saturation = [], []
    for year in YEARS:
        current = np.asarray(restart["PRESSURE", year], dtype=float).reshape(NZ, NY, NX)
        gas = np.asarray(restart["SGAS", year], dtype=float).reshape(NZ, NY, NX)
        pressure.append(np.maximum(current - initial, 0).mean(axis=0))
        saturation.append(gas.max(axis=0) * 100)
    return np.stack(pressure), np.stack(saturation)


def quantiles(values: np.ndarray, j: int, i: int) -> list[list[float]]:
    cell = values[:, :, j, i]
    return [
        [round(float(value), 3) for value in np.quantile(cell[:, t], (0.1, 0.5, 0.9))]
        for t in range(len(YEARS))
    ]


def main() -> None:
    if not shutil.which("flow"):
        raise SystemExit("OPM Flow is not on PATH; run inside Ubuntu WSL")
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    jobs = [
        (index, properties, fault_state, second_site)
        for fault_state in FAULT_STATES
        for second_site in (False, True)
        for index, properties in enumerate(CASES, start=1)
    ]
    grouped: dict[str, list[Path]] = {f"{state}_{sites}": [] for state in FAULT_STATES for sites in ("alpha", "alpha_beta")}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(run_case, *job): job for job in jobs}
        for number, future in enumerate(as_completed(futures), start=1):
            scenario, path = future.result()
            grouped[scenario].append(path)
            print(f"completed {number}/{len(jobs)}: {scenario}", flush=True)

    arrays = {}
    for scenario, paths in grouped.items():
        extracted = [extract(path) for path in sorted(paths)]
        arrays[scenario] = (
            np.stack([item[0] for item in extracted]),
            np.stack([item[1] for item in extracted]),
        )

    data = json.loads(SITE_DATA.read_text(encoding="utf-8"))
    reservoir = next(item for item in data["reservoirs"] if item["id"] == "gassum")
    points = reservoir["points"]
    lon_min, lon_max = min(p["lon"] for p in points), max(p["lon"] for p in points)
    lat_min, lat_max = min(p["lat"] for p in points), max(p["lat"] for p in points)
    for point in points:
        i = int(round((point["lon"] - lon_min) / (lon_max - lon_min) * (NX - 1)))
        j = int(round((point["lat"] - lat_min) / (lat_max - lat_min) * (NY - 1)))
        point["scenario_pressure_bar"] = {
            scenario: quantiles(values[0], j, i) for scenario, values in arrays.items()
        }
        point["scenario_co2_saturation"] = {
            scenario: quantiles(values[1], j, i) for scenario, values in arrays.items()
        }
        point["pressure_bar"] = point["scenario_pressure_bar"]["open_alpha"]
        point["co2_saturation"] = point["scenario_co2_saturation"]["open_alpha"]

    def grid_location(i: int, j: int) -> dict[str, float]:
        return {
            "lon": round(lon_min + (i - 1) / (NX - 1) * (lon_max - lon_min), 6),
            "lat": round(lat_min + (j - 1) / (NY - 1) * (lat_max - lat_min), 6),
        }

    reservoir["reference_injector"] = grid_location(30, 25)
    reservoir["storage_projects"] = [
        {"id": "alpha", "name": "Storage Alpha", "enabled": True, "rate_mt_yr": 1.0, **grid_location(30, 25)},
        {"id": "beta", "name": "Storage Beta", "enabled": False, "rate_mt_yr": 1.0, **grid_location(28, 20)},
    ]
    reservoir["fault_scenarios"] = {
        "modelled_fault_id": "polygon_23",
        "states": {"open": 1.0, "semi-open": 0.05, "closed": 0.0001},
        "orientation": "vertical through all six Gassum layers",
    }
    reservoir["ensemble_size"] = len(CASES)
    reservoir["ensemble_design"] = "L9 property ensemble for each site/fault configuration"
    data["model_version"] = "decode-pressure-opm-interference-0.3.0"
    SITE_DATA.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(SITE_DATA)


if __name__ == "__main__":
    main()
