"""Standard-library checks for LHS reproducibility and design quality."""
import sys
import unittest
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lhs_experiment import DEFAULT_CONFIG, lhs, validate


class SamplingTests(unittest.TestCase):
    def test_reproducible(self):
        self.assertEqual(lhs(DEFAULT_CONFIG), lhs(DEFAULT_CONFIG))

    def test_continuous_stratification_and_bounds(self):
        config = DEFAULT_CONFIG
        n = config["sample_count"]
        samples = lhs(config)
        self.assertEqual(len(samples), n)
        for name, p in config["parameters"].items():
            low, high = p["min"], p["max"]
            bins = []
            for s in samples:
                value = s[name]
                self.assertGreaterEqual(value, low)
                self.assertLessEqual(value, high)
                u = ((__import__("math").log(value / low) / __import__("math").log(high / low))
                     if p["scale"] == "log" else (value - low) / (high - low))
                bins.append(min(n - 1, int(u * n)))
            self.assertEqual(set(bins), set(range(n)), name)

    def test_discrete_faults_balanced(self):
        c = Counter(item["fault_state"] for item in lhs(DEFAULT_CONFIG))
        self.assertLessEqual(max(c.values()) - min(c.values()), 1)

    def test_bad_configuration(self):
        import copy
        c = copy.deepcopy(DEFAULT_CONFIG)
        c["parameters"]["permeability_multiplier"]["min"] = -1
        with self.assertRaises(ValueError):
            validate(c)


if __name__ == "__main__":
    unittest.main()
