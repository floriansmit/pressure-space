"""Reproducible Latin-hypercube deck preparation and local OPM Flow batch runner.

No simulator is invoked by the 'prepare' command. Results remain local and
are NOT automatically published to dist/data or committed to GitHub.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import subprocess
from pathlib import Path

from build_deck import build_deck

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE / "lhs-runs"

# Screening ranges only. Review against Gassum measurements before interpretation.
# Fault state is sampled as a discrete uncertainty dimension.
DEFAULT_CONFIG = {
    "seed": 20261109,
    "sample_count": 60,
    "years": 60,
    "injection_years": 20,
    "rate_mt_yr": 1.0,
    "fault_states": ["open", "semi-open", "closed"],
    "parameters": {
        "permeability_multiplier": {"min": 0.4966, "max": 2.0138, "scale": "log"},
        "porosity_multiplier": {"min": 0.9, "max": 1.1, "scale": "linear"},
        "thickness_sigma": {"min": -1.0, "max": 1.0, "scale": "linear"},
        "vertical_to_horizontal_perm_ratio": {"min": 0.01, "max": 0.3, "scale": "log"},
        "rock_compressibility_per_bar": {"min": 2e-5, "max": 8e-5, "scale": "log"},
        "boundary_pore_volume_multiplier": {"min": 1.0, "max": 1e6, "scale": "log"},
    },
}


def validate(config):
    n = config["sample_count"]
    if not isinstance(n, int) or isinstance(n, bool) or not 2 <= n <= 10000:
        raise ValueError("sample_count must be an integer in [2, 10000]")
    if not isinstance(config["seed"], int):
        raise ValueError("seed must be an integer")
    if not 1 <= config["injection_years"] <= config["years"]:
        raise ValueError("Require 1 <= injection_years <= years")
    if config["rate_mt_yr"] <= 0:
        raise ValueError("rate_mt_yr must be positive")
    states = config["fault_states"]
    if not states or len(set(states)) != len(states) or not set(states) <= {"open", "semi-open", "closed"}:
        raise ValueError("fault_states must be unique known states")
    expected = set(DEFAULT_CONFIG["parameters"])
    if set(config["parameters"]) != expected:
        raise ValueError("Unsupported parameter names; expected " + ", ".join(sorted(expected)))
    for name, spec in config["parameters"].items():
        a, b = spec["min"], spec["max"]
        if not all(isinstance(x, (float, int)) and math.isfinite(x) for x in (a, b)) or not a < b:
            raise ValueError(f"{name} requires finite min < max")
        if spec["scale"] not in ("linear", "log"):
            raise ValueError(f"{name}: scale must be linear or log")
        if spec["scale"] == "log" and a <= 0:
            raise ValueError(f"{name}: log minimum must be positive")
    if config["parameters"]["vertical_to_horizontal_perm_ratio"]["max"] > 1:
        raise ValueError("Kv/Kh cannot exceed 1 for this screening configuration")
    if config["parameters"]["rock_compressibility_per_bar"]["max"] >= .01:
        raise ValueError("Rock compressibility outside supported range")
    if config["parameters"]["boundary_pore_volume_multiplier"]["min"] < 1:
        raise ValueError("Boundary pore volume multiplier must be >= 1")


def lhs(config):
    """Independent randomized permutations give one sample per marginal stratum."""
    validate(config)
    rng = random.Random(config["seed"])
    n = config["sample_count"]
    params = {}
    for name, spec in config["parameters"].items():
        slots = list(range(n))
        rng.shuffle(slots)
        values = []
        for slot in slots:
            u = (slot + rng.random()) / n
            if spec["scale"] == "log":
                value = math.exp(math.log(spec["min"]) + u * (math.log(spec["max"]) - math.log(spec["min"])))
            else:
                value = spec["min"] + u * (spec["max"] - spec["min"])
            values.append(value)
        params[name] = values
    # Stratified categorical draw with near-balanced case counts.
    states = config["fault_states"]
    labels = [states[min(len(states) - 1, int((slot + .5) * len(states) / n))] for slot in range(n)]
    rng.shuffle(labels)
    return [{"run_id": f"LHS_{i + 1:04d}", "fault_state": labels[i],
             **{name: vals[i] for name, vals in params.items()}} for i in range(n)]


def prepare(config, root):
    """Write independent decks and manifest without executing OPM."""
    validate(config)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Output directory not empty: {root}. Use a new directory.")
    root.mkdir(parents=True, exist_ok=True)
    cases = lhs(config)
    for case in cases:
        run_id = case["run_id"]
        folder = root / run_id
        folder.mkdir()
        deck = build_deck(
            run_id, config["rate_mt_yr"], config["years"],
            permeability_multiplier=case["permeability_multiplier"],
            porosity_multiplier=case["porosity_multiplier"],
            thickness_sigma=case["thickness_sigma"],
            fault_state=case["fault_state"],
            injection_years=config["injection_years"],
            vertical_to_horizontal_perm_ratio=case["vertical_to_horizontal_perm_ratio"],
            rock_compressibility_per_bar=case["rock_compressibility_per_bar"],
            boundary_pore_volume_multiplier=case["boundary_pore_volume_multiplier"],
        )
        (folder / f"{run_id}.DATA").write_text(deck, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "design": "randomized Latin hypercube for continuous parameters; balanced discrete fault state",
        "description": "Screening distributions; not calibrated. No rel-perm, capillary or salinity variation yet.",
        "configuration": config,
        "cases": cases,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with (root / "samples.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(cases[0]))
        writer.writeheader()
        writer.writerows(cases)
    print(f"Prepared {len(cases)} independent OPM decks at {root}")
    return manifest


def run_batch(root, flow, max_cases=None, retry_failed=False):
    """Serial, resumable execution. A failed case remains available to diagnose."""
    if not shutil.which(flow) and not Path(flow).is_file():
        raise FileNotFoundError(f"Cannot find OPM Flow executable: {flow}")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]
    completed = 0
    failed = 0
    for case in cases:
        if max_cases is not None and completed + failed >= max_cases:
            break
        name = case["run_id"]
        folder = root / name
        output = folder / "output"
        output.mkdir(exist_ok=True)
        success_file = folder / "success.json"
        failed_file = folder / "failure.json"
        if success_file.exists():
            continue
        if failed_file.exists() and not retry_failed:
            continue
        deck = folder / f"{name}.DATA"
        digest = hashlib.sha256(deck.read_bytes()).hexdigest()
        with (folder / "flow.log").open("w", encoding="utf-8") as log:
            result = subprocess.run([flow, str(deck.resolve()), f"--output-dir={output.resolve()}"],
                                    stdout=log, stderr=subprocess.STDOUT, check=False)
        marker = {"returncode": result.returncode, "deck_sha256": digest}
        if result.returncode == 0 and (output / f"{name}.UNRST").exists():
            success_file.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
            failed_file.unlink(missing_ok=True)
            completed += 1
        else:
            failed_file.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
            failed += 1
        print(f"{name}: {'OK' if result.returncode == 0 and success_file.exists() else 'FAILED'}")
    print(f"This invocation: {completed} succeeded, {failed} failed")
    if failed:
        raise SystemExit(1)


def status(root):
    cases = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["cases"]
    counts = {"completed": 0, "failed": 0, "pending": 0}
    for case in cases:
        folder = root / case["run_id"]
        state = "completed" if (folder / "success.json").exists() else (
            "failed" if (folder / "failure.json").exists() else "pending")
        counts[state] += 1
    print(json.dumps({"total": len(cases), **counts}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="Make LHS CSV, manifest, and OPM decks (no simulation)")
    p.add_argument("--config", type=Path, help="Optional JSON configuration")
    p.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    r = sub.add_parser("run", help="Run prepared decks using local OPM Flow")
    r.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    r.add_argument("--flow", default="flow")
    r.add_argument("--max-cases", type=int)
    r.add_argument("--retry-failed", action="store_true")
    st = sub.add_parser("status")
    st.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    if args.command == "prepare":
        config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else DEFAULT_CONFIG
        prepare(config, args.root)
    elif args.command == "run":
        if args.max_cases is not None and args.max_cases < 1:
            parser.error("--max-cases must be positive")
        run_batch(args.root, args.flow, args.max_cases, args.retry_failed)
    else:
        status(args.root)


if __name__ == "__main__":
    main()
