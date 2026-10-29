"""Build the larger Area C regional OPM screening grid.

The Area C EarthVision exports are scattered-data files.  The builder expects
depth-domain Top Fjerritslev, Top Gassum and Top Vinding files in the Area C
directory and resamples those supplied depths directly to a 5 km regional grid.

This is a regional pressure-interference model, not a replacement for a
depth-converted static model.  The generated JSON records the source bounds,
wells and site classifications for reproducibility.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE.parent / "2026 Model Decode Area"
HORIZON_ROOT = SOURCE_ROOT / "Depth horizons EarthVision" / "Area C"
WELL_TOPS = SOURCE_ROOT / "wells" / "well_tops" / "dk_formation_tops_v_1_5_simplified.txt"
CALIBRATION = HERE / "data" / "gassum-petrophysics-calibration.json"
OUTPUT = HERE / "data" / "regional-area-c-geological-grid.json"

GRID_SPACING_M = 5_000.0
NZ = 6


def read_scattered(path: Path) -> tuple[np.ndarray, dict[str, float]]:
    grid_size = re.compile(r"^# Grid_size:\s*(\d+)\s*x\s*(\d+)")
    rows: list[tuple[float, float, float, int, int]] = []
    metadata: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = grid_size.match(line)
        if match:
            metadata["source_cols"] = float(match.group(1))
            metadata["source_rows"] = float(match.group(2))
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) >= 5:
            x, y, z = map(float, fields[:3])
            rows.append((x, y, z, int(fields[3]), int(fields[4])))
    if not rows:
        raise ValueError(f"No scattered points found in {path}")
    return np.asarray(rows, dtype=float), metadata


def read_well_locations() -> dict[str, tuple[float, float]]:
    locations: dict[str, tuple[float, float]] = {}
    header = re.compile(r'"([^"]+)"\s+"([^"]+)"\s*$')
    for line in WELL_TOPS.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith("#") or line.startswith("VERSION") or line.startswith("BEGIN"):
            continue
        match = header.search(line)
        fields = line.split()
        if not match or len(fields) < 5:
            continue
        _surface, well = match.groups()
        try:
            x, y, z, _md, twt = map(float, fields[:5])
        except ValueError:
            continue
        if x <= 0 or y <= 0:
            continue
        locations.setdefault(well, (x, y))
    return locations


def nearest_values(points: np.ndarray, targets: np.ndarray) -> np.ndarray:
    # EarthVision exports contain occasional no-data/sentinel depths in the
    # millions of metres.  Danish sedimentary horizons in this model are well
    # within 10 km of mean sea level, so reject those values before sampling.
    valid = points[(np.abs(points[:, 2]) > 10.0) & (np.abs(points[:, 2]) < 10_000.0)]
    coordinates = valid[:, :2]
    values = valid[:, 2]
    result = np.empty(len(targets), dtype=float)
    block_size = 512
    for start in range(0, len(targets), block_size):
        block = targets[start:start + block_size]
        distances = ((block[:, None, 0] - coordinates[None, :, 0]) ** 2
                     + (block[:, None, 1] - coordinates[None, :, 1]) ** 2)
        result[start:start + len(block)] = values[np.argmin(distances, axis=1)]
    return result


def aligned_horizon_samples(
    fjerritslev: np.ndarray, gassum: np.ndarray, vinding: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return source cells where all three supplied depth horizons agree.

    EarthVision exports can contain different no-data cells in each surface.
    Sampling each file independently can therefore combine unrelated cells and
    produce negative thicknesses or isolated kilometre-scale spikes.  The
    column/row indices in the exports let us keep only co-located, ordered
    horizon triplets before resampling.
    """
    def by_index(points: np.ndarray) -> dict[tuple[int, int], tuple[float, float, float]]:
        return {(int(row[3]), int(row[4])): (row[0], row[1], row[2]) for row in points}

    fj = by_index(fjerritslev)
    ga = by_index(gassum)
    vi = by_index(vinding)
    records: list[tuple[float, float, float, float, float]] = []
    for key in sorted(set(fj) & set(ga) & set(vi)):
        f, g, v = fj[key], ga[key], vi[key]
        # Values are negative TVDSS in the supplied exports: Fjerritslev is
        # shallower than Gassum, which is shallower than Vinding.
        if not all(10.0 < abs(item[2]) < 10_000.0 for item in (f, g, v)):
            continue
        if not (f[2] > g[2] > v[2]):
            continue
        records.append((f[0], f[1], f[2], g[2], v[2]))
    if not records:
        raise ValueError("No co-located, ordered Area C horizon triplets survived filtering")
    values = np.asarray(records, dtype=float)
    return values[:, :2], values[:, 2], values[:, 3], values[:, 4]


def nearest_from_samples(coordinates: np.ndarray, values: np.ndarray, targets: np.ndarray) -> np.ndarray:
    points = np.column_stack((coordinates, values))
    return nearest_values(points, targets)


def wgs84_to_utm32(latitude: float, longitude: float) -> tuple[float, float]:
    """Convert a Danish WGS84 point to UTM zone 32N without external GIS deps."""
    a = 6378137.0
    ecc_sq = 0.00669438
    k0 = 0.9996
    lat = math.radians(latitude)
    lon = math.radians(longitude)
    lon0 = math.radians(9.0)
    ecc_prime_sq = ecc_sq / (1 - ecc_sq)
    n = a / math.sqrt(1 - ecc_sq * math.sin(lat) ** 2)
    t = math.tan(lat) ** 2
    c = ecc_prime_sq * math.cos(lat) ** 2
    aa = math.cos(lat) * (lon - lon0)
    m = a * ((1 - ecc_sq / 4 - 3 * ecc_sq**2 / 64 - 5 * ecc_sq**3 / 256) * lat
             - (3 * ecc_sq / 8 + 3 * ecc_sq**2 / 32 + 45 * ecc_sq**3 / 1024) * math.sin(2 * lat)
             + (15 * ecc_sq**2 / 256 + 45 * ecc_sq**3 / 1024) * math.sin(4 * lat)
             - (35 * ecc_sq**3 / 3072) * math.sin(6 * lat))
    easting = k0 * n * (aa + (1 - t + c) * aa**3 / 6
                        + (5 - 18 * t + t**2 + 72 * c - 58 * ecc_prime_sq) * aa**5 / 120) + 500000
    northing = k0 * (m + n * math.tan(lat) * (aa**2 / 2
                 + (5 - t + 9 * c + 4 * c**2) * aa**4 / 24
                 + (61 - 58 * t + t**2 + 600 * c - 330 * ecc_prime_sq) * aa**6 / 720))
    return easting, northing


def sites(wells: dict[str, tuple[float, float]]) -> list[dict[str, object]]:
    known = {
        "Gassum": ("CO2 storage structure", "Gassum-1"),
        "Stenlille": ("CO2 storage structure and natural-gas storage", "Stenlille-01"),
        "Rødby": ("CO2 storage structure", "Rødby-1"),
        "Thisted geothermal": ("geothermal plant", "Thisted-1"),
        "Inez": ("CO2 storage structure", "Inez-1"),
    }
    approximate = {
        "Thorning": (56.29, 9.40),
        "Havnsø": (55.75, 11.30),
        "Jammerbugt": (57.15, 9.35),
        "Lisa": (57.35, 9.65),
        "Aarhus geothermal": (56.17, 10.18),
        "Copenhagen/Amager geothermal": (55.65, 12.63),
    }
    output: list[dict[str, object]] = []
    for name, (kind, well) in known.items():
        if well not in wells:
            continue
        x, y = wells[well]
        output.append({"name": name, "kind": kind, "x_m": x, "y_m": y, "coordinate_source": f"well tops: {well}"})
    for name, (lat, lon) in approximate.items():
        x, y = wgs84_to_utm32(lat, lon)
        output.append({"name": name, "kind": "screening reference site", "x_m": x, "y_m": y,
                       "latitude": lat, "longitude": lon, "coordinate_source": "approximate town/site reference"})
    return output


def find_horizon(*names: str) -> Path:
    for name in names:
        path = HORIZON_ROOT / name
        if path.is_file():
            return path
    expected = ", ".join(str(HORIZON_ROOT / name) for name in names)
    raise FileNotFoundError(f"Missing depth-domain Area C horizon; expected one of: {expected}")


def main() -> None:
    fjerritslev_path = find_horizon("Fjerritslev Formation", "Top Fjerritslev Formation", "Top Fjerritslev")
    top_path = find_horizon("Gassum Formation", "Top Gassum Formation", "Top Gassum")
    base_path = find_horizon("Vinding Formation", "Top Vinding Formation", "Top Vinding")
    fjerritslev_points, fjerritslev_meta = read_scattered(fjerritslev_path)
    top_points, top_meta = read_scattered(top_path)
    base_points, base_meta = read_scattered(base_path)
    wells = read_well_locations()

    source_coordinates, fjerritslev_z, top_z, base_z = aligned_horizon_samples(
        fjerritslev_points, top_points, base_points
    )
    all_points = source_coordinates
    min_x, min_y = np.floor(all_points.min(axis=0) / GRID_SPACING_M) * GRID_SPACING_M
    max_x, max_y = np.ceil(all_points.max(axis=0) / GRID_SPACING_M) * GRID_SPACING_M
    nx = int(round((max_x - min_x) / GRID_SPACING_M))
    ny = int(round((max_y - min_y) / GRID_SPACING_M))
    targets = np.asarray([
        (min_x + (i + 0.5) * GRID_SPACING_M, min_y + (j + 0.5) * GRID_SPACING_M)
        for j in range(ny) for i in range(nx)
    ], dtype=float)

    fjerritslev_depth = -nearest_from_samples(source_coordinates, fjerritslev_z, targets)
    top_depth = -nearest_from_samples(source_coordinates, top_z, targets)
    base_depth = -nearest_from_samples(source_coordinates, base_z, targets)
    gross = base_depth - top_depth
    caprock_thickness = top_depth - fjerritslev_depth

    with CALIBRATION.open(encoding="utf-8") as handle:
        calibration = json.load(handle)
    porosity_model = calibration["porosity_depth_trend"]
    permeability_model = calibration["porosity_permeability_transform"]
    mid_depth = top_depth + gross * 0.5
    porosity = np.clip(porosity_model["intercept"] + porosity_model["slope_per_m"] * mid_depth, 0.12, 0.30)
    permeability = np.clip(10 ** (permeability_model["intercept"] + permeability_model["slope_times_phi"] * porosity), 10.0, 2000.0)
    active = (top_depth >= 800.0) & (gross >= 20.0) & (caprock_thickness >= 20.0) & (base_depth > top_depth)
    thickness_sd = np.maximum(gross * 0.15, 10.0)
    site_records = sites(wells)
    for site in site_records:
        distance = (targets[:, 0] - site["x_m"]) ** 2 + (targets[:, 1] - site["y_m"]) ** 2
        index = int(np.argmin(distance))
        site["i"] = index % nx + 1
        site["j"] = index // nx + 1
        site["in_model_extent"] = bool(min_x <= site["x_m"] <= max_x and min_y <= site["y_m"] <= max_y)
        site["active_cell"] = bool(active[index]) if site["in_model_extent"] else False

    output = {
        "schema_version": "1.0.0",
        "model": "Area C regional pressure-interference screening grid",
        "source": {
            "seal_horizon": str(fjerritslev_path.relative_to(SOURCE_ROOT)),
            "top_horizon": str(top_path.relative_to(SOURCE_ROOT)),
            "base_horizon": str(base_path.relative_to(SOURCE_ROOT)),
            "well_tops": str(WELL_TOPS.relative_to(SOURCE_ROOT)),
            "horizon_vertical_units": "metres TVDSS; supplied depth horizons used directly",
            "crs": "EPSG:23032",
            "vertical_reference": "metres below mean sea level",
        },
        "resolution": {"dx_m": GRID_SPACING_M, "dy_m": GRID_SPACING_M, "nz": NZ,
                       "rationale": "5 km regional screening resolution; preserves 100-300 km pressure interference while keeping the six-layer model near 26,000 cells"},
        "nx": nx, "ny": ny, "nz": NZ,
        "longitude": [], "latitude": [],
        "x_m": targets[:, 0].round(2).tolist(), "y_m": targets[:, 1].round(2).tolist(),
        "seal_depth_m": fjerritslev_depth.round(2).tolist(), "top_depth_m": top_depth.round(2).tolist(),
        "gross_thickness_m": gross.round(2).tolist(), "caprock_thickness_m": caprock_thickness.round(2).tolist(),
        "mid_reservoir_depth_m": mid_depth.round(2).tolist(), "thickness_sd_m": thickness_sd.round(2).tolist(),
        "porosity": porosity.round(5).tolist(), "permeability_md": permeability.round(3).tolist(),
        "ntg": np.full(len(targets), 0.45).tolist(), "temperature_c": np.full(len(targets), 50.9).tolist(),
        "active": active.astype(int).tolist(),
        "well_count": len(wells),
        "wells": [{"name": name, "x_m": xy[0], "y_m": xy[1]} for name, xy in sorted(wells.items())],
        "sites": site_records,
        "limitations": [
            "Regional screening grid; not a history-matched or permit-ready model.",
            "Area C horizons are resampled from supplied depth-domain surfaces.",
            "Area C NTG and temperature are screening defaults pending complete regional property fields.",
            "Sites outside the Area C extent are retained as reference markers but are not simulated.",
            "Only co-located, ordered horizon triplets were resampled; EarthVision no-data/sentinel cells were excluded.",
        ],
    }
    OUTPUT.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "dimensions": [nx, ny, NZ], "cells": int(nx * ny * NZ),
                      "active_cells": int(active.sum()), "wells": len(wells), "sites": len(site_records),
                      "seal_source_grid": fjerritslev_meta, "top_source_grid": top_meta, "base_source_grid": base_meta}, indent=2))


if __name__ == "__main__":
    main()
