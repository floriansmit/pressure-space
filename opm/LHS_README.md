# Latin Hypercube Sampling (LHS) for PressureSpace

This is an **opt-in experimental workflow** for the Gassum CO2STORE model.
It does not modify the deployed browser data, replace the existing L9 or
fault-state ensembles, or claim that any additional OPM simulations have run.

## 1. Prepare reproducible input decks (no OPM needed)

From the repository root, in an environment with Python 3.10+:

```bash
python opm/lhs_experiment.py prepare
python opm/lhs_experiment.py status
```

The default is a 60-case design with seed `20261109`, one injection project
at 1 Mt CO2/year, 20 years of injection and a 60-year simulation.
Decks and `samples.csv` and `manifest.json` are written to
`opm/lhs-runs/`. The design is reproducible at the same Python version and
random seed. Each continuous parameter receives one draw in every LHS
marginal stratum; discrete fault states are distributed approximately evenly.

The six *sampled continuous* parameters are permeability multiplier,
porosity multiplier, mapped thickness offset (in mapped SD units), Kv/Kh,
rock compressibility and lateral-edge pore-volume multiplier. Each run
also samples one categorical all-fault state (open/semi-open/closed).

The default distributions are **illustrative screening ranges**, not
measured Gassum uncertainty distributions. In particular, changing the
edge pore-volume multiplier changes the conceptual aquifer-support treatment;
it should not be interpreted as a calibrated boundary condition.
No parameter correlations are represented.

To customize the design, create a JSON configuration using the
`DEFAULT_CONFIG` structure in `opm/lhs_experiment.py` and run:

```bash
python opm/lhs_experiment.py prepare --config my-lhs-config.json --root opm/lhs-project-01
```

Use an **empty/new output directory** for every design. Sampling never
overwrites an existing experiment.

## 2. Run a small smoke test on the GEUS workstation (Ubuntu/WSL2)

From the same repository root within the Ubuntu distribution with OPM Flow:

```bash
command -v flow
python opm/lhs_experiment.py run --max-cases 1
python opm/lhs_experiment.py status
```

Inspect `opm/lhs-runs/LHS_0001/flow.log` and confirm that the run produced
`output/LHS_0001.UNRST`. **Only after the smoke test succeeds**, start
the remaining cases:

```bash
python opm/lhs_experiment.py run
```

The runner executes **serially** to limit workstation memory pressure and
skips cases with `success.json`. It writes `failure.json` for a failed
case, with the simulator exit status and SHA-256 deck hash. Inspect the log,
then explicitly retry failed cases:

```bash
python opm/lhs_experiment.py run --retry-failed
```

You can give an alternate flow executable with `--flow /path/to/flow`.

If you change a prepared deck, use a fresh experiment directory rather
than resuming old outputs. The runner does not yet enforce input-hash
verification before skipping successful cases.

## 3. What is *not* included yet

- **Relative permeability / capillary pressure**: the current OPM deck
  contains fixed `WSF` and `GSF` tables. A robust uncertainty model requires
  physically consistent, validated curve families rather than arbitrarily
  multiplying tabulated saturations.
- **Salinity**: the current deck has no calibrated brine-composition sensitivity.
  Adding salinity requires selecting and validating the correct OPM CO2STORE
  fluid-property inputs and units.
- **Output aggregation and PressureSpace visualization**: produced `UNRST`
  results stay local. They are not imported into the published `dist/data`
  and are not added to the live P10/P50/P90 interface.
- **Execution on GEUS3573w10ws**: no remote connection or runner has been set
  up. Simulations must be started on an authorized OPM-enabled environment.

## Next steps

1. Verify a single local deck through OPM Flow (syntax, runtime and mass balance).
2. Review distribution ranges and correlations with a reservoir engineer.
3. Add validated fluid and multiphase sensitivity models.
4. Add ensemble postprocessing using `opm.io.ecl`: pressure and saturation
   differences from each run's own initial state, mass-balance/convergence
   checks, and cell-wise output quantiles.
5. Compare LHS convergence and sensitivity rankings before using outputs for
   pressure interference interpretation.

The existing published L9 and multi-site OPM workflows are unchanged.
