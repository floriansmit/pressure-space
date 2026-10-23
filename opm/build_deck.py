"""Generate a compact OPM Flow CO2STORE regional screening deck.

The model is a deliberately generic homogeneous regional aquifer. Replace the
properties and boundaries with calibrated geological inputs before decisions.
The keyword structure follows OPM's public CO2STORE_GASWAT regression example.
"""

from __future__ import annotations

import argparse
from pathlib import Path


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
4 30 1 1 /
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
'BASIC=2' 'ALLPROPS' /

SUMMARY
ALL
WBHP
'INJ1' /
WGIR
'INJ1' /

SCHEDULE
RPTRST
'BASIC=2' 'ALLPROPS' /
WELLSTRE
'CO2STREAM' 1.0 0.0 /
/
WELSPECS
INJ1 'STORAGE' {well_i} {well_j} 1* GAS /
/
COMPDAT
INJ1 {well_i} {well_j} 1 {nz} OPEN 2* 0.3 /
/
WINJGAS
INJ1 STREAM CO2STREAM /
/
WCONINJE
INJ1 GAS OPEN RATE {surface_rate_sm3_day} 1* {max_bhp_bar} /
/
TSTEP
{tsteps} /
END
"""


def build_deck(case_name: str, rate_mt_yr: float, years: int) -> str:
    nx, ny, nz = 60, 50, 6
    layer_thickness_m = 12.0
    top_depth_m = 1800.0
    # OPM's CO2 surface-volume convention depends on the selected PVT model.
    # This MVP conversion is a documented scenario parameter, not a mass audit.
    surface_rate = rate_mt_yr * 1.0e9 / 1.87 / 365.25
    return TEMPLATE.format(
        case_name=case_name.upper(), nx=nx, ny=ny, nz=nz, nxy=nx * ny,
        top_depth_m=top_depth_m, bottom_depth_m=top_depth_m + nz * layer_thickness_m,
        datum_depth_m=top_depth_m - 200, cell_size_m=2000,
        layer_thickness_m=layer_thickness_m, permeability_md=250,
        vertical_permeability_md=25, porosity=0.22,
        rock_compressibility_bar_inv="5e-05", temperature_c=65,
        initial_pressure_bar=180, well_i=nx // 2, well_j=ny // 2,
        surface_rate_sm3_day=round(surface_rate), max_bhp_bar=285,
        tsteps=" ".join(["12*30"] * years),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="gassum_base")
    parser.add_argument("--rate", type=float, default=1.0, help="Mt CO2/year")
    parser.add_argument("--years", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("runs/GASSUM_BASE.DATA"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_deck(args.case, args.rate, args.years), encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()

