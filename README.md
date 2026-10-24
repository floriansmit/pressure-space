# DECODE Pressure Space

Separate MVP for regional pressure management across CO2 storage and geothermal operations.

## What runs today

- The Gassum view uses 81 completed OPM Flow 2026.04 `CO2STORE` runs: nine
  property realizations, three all-fault transmissibility states, and unit-rate
  responses for Storage Alpha, Beta, and Zeta over a 20-year injection period.
- The interface reads simulated cell pressure and `SGAS` directly from OPM
  restart files and exposes pressure P10/P50/P90 plus a CO2 plume layer.
- The map includes wheel/button zoom, drag pan, OpenStreetMap, four geological
  model properties, eight supplied legacy wells, 29 supplied fault traces, and
  a connected-surface 3D top-structure view. The 3D view follows the geothermal
  explorer controls: orbit/scroll navigation, zoom buttons, top and reset
  camera presets, selectable surface/fault/well layers, vertical exaggeration,
  labelled well paths, and click-to-inspect cells.
- All 29 supplied faults are represented together as vertical Gassum baffles.
  Every trace receives the selected open (1.0), semi-open (0.05), or closed
  (0.0001) transmissibility multiplier.
- Storage Alpha and Beta are explicit screening placements. Storage Zeta is at
  Cell 192 (OPM I=43, J=9). They are not optimized or proposed development locations.
- Beta and Zeta can each be screened at 1, 2, or 3 Mt CO2/year. The browser
  superposes their 1 Mt/year OPM response increments on Alpha; this is a fast
  screening approximation rather than a fully coupled nonlinear combination.
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
240-report validation case, nine base ensemble cases, and all 81 all-fault and
interference response cases completed successfully.

## Scientific boundary

The included deck is a generic regional screening model, not a calibrated
Gassum field model. Permeability architecture, boundaries, vertical
communication, PVT, relative permeability, faults, stresses, pressure limits,
well deliverability, and thermal coupling require calibration before engineering
or regulatory use.

