"""Generate the pre-specified simulation and every number used in Post 8."""
from pathlib import Path
import csv
import hashlib
import importlib.metadata
import json

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, names, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(names)
        writer.writerows(rows)


def run():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    data, results = ROOT / "data", ROOT / "results"
    data.mkdir(exist_ok=True)
    results.mkdir(exist_ok=True)
    n, mu, sd = cfg["sample_size"], cfg["population_mean_ml"], cfg["population_sd_ml"]
    mu0, alpha = cfg["null_mean_ml"], cfg["alpha"]
    streams = [np.random.default_rng(child) for child in np.random.SeedSequence(cfg["root_seed"]).spawn(4)]
    # Independent streams mean a change to plotting or bootstrap effort cannot select
    # a different original sample, coverage experiment, or null experiment.
    sample = streams[0].normal(mu, sd, n)
    indices = streams[1].integers(0, n, size=(cfg["bootstrap_repetitions"], n), dtype=np.int16)
    coverage_samples = streams[2].normal(mu, sd, (cfg["coverage_repetitions"], n))
    null_samples = streams[3].normal(mu0, sd, (cfg["null_repetitions"], n))
    np.savez_compressed(data / "simulation_inputs.npz", sample=sample,
                        bootstrap_indices=indices, coverage_samples=coverage_samples,
                        null_samples=null_samples)
    write_csv(data / "original_sample.csv", ["bottle", "fill_ml"], enumerate(sample.tolist(), 1))

    sample_mean, sample_sd = float(sample.mean()), float(sample.std(ddof=1))
    se = sample_sd / np.sqrt(n)
    critical = float(stats.t.ppf(1 - alpha / 2, n - 1))
    ci_low, ci_high = sample_mean - critical * se, sample_mean + critical * se
    bootstrap_means = sample[indices].mean(axis=1)
    write_csv(results / "bootstrap_means.csv", ["resample", "mean_ml"],
              enumerate(bootstrap_means.tolist(), 1))

    coverage_means = coverage_samples.mean(axis=1)
    coverage_sds = coverage_samples.std(axis=1, ddof=1)
    halfwidth = critical * coverage_sds / np.sqrt(n)
    lows, highs = coverage_means - halfwidth, coverage_means + halfwidth
    covered = (lows <= mu) & (mu <= highs)
    write_csv(results / "coverage_intervals.csv",
              ["replication", "mean_ml", "sample_sd_ml", "lower_ml", "upper_ml", "covers_true_mean"],
              zip(range(1, len(covered) + 1), coverage_means, coverage_sds, lows, highs, covered.astype(int)))

    observed_t = float((sample_mean - mu0) / se)
    null_means = null_samples.mean(axis=1)
    null_sds = null_samples.std(axis=1, ddof=1)
    null_t = (null_means - mu0) / (null_sds / np.sqrt(n))
    extreme = np.abs(null_t) >= abs(observed_t)
    rejected = np.abs(null_t) > critical
    write_csv(results / "null_statistics.csv",
              ["replication", "mean_ml", "sample_sd_ml", "t_statistic", "as_extreme_as_observed", "reject_at_5pct"],
              zip(range(1, len(null_t) + 1), null_means, null_sds, null_t, extreme.astype(int), rejected.astype(int)))

    extreme_count, m = int(extreme.sum()), len(null_t)
    # Add-one Monte Carlo p-value; the exact same rule is documented in the article.
    mc_p = (extreme_count + 1) / (m + 1)
    exact_p = float(2 * stats.t.sf(abs(observed_t), n - 1))
    coverage_rate = float(covered.mean())
    summary = {
        "config": cfg,
        "observed": {"n": n, "mean_ml": sample_mean, "sd_ml": sample_sd,
                     "standard_error_ml": float(se), "ci95_lower_ml": float(ci_low),
                     "ci95_upper_ml": float(ci_high), "t_statistic": observed_t,
                     "target_in_ci": bool(ci_low <= mu0 <= ci_high),
                     "reject_null": bool(abs(observed_t) > critical)},
        "bootstrap": {"repetitions": len(bootstrap_means),
                      "mean_of_means_ml": float(bootstrap_means.mean()),
                      "standard_error_ml": float(bootstrap_means.std(ddof=1)),
                      "conditional_expected_sd_ml": float(sample.std(ddof=0) / np.sqrt(n)),
                      "minimum_unique_bottles_per_resample": int(min(len(set(row)) for row in indices))},
        "coverage": {"repetitions": len(covered), "covered_count": int(covered.sum()),
                     "missed_count": int((~covered).sum()), "rate": coverage_rate,
                     "mc_standard_error": float(np.sqrt(coverage_rate * (1 - coverage_rate) / len(covered))),
                     "first_100_covered_count": int(covered[:cfg["coverage_intervals_displayed"]].sum()),
                     "method": "Student t, not a bootstrap interval"},
        "null": {"repetitions": m, "critical_t": critical, "extreme_count": extreme_count,
                 "monte_carlo_p": mc_p, "analytic_t_p": exact_p,
                 "mc_p_standard_error": float(np.sqrt(mc_p * (1 - mc_p) / m)),
                 "rejection_count": int(rejected.sum()), "rejection_rate": float(rejected.mean()),
                 "empirical_quantiles_025_975": np.quantile(null_t, [.025, .975]).tolist()},
        "sources": [
            {"title": "NIST: Confidence Limits for the Mean", "url": "https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm"},
            {"title": "SciPy: bootstrap", "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html"},
            {"title": "SciPy: ttest_1samp", "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_1samp.html"}],
        "versions": {p: importlib.metadata.version(p) for p in ["numpy", "scipy", "matplotlib", "pandas"]},
        "original_sample_sha256": hashlib.sha256((data / "original_sample.csv").read_bytes()).hexdigest(),
        "limitations": ["Entirely simulated, not evidence about a real brand or legal compliance.",
                        "Independent normal fills and a stable process are assumptions, not verified industrial facts.",
                        "Coverage is for Student t intervals; the bootstrap distribution is a separate illustration.",
                        "A failure to reject does not prove the population mean equals the label.",
                        "Monte Carlo estimates have finite-simulation error; no seed was chosen for a desired result."]}
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mean_ml": sample_mean, "ci95": [ci_low, ci_high],
                      "coverage": coverage_rate, "simulated_p": mc_p, "analytic_p": exact_p}))
    return summary


if __name__ == "__main__":
    run()
