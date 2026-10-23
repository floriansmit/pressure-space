"""Build the browser-safe pressure-management MVP dataset.

This creates an analytical radial-diffusivity ensemble from DECODE's existing
regional reservoir grid. It is deliberately labelled as a proxy in the UI; the
OPM deck generator in ``opm/build_deck.py`` is the full-physics hand-off.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.special import exp1


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "apps" / "web" / "public" / "data" / "model-preview.json"
OUTPUT = ROOT / "sites" / "decode-pressure" / "dist" / "data" / "pressure-model.json"

TIMES_YEARS = np.array([1, 5, 10, 20, 30, 40], dtype=float)
REFERENCE_RATE_MT_YR = 1.0
CO2_DENSITY_KG_M3 = 650.0
BRINE_VISCOSITY_PA_S = 0.00055
TOTAL_COMPRESSIBILITY_PA_INV = 7.0e-10


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def pressure_bar(
    distance_m: float,
    time_years: float,
    permeability_md: np.ndarray,
    thickness_m: np.ndarray,
    porosity: np.ndarray,
    boundary_factor: np.ndarray,
) -> np.ndarray:
    """Theis-style pressure response for screening, not an OPM replacement."""
    k_m2 = np.maximum(permeability_md, 1.0) * 9.869233e-16
    h = np.maximum(thickness_m, 5.0)
    phi = np.clip(porosity, 0.05, 0.4)
    q_m3_s = REFERENCE_RATE_MT_YR * 1.0e9 / CO2_DENSITY_KG_M3 / (365.25 * 86400)
    seconds = max(time_years, 1 / 365.25) * 365.25 * 86400
    radius = max(distance_m, 350.0)
    diffusivity = k_m2 / (phi * BRINE_VISCOSITY_PA_S * TOTAL_COMPRESSIBILITY_PA_INV)
    u = radius**2 / np.maximum(4 * diffusivity * seconds, 1e-30)
    dp_pa = q_m3_s * BRINE_VISCOSITY_PA_S / (4 * math.pi * k_m2 * h) * exp1(np.clip(u, 1e-12, 100))
    return np.maximum(dp_pa * boundary_factor / 1e5, 0.0)


def build() -> dict:
    model = json.loads(SOURCE.read_text(encoding="utf-8"))
    rng = np.random.default_rng(20261023)
    reservoirs = []

    for reservoir in model["reservoirs"]:
        valid = [p for p in reservoir["points"] if p.get("valid_mask") == 1]
        if not valid:
            continue
        centre = valid[len(valid) // 2]
        samples = 160
        permeability_factor = rng.lognormal(mean=0.0, sigma=0.38, size=samples)
        thickness_factor = np.clip(rng.normal(1.0, 0.16, size=samples), 0.55, 1.5)
        porosity_factor = np.clip(rng.normal(1.0, 0.08, size=samples), 0.75, 1.25)
        boundary_factor = np.clip(rng.normal(1.0, 0.22, size=samples), 0.55, 1.8)
        output_points = []

        stride = max(1, len(valid) // 900)
        for point in valid[::stride]:
            distance = haversine_m(centre["lon"], centre["lat"], point["lon"], point["lat"])
            k = np.full(samples, max(point.get("permeability", 80.0), 1.0)) * permeability_factor
            h = np.full(samples, max(point.get("thickness_mean", 30.0) * point.get("ntg", 0.6), 5.0)) * thickness_factor
            phi = np.full(samples, max(point.get("porosity", 0.16), 0.05)) * porosity_factor
            quantiles = []
            for year in TIMES_YEARS:
                values = pressure_bar(distance, year, k, h, phi, boundary_factor)
                quantiles.append([round(float(x), 3) for x in np.quantile(values, [0.1, 0.5, 0.9])])
            output_points.append({
                "lon": round(point["lon"], 6),
                "lat": round(point["lat"], 6),
                "depth_m": round(point.get("top_depth", 0.0), 1),
                "thickness_m": round(point.get("thickness_mean", 0.0), 1),
                "permeability_md": round(point.get("permeability", 0.0), 1),
                "porosity": round(point.get("porosity", 0.0), 3),
                "pressure_bar": quantiles,
            })

        reservoirs.append({
            "id": reservoir["id"],
            "name": reservoir["name"],
            "assessment_type": reservoir["assessment_type"],
            "reference_injector": {"lon": centre["lon"], "lat": centre["lat"]},
            "points": output_points,
        })

    return {
        "model_version": "decode-pressure-proxy-0.1.0",
        "source_model_version": model["model_version"],
        "engine": "analytical radial-diffusivity ensemble",
        "is_opm_result": False,
        "reference_rate_mt_yr": REFERENCE_RATE_MT_YR,
        "times_years": TIMES_YEARS.astype(int).tolist(),
        "percentiles": [10, 50, 90],
        "ensemble_size": 160,
        "reservoirs": reservoirs,
        "limitations": [
            "Screening proxy only; not a CO2STORE simulation.",
            "Rate scaling is approximately linear and does not resolve multiphase near-well effects.",
            "Fault thresholds and geomechanical coupling are illustrative until calibrated data are supplied.",
        ],
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), separators=(",", ":")), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()

