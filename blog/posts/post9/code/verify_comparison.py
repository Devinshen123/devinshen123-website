"""Independently check the repaired run and recompute the reported statistics."""

from collections import defaultdict
import csv
from hashlib import sha256
import json
from math import fsum, isclose, prod, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "comparison"
MODELS = ("original_xgb", "relative_momentum_xgb")
HOLDINGS = {"equal_weight_95": 95, **dict.fromkeys(MODELS, 10)}


def rows(name, base=OUT):
    with (base / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def equal(a, b):
    assert isclose(float(a), float(b), rel_tol=0, abs_tol=2e-12), (a, b)


def keyed(records, *columns):
    keyed_rows = {tuple(row[k] for k in columns): row for row in records}
    assert len(keyed_rows) == len(records)
    return keyed_rows


def main():
    manifest = json.loads((ROOT / "data" / "download_manifest.json").read_text(encoding="utf-8"))
    assert sha256((ROOT / "data" / "daily_prices.csv").read_bytes()).hexdigest() == manifest["csv_sha256"]
    audit = json.loads((OUT / "audit.json").read_text(encoding="utf-8"))
    raw = [r for r in rows("daily_prices.csv", ROOT / "data") if r["date"] <= audit["data_through"]]
    prices = {k: float(v["adjusted"]) for k, v in keyed(raw, "symbol", "date").items()}
    symbols = sorted({s for s, _ in prices} - {"SPY"})
    sessions = sorted(d for s, d in prices if s == "SPY")
    index = {day: i for i, day in enumerate(sessions)}
    target = lambda s, i: prices[s, sessions[i + 20]] / prices[s, sessions[i + 1]] - 1
    training = [(s, i) for i in range(126, len(sessions) - 20)
                if sessions[i + 20] < "2024-01-01" for s in symbols]
    excluded = [(s, sessions[i], sessions[i + 20]) for i in range(126, len(sessions) - 20)
                if sessions[i] < "2024-01-01" <= sessions[i + 20] for s in symbols]
    assert len(training) == audit["training_rows"]
    assert {tuple(r.values()) for r in rows("excluded_training_labels.csv")} == set(excluded)
    mean_forecast = fsum(target(s, i) for s, i in training) / len(training)
    equal(mean_forecast, audit["fixed_training_forecast"])
    windows = rows("common_windows.csv")
    expected_signals = {}
    for i, d in enumerate(sessions[:-20]):
        if d >= "2024-01-01":
            expected_signals.setdefault(d[:7], d)
    assert [r["date"] for r in windows] == list(expected_signals.values())
    assert all(r["entry_date"] >= p["exit_date"] for p, r in zip(windows, windows[1:]))
    for w in windows:
        i = index[w["date"]]
        assert w["entry_date"] == sessions[i + 1] and w["exit_date"] == sessions[i + 20]
        equal(w["spy_return"], target("SPY", i))
    report = {}
    for prefix in ("", "sensitivity_"):
        predictions = keyed(rows(f"{prefix}test_predictions.csv"), "symbol", "date")
        assert len(predictions) == audit["test_rows"] == 66215
        for (s, d), r in predictions.items():
            i = index[d]
            assert d >= "2024-01-01"
            assert r["entry_date"] == sessions[i + 1] and r["exit_date"] == sessions[i + 20]
            equal(r["target"], target(s, i))
            equal(r["historical_mean"], mean_forecast)
            rel = (prices[s, sessions[i - 1]] / prices[s, sessions[i - 22]]
                   - prices["SPY", sessions[i - 1]] / prices["SPY", sessions[i - 22]])
            equal(r["relative_momentum_21"], rel)
        for m in rows(f"{prefix}prediction_metrics.csv"):
            errors = [float(r[m["model"]]) - float(r["target"]) for r in predictions.values()]
            equal(m["rmse"], sqrt(fsum(e * e for e in errors) / len(errors)))
            equal(m["mae"], fsum(abs(e) for e in errors) / len(errors))
        groups = defaultdict(list)
        for weight in rows(f"{prefix}portfolio_weights.csv"):
            groups[weight["model"], weight["date"]].append(weight)
        periods = keyed(rows(f"{prefix}portfolio_periods.csv"), "model", "date")
        totals = defaultdict(list)
        for w in windows:
            d = w["date"]
            i = index[d]
            for model, n in HOLDINGS.items():
                actual = groups[model, d]
                assert len(actual) == len({r["symbol"] for r in actual}) == n
                if model in MODELS:
                    ranked = sorted(symbols, key=lambda s: (-float(predictions[s, d][model]), s))[:n]
                    assert set(ranked) == {r["symbol"] for r in actual}
                    positive = [max(0, float(predictions[s, d][model])) for s in ranked]
                    expected = dict(zip(ranked, (p / fsum(positive) if fsum(positive) else 1/n for p in positive)))
                else:
                    expected = dict.fromkeys(symbols, 1/n)
                assert all(r["entry_date"] == w["entry_date"] and r["exit_date"] == w["exit_date"] for r in actual)
                for r in actual:
                    equal(r["weight"], expected[r["symbol"]])
                equal(fsum(float(r["weight"]) for r in actual), 1)
                totals[model].append(fsum(p * target(s, i) for s, p in expected.items()))
            totals["spy"].append(target("SPY", i))
            for model in totals:
                p = periods[model, d]
                assert p["entry_date"] == w["entry_date"] and p["exit_date"] == w["exit_date"]
                equal(p["gross_return"], totals[model][-1])
                equal(p["wealth"], prod(1 + r for r in totals[model]))
        for p in rows(f"{prefix}portfolio_metrics.csv"):
            equal(p["gross_cumulative_return"], prod(1 + r for r in totals[p["model"]]) - 1)
        report[prefix or "main"] = {
            "daily_predictions_checked": len(predictions),
            "nonoverlapping_windows_checked": len(windows),
            "relative_momentum_windows_ahead_of_original": sum(
                a > b for a, b in zip(totals["relative_momentum_xgb"], totals["original_xgb"])),
        }
    report["purged_training_labels_checked"] = len(excluded)
    (OUT / "independent_checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
