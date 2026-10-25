# PressureSpace

Interactive regional pressure-management screening for CO2 storage and
geothermal operations, backed by OPM Flow ensemble simulations.

**Live application:** https://floriansmit.github.io/pressure-space/

PressureSpace explores how injection projects, geothermal operations, and fault
transmissibility interact across a shared pressure system. It is designed as a
screening and scenario-comparison tool rather than a calibrated engineering or
permitting model.

## What runs today

- The Gassum view uses 81 completed OPM Flow 2026.04 `CO2STORE` runs: nine
  property realizations, three all-fault transmissibility states, and unit-rate
  responses for Storage Alpha, Beta, and Zeta through year 60.
- The OPM grid uses the DECODE EarthVision Top Gassum and Top Vinding surfaces.
  Gassum sand porosity is calculated from a robust depth trend fitted to the
  supplied wells at mid-reservoir TVDSS; permeability is calculated from 1,072
  paired PHIE–PERM_GEUS sand samples. Net-to-gross remains spatially sampled
  from the 500 m property model.
- Shared-node `COORD`/`ZCORN` corner-point geometry keeps neighbouring cells
  hydraulically connected across mapped structural relief and avoids artificial
  stair-step pressure channels.
- The interface reads simulated cell pressure and `SGAS` directly from OPM
  restart files and exposes pressure P10/P50/P90 plus a CO2 plume layer.
- Finite injection durations use time-shifted superposition of the 60-year OPM
  unit pressure response, so the pressure maps and trajectory continue through
  the post-injection period instead of holding the last year-20 result. The CO2
  plume remains fixed after injection stops because post-injection plume
  migration is not yet simulated.
- The same selector exposes marginal P10/P50/P90 porosity, permeability and
  gross-thickness inputs. Geological properties retain a fixed P10–P90 colour
  scale while the percentile changes; mapped structural depth remains fixed.
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
  Cell 192 (OPM I=30, J=5 on the geological grid). They are not optimized or
  proposed development locations.
- Beta and Zeta can each be screened at 1, 2, or 3 Mt CO2/year. The browser
  superposes their 1 Mt/year OPM response increments on Alpha; this is a fast
  screening approximation rather than a fully coupled nonlinear combination.
- Every reservoir is screened against the 800 m supercritical-CO2 depth rule.
  Frederikshavn begins at 800.1 m in this regional model and is flagged as
  borderline; shallow Chalk is excluded.
- The other formations retain the 160-member analytical proxy and are labelled
  separately in the interface.
- `opm/build_deck.py` generates the geological regional model with configurable
  rate, duration, property perturbations and fault state.

## Model transparency

The application includes a **Model assumptions** panel with the inputs and
boundary conditions used by the Gassum OPM ensemble. Reproducibility artifacts
are published with the site:

- [`dist/model/MODEL_ASSUMPTIONS.md`](dist/model/MODEL_ASSUMPTIONS.md) — readable technical disclosure;
- [`dist/data/model-manifest.json`](dist/data/model-manifest.json) — machine-readable parameters and limitations;
- [`dist/model/GASSUM_REFERENCE.DATA`](dist/model/GASSUM_REFERENCE.DATA) — generated reference OPM deck; and
- [`opm/data/gassum-geological-grid.json`](opm/data/gassum-geological-grid.json) — compact mapped grid input; and
- [`opm/data/gassum-petrophysics-calibration.json`](opm/data/gassum-petrophysics-calibration.json) — well observations, fitted depth trend and porosity–permeability transform;
- [`opm/`](opm/) — geological exporter, deck generator and ensemble runners.

The disclosure distinguishes the user-configured pressure screening limit from
a calibrated geomechanical, fracture-pressure, or fault-reactivation limit.

Generate the browser dataset:

```powershell
uv run python simulation/generate_ensemble.py
```

Rebuild the Gassum petrophysical calibration and OPM grid from the parent
DECODE workspace:

```powershell
uv run python opm/calibrate_gassum_petrophysics.py
uv run python opm/export_geological_grid.py
```

Generate an individual OPM deck:

```powershell
uv run python opm/build_deck.py --rate 1.2 --years 20
```

Run and merge the fault/interference OPM ensemble from Ubuntu WSL:

```bash
cd /mnt/c/GGS/decode-3d/sites/decode-pressure/opm
python3 run_interference_scenarios.py
```

## Run locally

From the repository root:

```powershell
node scripts/serve-preview.mjs 4176
```

Then open http://127.0.0.1:4176/.

## GitHub Pages

Pushes to `main` automatically publish the contents of `dist/` through the
GitHub Actions workflow in `.github/workflows/pages.yml`.

- Repository: https://github.com/floriansmit/pressure-space
- Published site: https://floriansmit.github.io/pressure-space/

## OPM runtime on Windows

OPM runs in the installed Ubuntu 24.04 WSL2 distribution. OPM Flow 2026.04 and
its Python bindings have been verified on this machine. The current grid has
41 × 28 × 6 cells (6,816 active), and all 81 geological all-fault/interference
response cases complete successfully.

## Scientific boundary

The included deck represents mapped regional structure and petrophysics, but it
is not a history-matched Gassum field model. Facies-scale architecture,
boundaries, vertical communication, PVT, relative permeability, faults,
stresses, pressure limits, well deliverability, and thermal coupling require
calibration before engineering or regulatory use.

