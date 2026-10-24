"""Prepare fault traces, legacy wells and CO2 depth-screen metadata for the site."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "sites" / "decode-pressure" / "dist" / "data" / "pressure-model.json"
OUTPUT = ROOT / "sites" / "decode-pressure" / "dist" / "data" / "regional-context.json"
WELL_DIR = ROOT / "all_wells" / "dev"
FAULT_DIR = ROOT / "2026 Model Decode Area" / "Fault sticks CPS-3 lines"


def header_value(lines: list[str], label: str) -> str | None:
    prefix = f"# {label}:"
    for line in lines:
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def read_wells(bounds: dict[str, float], transformer: Transformer) -> list[dict]:
    wells = []
    number = re.compile(r"[-+]?\d+(?:\.\d+)?")
    for path in sorted(WELL_DIR.glob("*.dev")):
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:18]
        x_text = header_value(lines, "WELL HEAD X-COORDINATE")
        y_text = header_value(lines, "WELL HEAD Y-COORDINATE")
        if not x_text or not y_text:
            continue
        x_match, y_match = number.search(x_text), number.search(y_text)
        if not x_match or not y_match:
            continue
        lon, lat = transformer.transform(float(x_match.group()), float(y_match.group()))
        if bounds["min_lon"] <= lon <= bounds["max_lon"] and bounds["min_lat"] <= lat <= bounds["max_lat"]:
            status = header_value(lines, "WELL TYPE") or "STATUS UNKNOWN"
            wells.append({
                "name": path.stem,
                "lon": round(lon, 6),
                "lat": round(lat, 6),
                "status": status.title(),
                "leakage_screen": "legacy well requiring integrity review",
            })
    return wells


def read_faults(bounds: dict[str, float], transformer: Transformer) -> list[dict]:
    faults = []
    for path in sorted(FAULT_DIR.glob("Polygon_*")):
        if path.suffix:
            continue
        points, seen = [], set()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) != 3:
                continue
            try:
                x, y, _ = map(float, parts)
            except ValueError:
                continue
            key = (round(x, 3), round(y, 3))
            if key in seen:
                continue
            seen.add(key)
            lon, lat = transformer.transform(x, y)
            points.append([round(lon, 6), round(lat, 6)])
        if len(points) < 2:
            continue
        intersects = any(
            bounds["min_lon"] - 0.08 <= lon <= bounds["max_lon"] + 0.08
            and bounds["min_lat"] - 0.08 <= lat <= bounds["max_lat"] + 0.08
            for lon, lat in points
        )
        if intersects:
            stride = max(1, len(points) // 120)
            faults.append({"id": path.name.lower(), "name": path.name.replace("_", " "), "points": points[::stride]})
    return faults


def main() -> None:
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    all_points = [point for reservoir in model["reservoirs"] for point in reservoir["points"]]
    bounds = {
        "min_lon": min(point["lon"] for point in all_points),
        "max_lon": max(point["lon"] for point in all_points),
        "min_lat": min(point["lat"] for point in all_points),
        "max_lat": max(point["lat"] for point in all_points),
    }
    transformer = Transformer.from_crs("EPSG:23032", "EPSG:4326", always_xy=True)
    depth_screen = []
    for reservoir in model["reservoirs"]:
        depths = [point["depth_m"] for point in reservoir["points"]]
        eligible = [depth >= 800 for depth in depths]
        depth_screen.append({
            "id": reservoir["id"],
            "name": reservoir["name"],
            "minimum_depth_m": round(min(depths), 1),
            "median_depth_m": round(sorted(depths)[len(depths) // 2], 1),
            "maximum_depth_m": round(max(depths), 1),
            "fraction_at_or_below_800m": round(sum(eligible) / len(eligible), 3),
            "co2_storage_screen": "eligible only where top depth is at least 800 m" if any(eligible) else "not eligible",
        })
    payload = {
        "model_version": "regional-context-0.2.0",
        "coordinate_source": "ED50 / UTM zone 32N supplied Petrel and EarthVision files",
        "bounds": bounds,
        "legacy_wells": read_wells(bounds, transformer),
        "faults": read_faults(bounds, transformer),
        "co2_depth_screen": depth_screen,
        "fault_model_note": "All displayed supplied fault traces are rasterized as one vertical transmissibility set through all six Gassum layers.",
    }
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(payload['legacy_wells'])} wells and {len(payload['faults'])} fault traces to {OUTPUT}")


if __name__ == "__main__":
    main()
