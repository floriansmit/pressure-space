# PressureSpace Gassum model assumptions

This document records the inputs used for the published Gassum OPM Flow
screening ensemble. The model is reproducible, but it is not calibrated for
engineering design, induced-seismicity assessment, operational approval or
permitting.

## Simulator and grid

- OPM Flow 2026.04 in `CO2STORE` mode with CO2 and H2O components.
- Cartesian grid: 60 × 50 × 6, or 18,000 cells.
- Horizontal cell dimensions: 2,000 × 2,000 m.
- Flat reservoir top: 1,800 m.
- Total thickness values: 45, 72 and 110 m; each realization divides its total
  thickness equally over six layers.
- The geological surfaces and cell properties visible in the map are regional
  context and are not yet transferred into the OPM grid.

## Boundary and initial conditions

- Four operations multiply the pore volume of the west, east, south and north
  edge-cell sets by 1,000,000. Corner cells occur in two edge sets and receive
  the multiplier twice. This is a large-volume pressure-sink approximation,
  not an explicit aquifer or a calibrated fixed-pressure boundary.
- The model top and base are no-flow boundaries.
- Initial pressure: 180 bar at the 1,800 m datum.
- Constant reservoir temperature: 65 °C.
- Exact initialization keyword: `EQUIL 1800 180 1600 0 1600 0 /`.

## Rock and fluid inputs

- Horizontal permeability: 100, 250 or 600 mD.
- Vertical permeability: 10% of horizontal permeability.
- Porosity: 0.18, 0.22 or 0.26.
- Total thickness: 45, 72 or 110 m.
- Rock compressibility: 5×10^-5 bar^-1 at a 200 bar reference pressure.
- Each realization is homogeneous. The nine combinations are listed in
  `data/model-manifest.json`.
- Relative-permeability and capillary-pressure tables are included verbatim in
  the downloadable reference deck.

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
| Storage Alpha | I=30, J=25 | Reference injector |
| Storage Beta | I=28, J=20 | Opposite side of central fault set |
| Storage Zeta | I=43, J=9 | Cell 192 |

- Wells are completed in all six layers.
- Maximum bottom-hole pressure: 285 bar.
- Unit-response rate: 1 Mt CO2/year.
- Rate conversion assumes 1.87 kg/Sm3, giving 1,464,091 Sm3/day for 1 Mt/year.
- Simulation begins 1 January 2027 and injects for 20 years with annual report
  steps. Published response years are 1, 5, 10 and 20.

The OPM schedule ends at year 20. When the browser is moved to years 21–60 it
holds the final year-20 response constant; those later states are not simulated
post-injection pressure dissipation.

## Ensemble and browser calculations

The published dataset contains 81 successful OPM simulations:

- 9 L9 property realizations;
- 3 shared all-fault states; and
- 3 unit-response patterns: Alpha, Alpha plus Beta, and Alpha plus Zeta.

P10, P50 and P90 are calculated across the nine property realizations. The
browser scales Alpha by its selected rate and adds the incremental Beta and Zeta
unit responses. Consequently, the 1–3 Mt/year multi-project controls are a
linear superposition screening method, not new fully coupled nonlinear runs.

## Important exclusions

The current model does not contain history matching, calibrated aquifer
support, spatial facies in the simulator grid, coupled geomechanics, thermal
coupling, stress-dependent fault behaviour, induced-seismicity probability,
well injectivity calibration or permit-ready operating limits. The pressure
constraint selected in the interface is a screening threshold, not a calibrated
fracture-pressure or fault-reactivation limit.

See the machine-readable `data/model-manifest.json`, the generated
`model/GASSUM_REFERENCE.DATA`, and the source under `opm/` for complete
reproduction details.
