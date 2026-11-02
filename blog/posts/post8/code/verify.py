"""Independently reconcile saved simulation inputs, formulas, and SciPy results."""
from pathlib import Path
import csv
import json
from math import isclose, sqrt
from statistics import mean, stdev

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]


def read_csv(name):
    with (ROOT / "results" / name).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def run():
    summary = json.loads((ROOT / "results/summary.json").read_text(encoding="utf-8"))
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    inputs = np.load(ROOT / "data/simulation_inputs.npz")
    sample = inputs["sample"].tolist()
    n, mu, mu0 = cfg["sample_size"], cfg["population_mean_ml"], cfg["null_mean_ml"]
    estimate, spread = mean(sample), stdev(sample)
    assert isclose(estimate, summary["observed"]["mean_ml"], abs_tol=1e-10)
    assert isclose(spread, summary["observed"]["sd_ml"], abs_tol=1e-10)
    library_test = stats.ttest_1samp(sample, popmean=mu0, alternative="two-sided")
    library_ci = library_test.confidence_interval(confidence_level=1 - cfg["alpha"])
    assert isclose(library_test.statistic, summary["observed"]["t_statistic"], abs_tol=1e-10)
    assert isclose(library_test.pvalue, summary["null"]["analytic_t_p"], abs_tol=1e-12)
    assert isclose(library_ci.low, summary["observed"]["ci95_lower_ml"], abs_tol=1e-10)
    assert isclose(library_ci.high, summary["observed"]["ci95_upper_ml"], abs_tol=1e-10)

    boot_rows = read_csv("bootstrap_means.csv")
    assert len(boot_rows) == cfg["bootstrap_repetitions"]
    for indices, row in zip(inputs["bootstrap_indices"], boot_rows):
        assert len(indices) == n and all(0 <= index < n for index in indices)
        assert isclose(mean(sample[int(index)] for index in indices), float(row["mean_ml"]), abs_tol=1e-10)
    # Every resample must be permitted to repeat observations. This is a check on
    # the saved indices, not a second invocation of the generating function.
    assert all(len(set(indices)) < n for indices in inputs["bootstrap_indices"])
    expected_boot_sd = spread * sqrt((n - 1) / n) / sqrt(n)
    assert abs(summary["bootstrap"]["standard_error_ml"] / expected_boot_sd - 1) < .05

    critical = stats.t.isf(cfg["alpha"] / 2, n - 1)
    coverage_rows = read_csv("coverage_intervals.csv")
    assert len(coverage_rows) == cfg["coverage_repetitions"]
    count = 0
    for raw, row in zip(inputs["coverage_samples"], coverage_rows):
        values = raw.tolist()
        center, halfwidth = mean(values), critical * stdev(values) / sqrt(n)
        lo, hi = center - halfwidth, center + halfwidth
        assert isclose(lo, float(row["lower_ml"]), abs_tol=1e-10)
        assert isclose(hi, float(row["upper_ml"]), abs_tol=1e-10)
        covered = lo <= mu <= hi
        assert covered == bool(int(row["covers_true_mean"]))
        count += covered
    assert count == summary["coverage"]["covered_count"]
    # Under the stated iid normal model the t interval has exact 95% coverage.
    # This wide diagnostic tolerance concerns simulation calibration, not an
    # instruction to change seeds until the display shows a preferred percentage.
    theoretical_mc_se = sqrt(.95 * .05 / len(coverage_rows))
    assert abs(count / len(coverage_rows) - .95) < 5 * theoretical_mc_se

    null_rows = read_csv("null_statistics.csv")
    assert len(null_rows) == cfg["null_repetitions"]
    observed_t = library_test.statistic
    extreme_count, rejection_count = 0, 0
    for raw, row in zip(inputs["null_samples"], null_rows):
        values = raw.tolist()
        t = (mean(values) - mu0) / (stdev(values) / sqrt(n))
        assert isclose(t, float(row["t_statistic"]), abs_tol=1e-10)
        extreme_count += abs(t) >= abs(observed_t)
        rejection_count += abs(t) > critical
    assert extreme_count == summary["null"]["extreme_count"]
    assert rejection_count == summary["null"]["rejection_count"]
    mc_p = (extreme_count + 1) / (len(null_rows) + 1)
    assert isclose(mc_p, summary["null"]["monte_carlo_p"], abs_tol=1e-15)
    assert abs(mc_p - library_test.pvalue) < 5 * sqrt(max(library_test.pvalue * (1 - library_test.pvalue), .0001) / len(null_rows)) + 1 / len(null_rows)
    assert summary["observed"]["reject_null"] == (library_test.pvalue < cfg["alpha"])
    assert summary["observed"]["target_in_ci"] != summary["observed"]["reject_null"]
    assert abs(rejection_count / len(null_rows) - .05) < 5 * theoretical_mc_se
    result = {"passed": True, "bootstrap_rows_recomputed": len(boot_rows),
              "coverage_intervals_recomputed": len(coverage_rows),
              "null_statistics_recomputed": len(null_rows),
              "independent_method": "Python statistics.mean/stdev on saved raw arrays plus scipy.stats.ttest_1samp and its confidence_interval",
              "sample_ci_agrees_with_scipy": True, "monte_carlo_p_agrees_with_analytic_within_simulation_error": True,
              "normal_model_calibration_passed": True,
              "all_samples_and_seed_retained": True}
    (ROOT / "results/validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    run()
