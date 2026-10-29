"""Generate an OPM Flow CO2STORE deck for the Area C regional grid."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_deck import corner_point_geometry, keyword_values, layer_values


HERE = Path(__file__).resolve().parent
GEOLOGY = HERE / "data" / "regional-area-c-geological-grid.json"


def build_deck(case: str, rate: float, years: int, injection_years: int, selected_sites: list[str]) -> str:
    geology = json.loads(GEOLOGY.read_text(encoding="utf-8"))
    nx, ny, nz = geology["nx"], geology["ny"], geology["nz"]
    sites = [site for site in geology["sites"] if site["active_cell"] and site["in_model_extent"]]
    if selected_sites:
        wanted = {item.casefold().strip() for item in selected_sites}
        sites = [site for site in sites if site["name"].casefold() in wanted]
    if not sites:
        raise ValueError("No active in-domain sites selected")
    if injection_years < 1 or injection_years > years:
        raise ValueError("injection-years must be between 1 and years")

    top = geology["top_depth_m"]
    gross = [max(20.0, value) for value in geology["gross_thickness_m"]]
    coord, zcorn = corner_point_geometry(top, gross, nx, ny, nz, geology["resolution"]["dx_m"], geology["resolution"]["dy_m"])
    permx = geology["permeability_md"]
    permz = [value * 0.1 for value in permx]
    porosity = geology["porosity"]
    ntg = geology["ntg"]
    min_depth = min(top)
    max_depth = max(value + thickness for value, thickness in zip(top, gross))
    names = [f"INJ{index}" for index in range(1, len(sites) + 1)]
    rate_sm3_day = rate * 1.0e9 / 1.87 / 365.25
    well_specs = "\n".join(f"{well} 'STORAGE' {site['i']} {site['j']} 1* GAS /" for well, site in zip(names, sites))
    compdat = "\n".join(f"{well} {site['i']} {site['j']} 1 {nz} OPEN 2* 0.3 /" for well, site in zip(names, sites))
    winjgas = "\n".join(f"{well} STREAM CO2STREAM /" for well in names)
    wconinje = "\n".join(f"{well} GAS OPEN RATE {round(rate_sm3_day)} 1* 285 /" for well in names)
    shut = "\n".join(f"{well} GAS SHUT RATE 0 1* 285 /" for well in names)
    summary = "\n".join(f"'{well}' /" for well in names)
    if len(names) > 30:
        raise ValueError("Too many sites for the deck WELLDIMS")
    shut_schedule = ""
    if injection_years < years:
        shut_schedule = f"""WCONINJE
{shut}
/
TSTEP
{years - injection_years}*365 /
"""

    return f"""-- PressureSpace Area C regional pressure-interference screening model
-- 5 km grid; supplied Area C depth horizons are used directly (no TWT conversion).
-- Screening model only; not calibrated for permitting or field design.
RUNSPEC
TITLE
PRESSURE SPACE - {case.upper()}
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
{max(4, len(names))} 30 1 3 /
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
{keyword_values(layer_values(geology['active'], nz))} /
PORO
{keyword_values(layer_values(porosity, nz))} /
NTG
{keyword_values(layer_values(ntg, nz))} /
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
PORV 1000000 1 {nx} 1 {ny} {ny} 1 {nz} /
/

PROPS
ROCK
200 5e-05 /
RTEMP
50.9 /
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
{summary}
WGIR
{summary}

SCHEDULE
RPTRST
'BASIC=2' 'PRES' 'SGAS' /
WELLSTRE
'CO2STREAM' 1.0 0.0 /
/
WELSPECS
{well_specs}
/
COMPDAT
{compdat}
/
WINJGAS
{winjgas}
/
WCONINJE
{wconinje}
/
TSTEP
{injection_years}*365 /
{shut_schedule}END
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="area_c_regional")
    parser.add_argument("--rate", type=float, default=1.0, help="Mt CO2/year per selected site")
    parser.add_argument("--years", type=int, default=20)
    parser.add_argument("--injection-years", type=int, default=20)
    parser.add_argument("--sites", help="Comma-separated exact site names; default is all active in-domain sites")
    parser.add_argument("--output", type=Path, default=Path("runs/AREA_C_REGIONAL.DATA"))
    args = parser.parse_args()
    selected = args.sites.split(",") if args.sites else []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_deck(args.case, args.rate, args.years, args.injection_years, selected), encoding="utf-8", newline="\n")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
