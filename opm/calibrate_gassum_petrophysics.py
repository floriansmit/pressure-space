"""Derive Gassum sand porosity and permeability transforms from supplied LAS logs.

The regional OPM grid represents the sand-rich reservoir fraction.  Consequently
the calibration uses samples with Vshale <= 0.40 rather than the median of the
entire Gassum interval (which mixes reservoir sand and shale).  Well depths are
TVDSS values from the supplied formation tops.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
sys.path.insert(0, str(WORKSPACE / "src"))

from decode3d.processing import well_conditioning as wells  # noqa: E402


OUTPUT = HERE / "data" / "gassum-petrophysics-calibration.json"
POROSITY_LIMITS = (0.12, 0.30)
PERMEABILITY_LIMITS_MD = (10.0, 2000.0)


def _theil_sen(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    slopes = [
        (y[j] - y[i]) / (x[j] - x[i])
        for i in range(len(x))
        for j in range(i + 1, len(x))
        if x[j] != x[i]
    ]
    slope = float(np.median(slopes))
    intercept = float(np.median(y - slope * x))
    return slope, intercept


def build_calibration() -> dict:
    observations = []
    paired_porosity: list[np.ndarray] = []
    paired_permeability: list[np.ndarray] = []

    for well in wells.read_study_well_tops().values():
        normalised = {wells._normalise(name): value for name, value in well["tops"].items()}
        top = normalised.get(wells._normalise("Top Gassum in DNB"))
        base = normalised.get(wells._normalise("Top Vinding"))
        las_path = wells._find_las(well["name"])
        if not top or not base or not las_path or base["md"] <= top["md"]:
            continue

        curves, data = wells._read_las(las_path)
        depth_i = wells._curve_index(curves, ("DEPT",))
        porosity_i = wells._curve_index(curves, ("PHIE-iter-1", "PHIE", "NPHI-iter-1", "NPHI"))
        permeability_i = wells._curve_index(curves, ("PERM_GEUS-iter-1",))
        shale_i = wells._curve_index(curves, ("Vshale-iter-1",))
        if depth_i is None or porosity_i is None or shale_i is None:
            continue

        mask = (
            (data[:, depth_i] >= top["md"])
            & (data[:, depth_i] < base["md"])
            & np.isfinite(data[:, shale_i])
            & (data[:, shale_i] >= -0.01)
            & (data[:, shale_i] <= 0.40)
        )
        porosity = data[:, porosity_i]
        porosity_mask = mask & np.isfinite(porosity) & (porosity > 0.02) & (porosity < 0.45)
        if not porosity_mask.any():
            continue

        item = {
            "well": well["name"],
            "mid_reservoir_depth_m_tvdss": round(float(-0.5 * (top["z"] + base["z"])), 2),
            "sand_porosity_median": round(float(np.median(porosity[porosity_mask])), 5),
            "sand_porosity_samples": int(porosity_mask.sum()),
        }
        if permeability_i is not None:
            permeability = data[:, permeability_i]
            pair_mask = porosity_mask & np.isfinite(permeability) & (permeability > 0.001) & (permeability < 100000)
            if pair_mask.any():
                item.update({
                    "sand_permeability_geomean_md": round(float(np.exp(np.mean(np.log(permeability[pair_mask])))), 3),
                    "paired_porosity_permeability_samples": int(pair_mask.sum()),
                })
                paired_porosity.append(porosity[pair_mask])
                paired_permeability.append(permeability[pair_mask])
        observations.append(item)

    depth = np.asarray([item["mid_reservoir_depth_m_tvdss"] for item in observations])
    porosity = np.asarray([item["sand_porosity_median"] for item in observations])
    depth_slope, depth_intercept = _theil_sen(depth, porosity)
    depth_prediction = depth_intercept + depth_slope * depth

    pair_phi = np.concatenate(paired_porosity)
    pair_log_k = np.log10(np.concatenate(paired_permeability))
    permeability_slope, permeability_intercept = np.polyfit(pair_phi, pair_log_k, 1)
    permeability_prediction = permeability_intercept + permeability_slope * pair_phi

    return {
        "schema_version": "1.0.0",
        "formation": "Gassum Formation",
        "source": "Supplied Petrel formation tops and LAS PHIE, Vshale and PERM_GEUS curves",
        "reservoir_sample_rule": "Gassum interval samples with Vshale <= 0.40; PHIE 0.02-0.45",
        "depth_reference": "mid-reservoir TVDSS below mean sea level",
        "well_observations": observations,
        "porosity_depth_trend": {
            "method": "Theil-Sen robust linear fit to well median sand porosity",
            "equation": "phi = intercept + slope_per_m * mid_reservoir_depth_m_tvdss",
            "slope_per_m": round(depth_slope, 10),
            "intercept": round(depth_intercept, 8),
            "rmse_fraction": round(float(np.sqrt(np.mean((porosity - depth_prediction) ** 2))), 5),
            "output_limits_fraction": list(POROSITY_LIMITS),
        },
        "porosity_permeability_transform": {
            "method": "ordinary least squares on paired sand-sample PHIE and log10(PERM_GEUS)",
            "equation": "permeability_md = 10 ** (intercept + slope_times_phi * phi)",
            "slope_times_phi": round(float(permeability_slope), 8),
            "intercept": round(float(permeability_intercept), 8),
            "rmse_log10_md": round(float(np.sqrt(np.mean((pair_log_k - permeability_prediction) ** 2))), 5),
            "sample_count": int(pair_phi.size),
            "output_limits_md": list(PERMEABILITY_LIMITS_MD),
        },
        "limitations": [
            "PERM_GEUS is a supplied log-derived permeability curve, not a new core calibration.",
            "The depth trend is regional and does not resolve local facies or diagenetic changes.",
            "The Voldum-1 low-porosity observation is retained; the robust fit limits its leverage.",
        ],
    }


def main() -> None:
    calibration = build_calibration()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(calibration, indent=2, ensure_ascii=False), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
