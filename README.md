# DECODE Pressure Space

Separate MVP for regional pressure management across CO2 storage and geothermal operations.

## What runs today

- The published static site uses a 160-member analytical radial-diffusivity ensemble generated from the existing DECODE reservoir grid.
- Every proxy result is labelled; it is not presented as OPM output.
- `opm/build_deck.py` generates an OPM Flow `CO2STORE` deck with configurable rate and duration.

Generate the browser dataset:

```powershell
uv run python sites/decode-pressure/simulation/generate_ensemble.py
```

Generate a full-physics deck:

```powershell
uv run python sites/decode-pressure/opm/build_deck.py --rate 1.2 --years 20
```

## OPM runtime on Windows

OPM's supported Windows path is WSL2. After installing Ubuntu 24.04, run
`opm/install-opm-ubuntu.sh` inside that distribution. The current host does not
have WSL or Docker installed, so the OPM deck is generated but has not been run.

## Scientific boundary

The included deck is a generic regional screening model. Permeability, boundary
conditions, vertical communication, PVT, relative permeability, fault
transmissibility, stresses, and pressure thresholds require calibration before
engineering or regulatory use.

