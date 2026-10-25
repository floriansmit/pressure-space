"""Run OPM unit-response ensembles for three sites and the full fault set."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from opm.io.ecl import ERst

from build_deck import build_deck, nearest_grid_cell, project_cells
from run_ensemble import CASES, GEOLOGY, NX, NY, NZ, SITE_DATA, YEARS


HERE = Path(__file__).resolve().parent
RUN_ROOT = Path(os.environ.get("PRESSURE_SPACE_RUN_ROOT", HERE / "scenario-runs"))
FAULT_STATES = ("open", "semi-open", "closed")
DURATIONS = (5, 10, 20, 30, 40)


SITE_RESPONSES = ("alpha", "alpha_beta_unit", "alpha_zeta_unit")


def run_case(index: int, properties: tuple[float, float, float], fault_state: str, site_response: str, duration: int) -> tuple[int, str, Path]:
    permeability, porosity, thickness = properties
    scenario_key = f"{fault_state}_{site_response}"
    case_name = f"GASSUM_D{duration:02d}_{fault_state.replace('-', '_').upper()}_{site_response.upper()}_{index:02d}"
    case_dir = RUN_ROOT / case_name
    output_dir = case_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    deck = case_dir / f"{case_name}.DATA"
    deck.write_text(
        build_deck(
            case_name,
            1.0,
            max(YEARS),
            permeability,
            porosity,
            thickness,
            fault_state=fault_state,
            beta_rate_mt_yr=1.0 if site_response == "alpha_beta_unit" else 0.0,
            zeta_rate_mt_yr=1.0 if site_response == "alpha_zeta_unit" else 0.0,
            injection_years=duration,
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
    return duration, scenario_key, output_dir / f"{case_name}.UNRST"


def extract(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    restart = ERst(str(path))
    active = np.asarray(GEOLOGY["active"] * NZ, dtype=bool).reshape(NZ, NY, NX)

    def expand(values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        if values.size == active.size:
            return values.reshape(NZ, NY, NX)
        result = np.zeros((NZ, NY, NX), dtype=float)
        result[active] = values
        return result

    initial = expand(restart["PRESSURE", 0])
    pressure, saturation, pressure_layers, saturation_layers = [], [], [], []
    for year in YEARS:
        current = expand(restart["PRESSURE", year])
        gas = expand(restart["SGAS", year])
        delta = np.maximum(current - initial, 0)
        pressure.append(delta.mean(axis=0))
        saturation.append(gas.max(axis=0) * 100)
        pressure_layers.append(delta)
        saturation_layers.append(gas * 100)
    return np.stack(pressure), np.stack(saturation), np.stack(pressure_layers), np.stack(saturation_layers)


def write_section_pack(path: Path, pressure: np.ndarray, saturation: np.ndarray) -> None:
    """Write time × percentile × layer × row × column arrays for lazy browser loading."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pressure_q = np.quantile(pressure, (0.1, 0.5, 0.9), axis=0).transpose(1, 0, 2, 3, 4)
    saturation_q = np.quantile(saturation, (0.1, 0.5, 0.9), axis=0).transpose(1, 0, 2, 3, 4)
    with path.open("wb") as stream:
        stream.write(np.asarray(pressure_q, dtype="<f4").tobytes(order="C"))
        stream.write(np.clip(np.rint(saturation_q * 255 / 100), 0, 255).astype(np.uint8).tobytes(order="C"))


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
        (index, properties, fault_state, site_response, duration)
        for fault_state in FAULT_STATES
        for site_response in SITE_RESPONSES
        for duration in DURATIONS
        for index, properties in enumerate(CASES, start=1)
    ]
    grouped: dict[int, dict[str, list[Path]]] = {
        duration: {f"{state}_{response}": [] for state in FAULT_STATES for response in SITE_RESPONSES}
        for duration in DURATIONS
    }
    with ThreadPoolExecutor(max_workers=min(9, os.cpu_count() or 3)) as executor:
        futures = {executor.submit(run_case, *job): job for job in jobs}
        for number, future in enumerate(as_completed(futures), start=1):
            duration, scenario, path = future.result()
            grouped[duration][scenario].append(path)
            print(f"completed {number}/{len(jobs)}: {duration} yr · {scenario}", flush=True)

    arrays = {}
    for duration, scenarios in grouped.items():
        arrays[duration] = {}
        for scenario, paths in scenarios.items():
            extracted = [extract(path) for path in sorted(paths)]
            arrays[duration][scenario] = (
                np.stack([item[0] for item in extracted]),
                np.stack([item[1] for item in extracted]),
                np.stack([item[2] for item in extracted]),
                np.stack([item[3] for item in extracted]),
            )

    section_dir = SITE_DATA.parent / "section"
    manifest = {
        "version": "0.12.0",
        "shape": [len(YEARS), 3, NZ, NY, NX],
        "times_years": list(YEARS),
        "percentiles": [10, 50, 90],
        "pressure_dtype": "float32-le",
        "saturation_dtype": "uint8",
        "saturation_scale": 100 / 255,
        "files": {},
    }
    for duration, scenarios in arrays.items():
        for scenario, values in scenarios.items():
            filename = f"d{duration}-{scenario}.bin"
            write_section_pack(section_dir / filename, values[2], values[3])
            manifest["files"][f"{duration}:{scenario}"] = f"section/{filename}"
    (SITE_DATA.parent / "section-manifest.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")

    data = json.loads(SITE_DATA.read_text(encoding="utf-8"))
    data["times_years"] = list(YEARS)
    reservoir = next(item for item in data["reservoirs"] if item["id"] == "gassum")
    reservoir["times_years"] = list(YEARS)
    points = reservoir["points"]
    for point in points:
        grid_i, grid_j = nearest_grid_cell(point["lon"], point["lat"], GEOLOGY)
        i, j = grid_i - 1, grid_j - 1
        grid_index = j * NX + i
        point.update({
            "grid_i": i,
            "grid_j": j,
            "depth_m": GEOLOGY["top_depth_m"][grid_index],
            "thickness_m": GEOLOGY["gross_thickness_m"][grid_index],
            "mid_reservoir_depth_m": GEOLOGY["mid_reservoir_depth_m"][grid_index],
            "porosity": GEOLOGY["porosity"][grid_index],
            "permeability_md": GEOLOGY["permeability_md"][grid_index],
            "thickness_sd_m": GEOLOGY["thickness_sd_m"][grid_index],
        })
        point["scenario_pressure_bar_by_duration"] = {
            str(duration): {scenario: quantiles(values[0], j, i) for scenario, values in scenarios.items()}
            for duration, scenarios in arrays.items()
        }
        point["scenario_co2_saturation_by_duration"] = {
            str(duration): {scenario: quantiles(values[1], j, i) for scenario, values in scenarios.items()}
            for duration, scenarios in arrays.items()
        }
        point["scenario_pressure_bar"] = point["scenario_pressure_bar_by_duration"]["20"]
        point["scenario_co2_saturation"] = point["scenario_co2_saturation_by_duration"]["20"]
        point["pressure_bar"] = point["scenario_pressure_bar"]["open_alpha"]
        point["co2_saturation"] = point["scenario_co2_saturation"]["open_alpha"]

    def grid_location(i: int, j: int) -> dict[str, float]:
        index = (j - 1) * NX + (i - 1)
        return {
            "lon": GEOLOGY["longitude"][index],
            "lat": GEOLOGY["latitude"][index],
        }

    cells = project_cells(GEOLOGY)
    reservoir["reference_injector"] = grid_location(*cells["alpha"])
    reservoir["storage_projects"] = [
        {"id": "alpha", "name": "Storage Alpha", "enabled": True, "rate_mt_yr": 1.0, **grid_location(*cells["alpha"])},
        {"id": "beta", "name": "Storage Beta", "enabled": False, "rate_mt_yr": 1.0, **grid_location(*cells["beta"])},
        {"id": "zeta", "name": "Storage Zeta", "enabled": False, "rate_mt_yr": 1.0, "cell_id": 192, "lon": points[191]["lon"], "lat": points[191]["lat"]},
    ]
    reservoir["fault_scenarios"] = {
        "modelled_fault_ids": [fault["id"] for fault in json.loads((HERE.parent / "dist" / "data" / "regional-context.json").read_text(encoding="utf-8"))["faults"]],
        "fault_count": 29,
        "states": {"open": 1.0, "semi-open": 0.05, "closed": 0.0001},
        "orientation": "all supplied traces represented vertically through all six Gassum layers",
        "response_method": "unit-rate OPM responses superposed for 1, 2 and 3 Mt/yr screening",
    }
    reservoir["ensemble_size"] = len(CASES)
    reservoir["schedule_count"] = len(FAULT_STATES) * len(SITE_RESPONSES) * len(DURATIONS)
    reservoir["injection_durations_years"] = list(DURATIONS)
    reservoir["engine"] = "OPM Flow 2026.04 CO2STORE"
    reservoir["is_opm_result"] = True
    reservoir["ensemble_design"] = "L9 perturbations around mapped geology for each all-fault state and Alpha/Beta/Zeta unit response"
    reservoir["geological_model"] = {
        "geometry": GEOLOGY["source"]["geometry"],
        "properties": ["porosity", "permeability", "net-to-gross", "gross thickness"],
        "surface_cells": NX * NY,
        "active_surface_cells": sum(GEOLOGY["active"]),
        "petrophysics_method": GEOLOGY["source"]["property_method"],
        "property_percentiles": {
            "10": {"permeability_multiplier": 0.4966, "porosity_multiplier": 0.9, "thickness_sigma_offset": -1.0},
            "50": {"permeability_multiplier": 1.0, "porosity_multiplier": 1.0, "thickness_sigma_offset": 0.0},
            "90": {"permeability_multiplier": 2.0138, "porosity_multiplier": 1.1, "thickness_sigma_offset": 1.0},
        },
    }
    data["model_version"] = "pressure-space-opm-geological-0.12.0"
    SITE_DATA.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(SITE_DATA)


if __name__ == "__main__":
    main()
