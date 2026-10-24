"""Generate a compact OPM Flow CO2STORE regional screening deck.

The model is a deliberately generic homogeneous regional aquifer. Replace the
properties and boundaries with calibrated geological inputs before decisions.
The keyword structure follows OPM's public CO2STORE_GASWAT regression example.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONTEXT_PATH = HERE.parent / "dist" / "data" / "regional-context.json"
MODEL_PATH = HERE.parent / "dist" / "data" / "pressure-model.json"


TEMPLATE = """-- DECODE Pressure Space regional screening model
-- Generic MVP deck. Not calibrated for permitting or operational decisions.
RUNSPEC
TITLE
DECODE PRESSURE SPACE - {case_name}
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
TOPS
{nxy}*{top_depth_m} /
DXV
{nx}*{cell_size_m} /
DYV
{ny}*{cell_size_m} /
DZV
{nz}*{layer_thickness_m} /
EQUALS
PERMX {permeability_md} /
PERMY {permeability_md} /
PERMZ {vertical_permeability_md} /
PORO {porosity} /
/

EDIT
MULTIPLY
PORV 1000000 1 1 1 {ny} 1 {nz} /
PORV 1000000 {nx} {nx} 1 {ny} 1 {nz} /
PORV 1000000 1 {nx} 1 1 1 {nz} /
PORV 1000000 1 {nx} {ny} {ny} 1 {nz} /
{fault_multiply}
/

PROPS
ROCK
200 {rock_compressibility_bar_inv} /
RTEMP
{temperature_c} /
NCOMPS
2 /
CNAMES
'CO2'
'H2O' /
ZMFVD
{top_depth_m} 0 1.0
{bottom_depth_m} 0 1.0 /
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
{top_depth_m} {initial_pressure_bar} {datum_depth_m} 0 {datum_depth_m} 0 /
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
INJ1 'STORAGE' {well_i} {well_j} 1* GAS /
{beta_welspec}
{zeta_welspec}
/
COMPDAT
INJ1 {well_i} {well_j} 1 {nz} OPEN 2* 0.3 /
{beta_compdat}
{zeta_compdat}
/
WINJGAS
INJ1 STREAM CO2STREAM /
{beta_winjgas}
{zeta_winjgas}
/
WCONINJE
INJ1 GAS OPEN RATE {surface_rate_sm3_day} 1* {max_bhp_bar} /
{beta_wconinje}
{zeta_wconinje}
/
TSTEP
{tsteps} /
END
"""


def _grid_bounds() -> tuple[float, float, float, float]:
    data = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    reservoir = next(item for item in data["reservoirs"] if item["id"] == "gassum")
    points = reservoir["points"]
    return (
        min(point["lon"] for point in points), max(point["lon"] for point in points),
        min(point["lat"] for point in points), max(point["lat"] for point in points),
    )


def all_fault_face_keywords(multiplier: float, nx: int = 60, ny: int = 50, nz: int = 6) -> str:
    """Rasterize every supplied fault trace to vertical structured-grid faces."""
    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    min_lon, max_lon, min_lat, max_lat = _grid_bounds()
    x_faces: set[tuple[int, int]] = set()
    y_faces: set[tuple[int, int]] = set()

    def grid(point: list[float]) -> tuple[float, float]:
        return (
            (point[0] - min_lon) / (max_lon - min_lon) * (nx - 1),
            (point[1] - min_lat) / (max_lat - min_lat) * (ny - 1),
        )

    for fault in context["faults"]:
        trace = fault["points"]
        for start, end in zip(trace, trace[1:]):
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
    permeability_md: float = 250.0,
    porosity: float = 0.22,
    thickness_m: float = 72.0,
    fault_state: str = "open",
    second_site: bool = False,
    beta_rate_mt_yr: float = 0.0,
    zeta_rate_mt_yr: float = 0.0,
) -> str:
    nx, ny, nz = 60, 50, 6
    layer_thickness_m = thickness_m / nz
    top_depth_m = 1800.0
    # OPM's CO2 surface-volume convention depends on the selected PVT model.
    # This MVP conversion is a documented scenario parameter, not a mass audit.
    surface_rate = rate_mt_yr * 1.0e9 / 1.87 / 365.25
    fault_multiplier = {"open": 1.0, "semi-open": 0.05, "closed": 0.0001}[fault_state]
    fault_multiply = all_fault_face_keywords(fault_multiplier, nx, ny, nz)
    if second_site and beta_rate_mt_yr <= 0:
        beta_rate_mt_yr = 1.0
    beta_rate = beta_rate_mt_yr * 1.0e9 / 1.87 / 365.25
    zeta_rate = zeta_rate_mt_yr * 1.0e9 / 1.87 / 365.25
    beta_welspec = "INJ2 'STORAGE' 28 20 1* GAS /" if beta_rate_mt_yr > 0 else ""
    beta_compdat = f"INJ2 28 20 1 {nz} OPEN 2* 0.3 /" if beta_rate_mt_yr > 0 else ""
    beta_winjgas = "INJ2 STREAM CO2STREAM /" if beta_rate_mt_yr > 0 else ""
    beta_wconinje = f"INJ2 GAS OPEN RATE {round(beta_rate)} 1* 285 /" if beta_rate_mt_yr > 0 else ""
    # Storage Zeta is anchored to browser cell 192, which maps to I=43, J=9.
    zeta_welspec = "INJ3 'STORAGE' 43 9 1* GAS /" if zeta_rate_mt_yr > 0 else ""
    zeta_compdat = f"INJ3 43 9 1 {nz} OPEN 2* 0.3 /" if zeta_rate_mt_yr > 0 else ""
    zeta_winjgas = "INJ3 STREAM CO2STREAM /" if zeta_rate_mt_yr > 0 else ""
    zeta_wconinje = f"INJ3 GAS OPEN RATE {round(zeta_rate)} 1* 285 /" if zeta_rate_mt_yr > 0 else ""
    return TEMPLATE.format(
        case_name=case_name.upper(), nx=nx, ny=ny, nz=nz, nxy=nx * ny,
        top_depth_m=top_depth_m, bottom_depth_m=top_depth_m + nz * layer_thickness_m,
        datum_depth_m=top_depth_m - 200, cell_size_m=2000,
        layer_thickness_m=layer_thickness_m, permeability_md=permeability_md,
        vertical_permeability_md=permeability_md * 0.1, porosity=porosity,
        rock_compressibility_bar_inv="5e-05", temperature_c=65,
        initial_pressure_bar=180, well_i=nx // 2, well_j=ny // 2,
        surface_rate_sm3_day=round(surface_rate), max_bhp_bar=285,
        fault_multiply=fault_multiply,
        beta_welspec=beta_welspec,
        beta_compdat=beta_compdat,
        beta_winjgas=beta_winjgas,
        beta_wconinje=beta_wconinje,
        zeta_welspec=zeta_welspec,
        zeta_compdat=zeta_compdat,
        zeta_winjgas=zeta_winjgas,
        zeta_wconinje=zeta_wconinje,
        # Annual report steps are sufficient for the explorer and make ensemble
        # runs dramatically smaller than the initial monthly validation case.
        tsteps=f"{years}*365",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="gassum_base")
    parser.add_argument("--rate", type=float, default=1.0, help="Mt CO2/year")
    parser.add_argument("--years", type=int, default=20)
    parser.add_argument("--permeability", type=float, default=250.0, help="Horizontal permeability (mD)")
    parser.add_argument("--porosity", type=float, default=0.22)
    parser.add_argument("--thickness", type=float, default=72.0, help="Total aquifer thickness (m)")
    parser.add_argument("--fault-state", choices=("open", "semi-open", "closed"), default="open")
    parser.add_argument("--second-site", action="store_true", help="Enable Storage Beta south of the modelled fault")
    parser.add_argument("--beta-rate", type=float, default=0.0, help="Storage Beta rate (Mt CO2/year)")
    parser.add_argument("--zeta-rate", type=float, default=0.0, help="Storage Zeta rate (Mt CO2/year at cell 192)")
    parser.add_argument("--output", type=Path, default=Path("runs/GASSUM_BASE.DATA"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        build_deck(
            args.case,
            args.rate,
            args.years,
            permeability_md=args.permeability,
            porosity=args.porosity,
            thickness_m=args.thickness,
            fault_state=args.fault_state,
            second_site=args.second_site,
            beta_rate_mt_yr=args.beta_rate,
            zeta_rate_mt_yr=args.zeta_rate,
        ),
        encoding="utf-8",
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()

