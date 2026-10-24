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
4 30 1 2 /
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
/
COMPDAT
INJ1 {well_i} {well_j} 1 {nz} OPEN 2* 0.3 /
{beta_compdat}
/
WINJGAS
INJ1 STREAM CO2STREAM /
{beta_winjgas}
/
WCONINJE
INJ1 GAS OPEN RATE {surface_rate_sm3_day} 1* {max_bhp_bar} /
{beta_wconinje}
/
TSTEP
{tsteps} /
END
"""


def build_deck(
    case_name: str,
    rate_mt_yr: float,
    years: int,
    permeability_md: float = 250.0,
    porosity: float = 0.22,
    thickness_m: float = 72.0,
    fault_state: str = "open",
    second_site: bool = False,
) -> str:
    nx, ny, nz = 60, 50, 6
    layer_thickness_m = thickness_m / nz
    top_depth_m = 1800.0
    # OPM's CO2 surface-volume convention depends on the selected PVT model.
    # This MVP conversion is a documented scenario parameter, not a mass audit.
    surface_rate = rate_mt_yr * 1.0e9 / 1.87 / 365.25
    fault_multiplier = {"open": 1.0, "semi-open": 0.05, "closed": 0.0001}[fault_state]
    # Polygon 23 is the supplied E-W trace nearest the reference injector. Its
    # Gassum intersection maps to the J=23 interface over I=27..31. MULTY is
    # applied through every layer, making the screening fault vertical.
    fault_multiply = f"MULTY {fault_multiplier} 27 31 23 23 1 {nz} /"
    beta_welspec = "INJ2 'STORAGE' 28 20 1* GAS /" if second_site else ""
    beta_compdat = f"INJ2 28 20 1 {nz} OPEN 2* 0.3 /" if second_site else ""
    beta_winjgas = "INJ2 STREAM CO2STREAM /" if second_site else ""
    beta_wconinje = f"INJ2 GAS OPEN RATE {round(surface_rate)} 1* 285 /" if second_site else ""
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
        ),
        encoding="utf-8",
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()

