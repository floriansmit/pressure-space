# PressureSpace

Interactive regional pressure-management screening for CO2 storage and
geothermal operations, backed by OPM Flow ensemble simulations.

**Live application:** https://floriansmit.github.io/pressure-space/

PressureSpace explores how injection projects, geothermal operations, and fault
transmissibility interact across a shared pressure system. It is designed as a
screening and scenario-comparison tool rather than a calibrated engineering or
permitting model.

## What runs today

- The Gassum view uses 405 completed OPM Flow 2026.04 `CO2STORE` runs: nine
  property realizations, three all-fault transmissibility states, unit-rate
  responses for Storage Alpha, Beta, and Zeta, and five injection durations
  (5, 10, 20, 30 and 40 years), all carried through year 60.
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
- Every available duration has an explicit OPM shut-in schedule, so both
  pressure dissipation and CO2 plume migration continue to update throughout
  the post-injection period. The interface offers only the five simulated
  durations rather than interpolating between nonlinear plume outcomes.
- The same selector exposes marginal P10/P50/P90 porosity, permeability and
  gross-thickness inputs. Geological properties retain a fixed P10–P90 colour
  scale while the percentile changes; mapped structural depth remains fixed.
- The map includes wheel/button zoom, drag pan, OpenStreetMap, four geological
  model properties, eight supplied legacy wells, 29 supplied fault traces, and
  a connected-surface 3D top-structure view. The 3D view follows the geothermal
  explorer controls: orbit/scroll navigation, zoom buttons, top and reset
  camera presets, selectable surface/fault/well layers, vertical exaggeration,
  labelled well paths, and click-to-inspect cells.
- An optional A–A′ cross section opens beneath the map. It samples the actual
  six-layer structural grid and lazy-loads layer-resolved OPM pressure and gas
  saturation for the active duration, fault state and project combination.
  Fault intersections, nearby legacy wells and storage locations are shown in
  the section, and users can replace the default line with two map clicks.
  The section supports button and mouse-wheel zoom up to 8×, with cursor-centred
  wheel zoom and a Fit control to restore the complete A–A′ line.
- The year control includes Play/Pause and 0.5×, 1×, 2× and 4× speeds; map,
  section, plume and selected-cell metrics remain synchronized during playback.
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

## Install OPM on Windows

PressureSpace runs OPM Flow in Ubuntu on WSL2. OPM is not a native Windows
executable, so install WSL2 first and run the simulator from the Ubuntu shell.
The commands below target Ubuntu 24.04, which has official OPM binary packages.

### 1. Install WSL2 and Ubuntu 24.04

Open **PowerShell as Administrator** and run:

```powershell
wsl --install --distribution Ubuntu-24.04
```

Restart Windows when prompted. Then launch **Ubuntu 24.04** from the Start menu
and create the Linux username and password requested by Ubuntu. Confirm that
the distribution is using WSL2 from PowerShell:

```powershell
wsl --list --verbose
wsl --set-version Ubuntu-24.04 2
```

If `wsl --install` is unavailable, enable the Windows features requested by
Windows, restart, and run the command again. Microsoft’s current WSL
instructions are available at <https://learn.microsoft.com/windows/wsl/install>.

### 2. Install OPM Flow in Ubuntu

Run the following commands in the **Ubuntu** terminal, not PowerShell:

```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:opm/ppa
sudo apt update
sudo apt install -y mpi-default-bin libopm-simulators-bin \
  python3-opm-common python3-opm-simulators
```

The packages include the `flow` executable and the optional Python bindings.
Verify the installation:

```bash
command -v flow
flow --version
```

The package names and repository are documented by OPM at
<https://opm-project.org/?page_id=245>.

### 3. Run this repository with OPM

The Windows checkout is available inside WSL under `/mnt`. From Ubuntu:

```bash
cd /mnt/d/python/pressure-space
python3 opm/build_deck.py --rate 1.2 --years 20
flow opm/runs/GASSUM_BASE.DATA --output-dir=opm/runs/output
```

To run the repository’s ensemble workflow:

```bash
cd /mnt/d/python/pressure-space/opm
python3 run_interference_scenarios.py
```

If the repository is stored on another Windows drive, replace `/mnt/d` with
the corresponding WSL mount (for example, `C:\\` is `/mnt/c`).

The helper script [`opm/install-opm-ubuntu.sh`](opm/install-opm-ubuntu.sh)
performs the OPM package installation step from Ubuntu:

```bash
cd /mnt/d/python/pressure-space
bash opm/install-opm-ubuntu.sh
```

The current grid has 41 × 28 × 6 cells (6,816 active). After installation,
the generated OPM cases can be used to reproduce the 405 geological
all-fault/interference response cases.

## Area C regional pressure-interference model

The repository also contains a larger regional screening model built from the
supplied Area C EarthVision horizons and well tops. The Area C horizon exports
are 284 × 232 at approximately 2.5 km spacing, but using that resolution would
create roughly 66,000 horizontal columns before adding vertical layers. The
regional model therefore uses a 5 km × 5 km grid with six layers:

- 58 × 55 × 6 cells (19,140 total cells); and
- 1,953 active surface columns after the 800 m depth, gross-thickness and
  caprock-thickness screening.

This resolution is intended to show pressure interference over roughly
100–300 km while keeping multi-site OPM runs practical. It is not intended to
resolve near-well injectivity, faults at field scale, or plume geometry around
individual wells.

The builder uses the supplied depth-domain Top Fjerritslev, Top Gassum and Top
Vinding horizons directly in metres TVDSS; no TWT-to-depth conversion is
performed. Before resampling, it keeps only co-located, stratigraphically
ordered horizon triplets and excludes EarthVision no-data/sentinel values.
Top Fjerritslev is used as the seal horizon and as an additional
caprock-thickness screening check. NTG and temperature currently use regional
screening defaults because a complete Area C property cube is not included
with the horizon files.

Regenerate the regional grid and site inventory:

```powershell
uv run python opm/build_regional_area_c.py
```

Generate a multi-site regional OPM deck, with all active in-domain reference
sites injecting 1 Mt CO2/year each:

```powershell
uv run python opm/build_regional_deck.py --years 20 --injection-years 20 --output opm/runs/AREA_C_REGIONAL.DATA
```

Generate a smaller scenario using selected sites:

```powershell
uv run python opm/build_regional_deck.py --sites "Gassum,Stenlille,Aarhus geothermal" --rate 1 --years 20 --injection-years 10 --output opm/runs/AREA_C_GASSUM_STENLILLE_AARHUS.DATA
```

The generated site inventory includes the Energistyrelsen storage structures
Gassum, Thorning, Havnsø, Stenlille, Rødby, Jammerbugt, Lisa and Inez, plus
Thisted, Aarhus and Copenhagen/Amager geothermal references. The inventory
also records whether each reference falls inside the horizon footprint and
whether its nearest 5 km column passes the CO2 screening rules. For example,
Thisted is retained but is currently shallower than the 800 m supercritical
CO2 threshold, so it is not selected by the CO2 deck generator. Inez is
outside the Area C horizon footprint and is retained as a reference marker.
Storage-area status and boundaries must be treated as screening information;
see the [Danish Energy Agency overview of CO2 storage licences and planning
areas](https://ens.dk/en/supply-and-consumption/licenses-exploration-and-storage-co2-including-environmental-consultation).

The generated artifacts are [`opm/data/regional-area-c-geological-grid.json`](opm/data/regional-area-c-geological-grid.json),
[`opm/build_regional_area_c.py`](opm/build_regional_area_c.py), and
[`opm/build_regional_deck.py`](opm/build_regional_deck.py).

## Scientific boundary

The included deck represents mapped regional structure and petrophysics, but it
is not a history-matched Gassum field model. Facies-scale architecture,
boundaries, vertical communication, PVT, relative permeability, faults,
stresses, pressure limits, well deliverability, and thermal coupling require
calibration before engineering or regulatory use.

