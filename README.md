# DECODE Pressure Space

Separate MVP for regional pressure management across CO2 storage and geothermal operations.

## What runs today

- The Gassum view uses 54 completed OPM Flow 2026.04 `CO2STORE` runs: nine
  property realizations, three supplied-fault transmissibility states, and
  single-project versus dual-project injection at 1 Mt CO2/year for 20 years.
- The interface reads simulated cell pressure and `SGAS` directly from OPM
  restart files and exposes pressure P10/P50/P90 plus a CO2 plume layer.
- The map includes wheel/button zoom, drag pan, OpenStreetMap, four underlying
  geology properties, eight supplied legacy wells, and 29 supplied fault traces.
- Supplied fault Polygon 23 is represented as a vertical Gassum baffle with
  open (1.0), semi-open (0.05), and closed (0.0001) transmissibility multipliers.
- Storage Alpha and Beta are explicit screening placements on opposing sides of
  that fault. They are not optimized or proposed development locations.
- Every reservoir is screened against the 800 m supercritical-CO2 depth rule.
  Frederikshavn begins at 800.1 m in this regional model and is flagged as
  borderline; shallow Chalk is excluded.
- The other formations retain the 160-member analytical proxy and are labelled
  separately in the interface.
- `opm/build_deck.py` generates a regional model with configurable rate,
  duration, permeability, porosity, and thickness.

Generate the browser dataset:

```powershell
uv run python sites/decode-pressure/simulation/generate_ensemble.py
```

Generate an individual OPM deck:

```powershell
uv run python sites/decode-pressure/opm/build_deck.py --rate 1.2 --years 20
```

Run and merge the fault/interference OPM ensemble from Ubuntu WSL:

```bash
cd /mnt/c/GGS/decode-3d/sites/decode-pressure/opm
python3 run_interference_scenarios.py
```

## OPM runtime on Windows

OPM runs in the installed Ubuntu 24.04 WSL2 distribution. OPM Flow 2026.04 and
its Python bindings have been verified on this machine. The initial 18,000-cell,
240-report validation case, nine base ensemble cases, and all 54 fault and
interference cases completed successfully.

## Scientific boundary

The included deck is a generic regional screening model, not a calibrated
Gassum field model. Permeability architecture, boundaries, vertical
communication, PVT, relative permeability, faults, stresses, pressure limits,
well deliverability, and thermal coupling require calibration before engineering
or regulatory use.

