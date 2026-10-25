"""Export the DECODE Gassum geological model to the OPM screening grid.

Run from the parent DECODE workspace. The resulting compact JSON is committed
with PressureSpace so the public reference deck can be regenerated without
redistributing the much larger working NetCDF model.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr
from pyproj import Transformer
from scipy.ndimage import distance_transform_edt


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
ARCHITECTURE = WORKSPACE / "apps" / "web" / "public" / "data" / "architecture-3d.json"
PROPERTIES = WORKSPACE / "data" / "derived" / "gassum__pythermogis_input.nc"
OUTPUT = HERE / "data" / "gassum-geological-grid.json"


def rounded(values: np.ndarray, decimals: int) -> list[float]:
    return np.round(np.asarray(values, dtype=float), decimals).tolist()


def main() -> None:
    architecture = json.loads(ARCHITECTURE.read_text(encoding="utf-8"))
    grid = architecture["grid"]
    horizons = {item["id"]: np.asarray(item["depths_m_bmsl"], dtype=float) for item in architecture["horizons"]}
    top = horizons["top_gassum"]
    base = horizons["top_vinding"]

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:23032", always_xy=True)
    eastings, northings = transformer.transform(grid["longitude"], grid["latitude"])
    with xr.open_dataset(PROPERTIES) as dataset:
        sampled = {}
        for name in ("porosity", "permeability", "ntg", "temperature", "thickness_sd"):
            values = np.asarray(dataset[name].values, dtype=float)
            invalid = ~np.isfinite(values)
            if invalid.any():
                nearest = distance_transform_edt(invalid, return_distances=False, return_indices=True)
                values = values[tuple(nearest)]
            filled = xr.DataArray(values, coords=dataset[name].coords, dims=dataset[name].dims)
            sampled[name] = np.asarray(
                filled.interp(
                    x=("cell", eastings), y=("cell", northings),
                    kwargs={"fill_value": None},
                ).values,
                dtype=float,
            )

    gross_thickness = np.maximum(base - top, 0.0)
    active = (
        (top >= 800.0)
        & (gross_thickness >= 5.0)
        & np.isfinite(sampled["porosity"])
        & np.isfinite(sampled["permeability"])
    )
    medians = {name: float(np.nanmedian(values[active])) for name, values in sampled.items()}
    for name in ("porosity", "permeability", "ntg", "temperature", "thickness_sd"):
        sampled[name] = np.where(np.isfinite(sampled[name]), sampled[name], medians[name])

    output = {
        "schema_version": "1.0.0",
        "source": {
            "geometry": "DECODE EarthVision top Gassum and top Vinding horizons",
            "properties": "gassum__pythermogis_input.nc",
            "property_method": "linear interpolation from the 500 m EPSG:23032 grid to the 2 km architecture nodes",
            "crs": architecture["crs"],
            "vertical_reference": architecture["vertical_reference"],
        },
        "nx": grid["cols"], "ny": grid["rows"], "nz": 6,
        "dx_m": grid["spacing_m"], "dy_m": grid["spacing_m"],
        "longitude": rounded(np.asarray(grid["longitude"]), 6),
        "latitude": rounded(np.asarray(grid["latitude"]), 6),
        "top_depth_m": rounded(top, 1),
        "gross_thickness_m": rounded(gross_thickness, 1),
        "thickness_sd_m": rounded(sampled["thickness_sd"], 2),
        "porosity": rounded(np.clip(sampled["porosity"], 0.03, 0.4), 5),
        "permeability_md": rounded(np.clip(sampled["permeability"], 0.01, None), 3),
        "ntg": rounded(np.clip(sampled["ntg"], 0.01, 1.0), 5),
        "temperature_c": rounded(sampled["temperature"], 2),
        "active": active.astype(int).tolist(),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    print(f"{OUTPUT} ({int(active.sum())}/{active.size} active surface cells)")


if __name__ == "__main__":
    main()
