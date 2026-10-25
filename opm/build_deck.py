"""Generate the geological Gassum OPM Flow CO2STORE screening deck."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONTEXT_PATH = HERE.parent / "dist" / "data" / "regional-context.json"
MODEL_PATH = HERE.parent / "dist" / "data" / "pressure-model.json"
GEOLOGY_PATH = HERE / "data" / "gassum-geological-grid.json"


def load_geology() -> dict:
    return json.loads(GEOLOGY_PATH.read_text(encoding="utf-8"))


def keyword_values(values: list[float] | list[int], per_line: int = 12) -> str:
    rendered = [f"{value:g}" if isinstance(value, float) else str(value) for value in values]
    return "\n".join(" ".join(rendered[start:start + per_line]) for start in range(0, len(rendered), per_line))


def layer_values(surface_values: list[float] | list[int], nz: int) -> list[float] | list[int]:
    return surface_values * nz


def cell_centres_to_nodes(values: list[float], nx: int, ny: int) -> list[float]:
    """Average cell-centre values onto shared corner-point grid nodes."""
    nodes: list[float] = []
    for node_j in range(ny + 1):
        for node_i in range(nx + 1):
            neighbours = []
            for cell_j in (node_j - 1, node_j):
                for cell_i in (node_i - 1, node_i):
                    if 0 <= cell_i < nx and 0 <= cell_j < ny:
                        neighbours.append(values[cell_j * nx + cell_i])
            nodes.append(sum(neighbours) / len(neighbours))
    return nodes


def corner_point_geometry(
    top: list[float], gross: list[float], nx: int, ny: int, nz: int, dx: float, dy: float,
) -> tuple[list[float], list[float]]:
    """Build continuous vertical pillars and shared ZCORN faces.

    Cell-centre horizons are averaged to nodes. Adjacent cells therefore use
    identical corner depths on their common face, avoiding artificial gaps in
    steeply dipping parts of the mapped structure.
    """
    base = [top_depth + thickness for top_depth, thickness in zip(top, gross)]
    top_nodes = cell_centres_to_nodes(top, nx, ny)
    base_nodes = cell_centres_to_nodes(base, nx, ny)
    coord: list[float] = []
    pillar_top = min(top_nodes) - 500.0
    pillar_base = max(base_nodes) + 500.0
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = i * dx, j * dy
            coord.extend((x, y, pillar_top, x, y, pillar_base))

    def boundary(fraction: float) -> list[float]:
        return [a + (b - a) * fraction for a, b in zip(top_nodes, base_nodes)]

    zcorn: list[float] = []
    node_width = nx + 1
    for k in range(nz):
        for surface in (boundary(k / nz), boundary((k + 1) / nz)):
            for j in range(ny):
                for node_j in (j, j + 1):
                    row = node_j * node_width
                    for i in range(nx):
                        zcorn.extend((surface[row + i], surface[row + i + 1]))
    return coord, zcorn


def nearest_grid_cell(lon: float, lat: float, geology: dict) -> tuple[int, int]:
    index = min(
        range(len(geology["longitude"])),
        key=lambda item: (geology["longitude"][item] - lon) ** 2 + (geology["latitude"][item] - lat) ** 2,
    )
    return index % geology["nx"] + 1, index // geology["nx"] + 1


def project_cells(geology: dict) -> dict[str, tuple[int, int]]:
    data = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    reservoir = next(item for item in data["reservoirs"] if item["id"] == "gassum")
    projects = reservoir.get("storage_projects")
    if projects:
        return {project["id"]: nearest_grid_cell(project["lon"], project["lat"], geology)
                for project in projects}
    # Stable screening placements used when a freshly generated analytical base
    # dataset has not yet been enriched with the OPM scenario metadata.
    return {"alpha": (21, 14), "beta": (19, 11), "zeta": (30, 5)}


def _grid_bounds() -> tuple[float, float, float, float]:
    geology = load_geology()
    return min(geology["longitude"]), max(geology["longitude"]), min(geology["latitude"]), max(geology["latitude"])


def all_fault_face_keywords(multiplier: float, nx: int | None = None, ny: int | None = None, nz: int = 6) -> str:
    """Rasterize every supplied fault trace to vertical structured-grid faces."""
    geology = load_geology()
    nx, ny = nx or geology["nx"], ny or geology["ny"]
    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    min_lon, max_lon, min_lat, max_lat = _grid_bounds()
    x_faces: set[tuple[int, int]] = set()
    y_faces: set[tuple[int, int]] = set()

    def grid(point: list[float]) -> tuple[float, float]:
        return ((point[0] - min_lon) / (max_lon - min_lon) * (nx - 1),
                (point[1] - min_lat) / (max_lat - min_lat) * (ny - 1))

    for fault in context["faults"]:
        for start, end in zip(fault["points"], fault["points"][1:]):
            x0, y0 = grid(start)
            x1, y1 = grid(end)
            steps = max(1, math.ceil(max(abs(x1 - x0), abs(y1 - y0)) * 3))
            previous = None
            for step in range(steps + 1):
                fraction = step / steps
                gx, gy = x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction
                if not (0 <= gx <= nx - 1 and 0 <= gy <= ny - 1):
                    previous = None
                    continue
                cell = (round(gx), round(gy))
                if previous and cell != previous:
                    pi, pj = previous
                    ci, cj = cell
                    if ci != pi:
                        x_faces.add((min(ci, pi) + 1, pj + 1))
                    if cj != pj:
                        y_faces.add((ci + 1, min(cj, pj) + 1))
                previous = cell
    lines = [f"MULTX {multiplier} {i} {i} {j} {j} 1 {nz} /" for i, j in sorted(x_faces)]
    lines += [f"MULTY {multiplier} {i} {i} {j} {j} 1 {nz} /" for i, j in sorted(y_faces)]
    return "\n".join(lines)


def build_deck(
    case_name: str,
    rate_mt_yr: float,
    years: int,
    permeability_multiplier: float = 1.0,
    porosity_multiplier: float = 1.0,
    thickness_sigma: float = 0.0,
    fault_state: str = "open",
    second_site: bool = False,
    beta_rate_mt_yr: float = 0.0,
    zeta_rate_mt_yr: float = 0.0,
) -> str:
    geology = load_geology()
    nx, ny, nz = geology["nx"], geology["ny"], geology["nz"]
    top = geology["top_depth_m"]
    gross = [max(5.0, value + thickness_sigma * sd)
             for value, sd in zip(geology["gross_thickness_m"], geology["thickness_sd_m"])]
    coord, zcorn = corner_point_geometry(
        top, gross, nx, ny, nz, geology["dx_m"], geology["dy_m"],
    )
    permx = [max(0.01, value * permeability_multiplier) for value in geology["permeability_md"]]
    permz = [value * 0.1 for value in permx]
    porosity = [min(0.4, max(0.03, value * porosity_multiplier)) for value in geology["porosity"]]
    active = geology["active"]
    cells = project_cells(geology)

    surface_rate = rate_mt_yr * 1.0e9 / 1.87 / 365.25
    if second_site and beta_rate_mt_yr <= 0:
        beta_rate_mt_yr = 1.0
    beta_rate = beta_rate_mt_yr * 1.0e9 / 1.87 / 365.25
    zeta_rate = zeta_rate_mt_yr * 1.0e9 / 1.87 / 365.25
    fault_multiplier = {"open": 1.0, "semi-open": 0.05, "closed": 0.0001}[fault_state]
    alpha_i, alpha_j = cells["alpha"]
    beta_i, beta_j = cells["beta"]
    zeta_i, zeta_j = cells["zeta"]
    min_depth = min(top)
    max_depth = max(value + thickness for value, thickness in zip(top, gross))
    median_temperature = sorted(geology["temperature_c"])[len(geology["temperature_c"]) // 2]

    beta_welspec = f"INJ2 'STORAGE' {beta_i} {beta_j} 1* GAS /" if beta_rate_mt_yr > 0 else ""
    beta_compdat = f"INJ2 {beta_i} {beta_j} 1 {nz} OPEN 2* 0.3 /" if beta_rate_mt_yr > 0 else ""
    beta_winjgas = "INJ2 STREAM CO2STREAM /" if beta_rate_mt_yr > 0 else ""
    beta_wconinje = f"INJ2 GAS OPEN RATE {round(beta_rate)} 1* 285 /" if beta_rate_mt_yr > 0 else ""
    zeta_welspec = f"INJ3 'STORAGE' {zeta_i} {zeta_j} 1* GAS /" if zeta_rate_mt_yr > 0 else ""
    zeta_compdat = f"INJ3 {zeta_i} {zeta_j} 1 {nz} OPEN 2* 0.3 /" if zeta_rate_mt_yr > 0 else ""
    zeta_winjgas = "INJ3 STREAM CO2STREAM /" if zeta_rate_mt_yr > 0 else ""
    zeta_wconinje = f"INJ3 GAS OPEN RATE {round(zeta_rate)} 1* 285 /" if zeta_rate_mt_yr > 0 else ""

    return f"""-- PressureSpace geological Gassum regional screening model
-- EarthVision structure and spatial petrophysics; not calibrated for permitting.
RUNSPEC
TITLE
PRESSURE SPACE - {case_name.upper()}
START
1 'JAN' 2027 /
METRIC
CO2STORE
COMPS
2 /
DIMENS
{nx} {ny} {nz} /
TABDIMS
1 1 40 40 /
EQLDIMS
1 1* 20 1 20 /
REGDIMS
10 1 0 1 0 /
WELLDIMS
4 30 1 3 /
GASWAT
UNIFOUT
UNIFIN

GRID
INIT
COORD
{keyword_values(coord)} /
ZCORN
{keyword_values(zcorn)} /
ACTNUM
{keyword_values(layer_values(active, nz))} /
PORO
{keyword_values(layer_values(porosity, nz))} /
NTG
{keyword_values(layer_values(geology['ntg'], nz))} /
PERMX
{keyword_values(layer_values(permx, nz))} /
PERMY
{keyword_values(layer_values(permx, nz))} /
PERMZ
{keyword_values(layer_values(permz, nz))} /

EDIT
MULTIPLY
PORV 1000000 1 1 1 {ny} 1 {nz} /
PORV 1000000 {nx} {nx} 1 {ny} 1 {nz} /
PORV 1000000 1 {nx} 1 1 1 {nz} /
PORV 1000000 1 {nx} {ny} {ny} 1 {nz} /
{all_fault_face_keywords(fault_multiplier, nx, ny, nz)}
/

PROPS
ROCK
200 5e-05 /
RTEMP
{median_temperature:g} /
NCOMPS
2 /
CNAMES
'CO2'
'H2O' /
ZMFVD
{min_depth:g} 0 1.0
{max_depth:g} 0 1.0 /
WSF
0.20 0.0
0.40 0.1
0.80 0.5
1.00 1.0 /
GSF
0.00 0.0 0.0
0.08 0.001 0.0
0.17 0.01 0.0
0.35 0.05 0.0
0.53 0.20 0.0
0.62 0.35 0.0
0.71 0.56 0.0
0.80 1.0 0.0 /

SOLUTION
EQUIL
1800 180 {min_depth - 200:g} 0 {min_depth - 200:g} 0 /
RPTRST
'BASIC=2' 'PRES' 'SGAS' /

SUMMARY
ALL
WBHP
'INJ1' /
WGIR
'INJ1' /

SCHEDULE
RPTRST
'BASIC=2' 'PRES' 'SGAS' /
WELLSTRE
'CO2STREAM' 1.0 0.0 /
/
WELSPECS
INJ1 'STORAGE' {alpha_i} {alpha_j} 1* GAS /
{beta_welspec}
{zeta_welspec}
/
COMPDAT
INJ1 {alpha_i} {alpha_j} 1 {nz} OPEN 2* 0.3 /
{beta_compdat}
{zeta_compdat}
/
WINJGAS
INJ1 STREAM CO2STREAM /
{beta_winjgas}
{zeta_winjgas}
/
WCONINJE
INJ1 GAS OPEN RATE {round(surface_rate)} 1* 285 /
{beta_wconinje}
{zeta_wconinje}
/
TSTEP
{years}*365 /
END
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="gassum_geological")
    parser.add_argument("--rate", type=float, default=1.0, help="Mt CO2/year")
    parser.add_argument("--years", type=int, default=20)
    parser.add_argument("--permeability-multiplier", type=float, default=1.0)
    parser.add_argument("--porosity-multiplier", type=float, default=1.0)
    parser.add_argument("--thickness-sigma", type=float, default=0.0)
    parser.add_argument("--fault-state", choices=("open", "semi-open", "closed"), default="open")
    parser.add_argument("--second-site", action="store_true")
    parser.add_argument("--beta-rate", type=float, default=0.0)
    parser.add_argument("--zeta-rate", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=Path("runs/GASSUM_GEOLOGICAL.DATA"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(build_deck(
            args.case, args.rate, args.years,
            args.permeability_multiplier, args.porosity_multiplier, args.thickness_sigma,
            args.fault_state, args.second_site, args.beta_rate, args.zeta_rate,
        ))
    print(args.output.resolve())


if __name__ == "__main__":
    main()
