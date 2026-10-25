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
exporter `opm/export_geological_grid.py` derives it from the EarthVision
architecture and the 500 m `gassum__pythermogis_input.nc` property model.

## Rock and fluid inputs

- Spatial porosity: approximately 0.106–0.208 in active cells.
- Spatial horizontal permeability: approximately 8.4–396 mD in active cells.
- Spatial net-to-gross: approximately 0.365–0.561.
- Vertical permeability: 10% of local horizontal permeability.
- Rock compressibility: 5×10^-5 bar^-1 at a 200 bar reference pressure.
- Initial pressure: 180 bar at the 1,800 m datum, initialized hydrostatically.
- OPM uses the regional median mapped temperature, approximately 50.9 °C. The
  full lateral temperature field remains visible data but is not a lateral
  thermal-flow simulation.
- Relative-permeability and capillary-pressure tables are included verbatim in
  the downloadable reference deck.

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
- Simulation begins 1 January 2027 and injects for 20 years with annual report
  steps. Published response years are 1, 5, 10 and 20.

The schedule ends at year 20. Browser years 21–60 hold the final year-20
response and are not separately simulated post-injection states.

## Ensemble and browser calculations

The published dataset contains 81 successful OPM simulations: nine geological
property perturbations, three shared all-fault states, and three unit-response
patterns (Alpha, Alpha plus Beta, and Alpha plus Zeta). P10, P50 and P90 are
calculated across the nine realizations. The browser scales unit responses for
the 1–3 Mt/year controls; this is linear superposition, not a fresh nonlinear
OPM solve for every slider position.

## Important exclusions

The current model does not contain history matching, calibrated aquifer
support, facies-scale layering, coupled geomechanics, stress-dependent fault
behaviour, induced-seismicity probability, well injectivity calibration or
permit-ready operating limits. The pressure constraint selected in the
interface is a screening threshold, not a calibrated fracture-pressure or
fault-reactivation limit.

See `data/model-manifest.json`, `model/GASSUM_REFERENCE.DATA`, and the source
under `opm/` for complete reproduction details.
