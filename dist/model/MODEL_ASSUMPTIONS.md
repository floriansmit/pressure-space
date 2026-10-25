# PressureSpace Gassum model assumptions

This document records the inputs used for the published Gassum OPM Flow
screening ensemble. The model is reproducible, but it is not history matched or
calibrated for engineering design, induced-seismicity assessment, operational
approval or permitting.

## Geological grid

- OPM Flow 2026.04 in `CO2STORE` mode with CO2 and H2O components.
- Continuous corner-point grid: 41 × 28 × 6, with 1,148 surface cells and
  6,816 active cells.
- Horizontal cell dimensions: 2,000 × 2,000 m.
- The top of every column is the DECODE EarthVision Top Gassum horizon. Active
  top depths range from approximately 948 to 2,341 m below MSL.
- Gross thickness is the mapped interval from Top Gassum to Top Vinding, up to
  approximately 224 m. Each column is divided into six equal-thickness layers.
- Cell-centre horizons are averaged to shared structural nodes and written as
  `COORD`/`ZCORN`. Adjacent columns therefore share the same face geometry;
  steep structure does not create artificial gaps between Cartesian columns.
- Twelve columns thinner than 5 m are inactive. Small property gaps introduced
  at resampling edges are filled from the nearest valid 500 m geological cell.
- Geometry and petrophysics are sampled onto the same 2 km architecture grid
  used by the explorer, so the simulation and map share the same locations.

The compact input is stored in `opm/data/gassum-geological-grid.json`. The
exporter `opm/export_geological_grid.py` combines the EarthVision architecture,
the well-calibrated Gassum sand trend and the 500 m net-to-gross, temperature
and thickness-uncertainty fields.

## Rock and fluid inputs

- Spatial porosity: approximately 0.198–0.300 in active cells.
- Spatial horizontal permeability: approximately 110–1,670 mD in active cells.
- Spatial net-to-gross: approximately 0.365–0.561.
- Vertical permeability: 10% of local horizontal permeability.
- Rock compressibility: 5×10^-5 bar^-1 at a 200 bar reference pressure.
- Initial pressure: 180 bar at the 1,800 m datum, initialized hydrostatically.
- OPM uses the regional median mapped temperature, approximately 50.9 °C. The
  full lateral temperature field remains visible data but is not a lateral
  thermal-flow simulation.
- Relative-permeability and capillary-pressure tables are included verbatim in
  the downloadable reference deck.

### Gassum petrophysical calibration

The OPM cells represent the sand-rich reservoir fraction, so the calibration
uses supplied LAS samples within the Top Gassum–Top Vinding interval for which
`Vshale <= 0.40`. It does not use the median of the complete sand-plus-shale
interval. Five wells provide sand porosity medians: Gassum-1 (0.265 at 1,525 m
mid-reservoir TVDSS), Hobro-1 (0.201 at 2,416 m), Hyllebjerg-1 (0.170 at
2,639 m), Kvols-1 (0.195 at 2,459 m), and Voldum-1 (0.107 at 1,786 m).

A robust Theil-Sen trend limits the leverage of the anomalously low Voldum-1
value while retaining it in the evidence:

`porosity = 0.38608518 - 0.0000796026 × mid-reservoir depth (m TVDSS)`

Values are constrained to 0.12–0.30 outside the calibration support. Each grid
column uses its mapped mid-reservoir depth, calculated halfway between Top
Gassum and Top Vinding. Horizontal permeability is then calculated from 1,072
paired sand-sample PHIE and supplied `PERM_GEUS` observations:

`permeability (mD) = 10 ^ (-0.24105203 + 11.54564195 × porosity)`

`PERM_GEUS` is log-derived rather than a new core calibration. The trend is
therefore more representative of the supplied sand observations but still does
not resolve local facies or diagenetic variation. The complete observations,
fit diagnostics and limits are in
`opm/data/gassum-petrophysics-calibration.json`.

## Boundary conditions

Four operations multiply the pore volume of west, east, south and north edge
cell sets by 1,000,000. This approximates a large connected regional aquifer;
it is not an explicit aquifer model or a calibrated fixed-pressure boundary.
The model top and base are no-flow boundaries.

## Geological uncertainty ensemble

Every realization preserves the mapped spatial patterns. The nine-run L9
design combines:

- permeability multipliers of exp(-0.7), 1 and exp(+0.7);
- porosity multipliers of 0.9, 1.0 and 1.1; and
- gross-thickness adjustments of -1, 0 and +1 mapped thickness standard
  deviation.

These are screening perturbations around the geological model, not nine
history-matched realizations.

The P10/P50/P90 selector also changes the geological property maps. Porosity
shows the 0.9/1.0/1.1 multiplier levels, permeability shows the
0.4966/1.0/2.0138 levels, and gross thickness shows -1/0/+1 mapped standard
deviation. Every property uses one fixed colour scale spanning its displayed
P10–P90 range, so changes in colour represent actual changes in value rather
than legend rescaling. Top depth remains fixed because structural uncertainty
is not included.

These property maps are marginal input percentiles. Pressure and gas saturation
are cell-wise output quantiles across all nine L9 runs, so a P10 property map is
not necessarily the single realization that produces pressure P10 everywhere.

## Fault representation

All 29 supplied map traces are rasterized onto Cartesian `MULTX` and `MULTY`
faces and extended vertically through all six layers. Every fault uses the same
state in a scenario:

| State | Transmissibility multiplier |
| --- | ---: |
| Open | 1.0 |
| Semi-open | 0.05 |
| Closed | 0.0001 |

These are scenario multipliers, not measured fault transmissibilities.

## Wells and schedule

| Project | OPM cell | Browser reference |
| --- | --- | --- |
| Storage Alpha | I=21, J=14 | Reference injector |
| Storage Beta | I=19, J=11 | South-west project |
| Storage Zeta | I=30, J=5 | Cell 192 |

- Wells are completed in all six layers.
- Maximum bottom-hole pressure: 285 bar.
- Unit-response rate: 1 Mt CO2/year.
- Rate conversion assumes 1.87 kg/Sm3, giving 1,464,091 Sm3/day per Mt/year.
- Simulation begins 1 January 2027. Separate cases inject for 5, 10, 20, 30
  or 40 years, shut in all active injectors, and continue through year 60.
  Published response years are 1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50,
  55 and 60.
- The browser linearly interpolates between published OPM response years.
- Both pressure and SGAS are read from the explicit schedule selected in the
  interface, including the post-injection period. Durations between the five
  simulated schedules are intentionally unavailable rather than interpolated.

## Ensemble and browser calculations

The published dataset contains 405 successful OPM simulations: nine geological
property perturbations, three shared all-fault states, three unit-response
patterns (Alpha, Alpha plus Beta, and Alpha plus Zeta), and five injection
durations. P10, P50 and P90 are calculated across the nine realizations. The
browser scales unit responses for the 1–3 Mt/year controls; this is linear
superposition, not a fresh nonlinear OPM solve for every rate combination.

## Important exclusions

The current model does not contain history matching, calibrated aquifer
support, facies-scale layering, coupled geomechanics, stress-dependent fault
behaviour, induced-seismicity probability, well injectivity calibration or
permit-ready operating limits. The pressure constraint selected in the
interface is a screening threshold, not a calibrated fracture-pressure or
fault-reactivation limit.

See `data/model-manifest.json`, `model/GASSUM_REFERENCE.DATA`, and the source
under `opm/` for complete reproduction details.
