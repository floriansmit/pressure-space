# DECODE Pressure Space

Separate MVP for regional pressure management across CO2 storage and geothermal operations.

## What runs today

- The Gassum view uses a completed nine-case OPM Flow 2026.04 `CO2STORE`
  screening ensemble at 1 Mt CO2/year for 20 years.
- The interface reads simulated cell pressure and `SGAS` directly from OPM
  restart files and exposes pressure P10/P50/P90 plus a CO2 plume layer.
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

Run and merge the nine-case OPM ensemble from Ubuntu WSL:

```bash
cd /mnt/c/GGS/decode-3d/sites/decode-pressure/opm
python3 run_ensemble.py
```

## OPM runtime on Windows

OPM runs in the installed Ubuntu 24.04 WSL2 distribution. OPM Flow 2026.04 and
its Python bindings have been verified on this machine. The initial 18,000-cell,
240-report validation case and all nine annual-report ensemble cases completed
successfully.

## Scientific boundary

The included deck is a generic regional screening model, not a calibrated
Gassum field model. Permeability architecture, boundaries, vertical
communication, PVT, relative permeability, faults, stresses, pressure limits,
well deliverability, and thermal coupling require calibration before engineering
or regulatory use.

