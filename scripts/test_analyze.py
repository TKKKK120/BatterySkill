"""Meaningful numeric and CLI checks, all using synthetic data."""
import csv
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from analyze import absolute_linear_area, cv_calculate, gitt_value, regression


class CoreTests(unittest.TestCase):
    def test_cv_recovers_known_signed_components(self):
        rates = [0.0002, 0.0004, 0.0006, 0.0008, 0.001]
        params = [(0.02, 0.001), (0.03, 0.002), (-0.02, -0.001)]
        currents = [[a * v + b * math.sqrt(v) for v in rates] for a, b in params]
        coefficients, parts, _ = cv_calculate([0, 0.5, 0], currents, rates)
        for row, (a, b) in zip(coefficients, params):
            self.assertAlmostEqual(row["k1_A_s_per_V"], a, places=12)
            self.assertAlmostEqual(row["k2_A_sqrt_s_per_V"], b, places=12)
            self.assertAlmostEqual(row["r2"], 1)
            self.assertTrue(row["accepted"])
            self.assertEqual(row["qc"], "")
        self.assertLess(max(abs(p["residual_A"]) for p in parts), 1e-15)

    def test_constant_transformed_signal_and_zero_intercept(self):
        a, b, r2, _ = regression([1, 2, 3], [5, 5, 5])
        self.assertEqual((a, b, r2), (0, 5, None))
        a, b, r2, _ = regression([1, 2, 3], [2, 4, 6])
        self.assertEqual((a, b, r2), (2, 0, 1))

    def test_absolute_area_handles_zero_crossing(self):
        self.assertAlmostEqual(absolute_linear_area(-1, 1, 2), 1)
        self.assertAlmostEqual(absolute_linear_area(-2, 1, 3), 2.5)

    def test_no_bridge_across_rejected_point(self):
        rates = [1, 4, 9]
        good = [v + math.sqrt(v) for v in rates]
        bad = [math.sqrt(v) for v in rates]
        _, _, summaries = cv_calculate([0, 1, 2], [good, bad, good], rates)
        for row in summaries:
            self.assertEqual(row["retained_path_fraction"], 0)
            self.assertIsNone(row["fraction_retained"])
            self.assertIsNotNone(row["fraction_all"])

    def test_gitt_known_value_and_scaling(self):
        values = (120, 4.2, 4.19, 4.09, 4.18, 0.001902, 80, 20.5, 1)
        _, _, d, logd = gitt_value(*values)
        expected = 4 / (math.pi * 120) * (0.001902 * 20.5 / 80) ** 2 * 0.2 ** 2
        self.assertAlmostEqual(d / expected, 1, places=11)
        self.assertAlmostEqual(math.log10(d), logd)
        doubled = list(values)
        doubled[-1] = 2
        self.assertAlmostEqual(gitt_value(*doubled)[2] / d, 0.25)
        doubled = list(values)
        doubled[0] = 240
        self.assertAlmostEqual(gitt_value(*doubled)[2] / d, 0.5)

    def test_gitt_rejects_undefined_voltage_ratios(self):
        with self.assertRaises(ValueError):
            gitt_value(120, 4.2, 4.1, 4.1, 4.18, 0.001902, 80, 20.5, 1)
        with self.assertRaises(ValueError):
            gitt_value(120, 4.2, 4.19, 4.09, 4.2, 0.001902, 80, 20.5, 1)

    def test_cv_unit_invariance_and_preserved_bad_gitt_row(self):
        script = str(Path(__file__).with_name("analyze.py"))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for unit, factor, rates, rate_unit in (("A", 1, "0.001,0.004,0.009", "V/s"),
                                                    ("mA", 1000, "1,4,9", "mV/s")):
                source = root / (unit + ".csv")
                with source.open("w", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(["E_V", "i1", "i2", "i3"])
                    for e in [0, 0.5, 1]:
                        writer.writerow([e] + [factor * (0.02 * v + 0.001 * math.sqrt(v))
                                                for v in [0.001, 0.004, 0.009]])
                subprocess.run([sys.executable, script, "cv", str(source), "--rates", rates,
                                "--rate-unit", rate_unit, "--current-unit", unit,
                                "--out", str(root / unit)], check=True, capture_output=True)
            def csv_rows(path):
                with path.open(encoding="utf-8-sig") as stream:
                    return list(csv.DictReader(stream))
            a = csv_rows(root / "A" / "cv_coefficients.csv")
            b = csv_rows(root / "mA" / "cv_coefficients.csv")
            for ra, rb in zip(a, b):
                self.assertAlmostEqual(float(ra["k1_A_s_per_V"]), float(rb["k1_A_s_per_V"]), places=12)
            source = root / "endpoints.csv"
            source.write_text("pulse_id,tau_s,E0_V,E1_V,E2_V,E3_V\n"
                              "good,120,4.2,4.19,4.09,4.18\n"
                              "bad,120,4.2,4.1,4.1,4.18\n")
            subprocess.run([sys.executable, script, "gitt", str(source), "--mass-g", "0.001902",
                            "--molar-mass", "80", "--molar-volume", "20.5", "--area-cm2", "1",
                            "--out", str(root / "gitt")], check=True, capture_output=True)
            results = csv_rows(root / "gitt" / "gitt_results.csv")
            self.assertEqual(len(results), 2)
            self.assertGreater(float(results[0]["D_cm2_s"]), 0)
            self.assertEqual(results[1]["D_cm2_s"], "")
            self.assertIn("zero_or_unresolved_delta_E_tau", results[1]["qc"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
