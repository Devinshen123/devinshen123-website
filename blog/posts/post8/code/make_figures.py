"""Static publication figures from the saved, audited simulation outputs."""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BLUE, RED, GREY, INK = "#216B6B", "#B95135", "#A8B1BA", "#253746"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "text.color": INK, "axes.labelcolor": INK,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.axisbelow": True, "svg.fonttype": "path",
                     "svg.hashsalt": "post8-bottles"})


def summary():
    return json.loads((ROOT / "results/summary.json").read_text(encoding="utf-8"))


def header(fig, title, subtitle, footer):
    fig.text(.03, .95, title, fontsize=16, weight="bold")
    fig.text(.03, .89, subtitle, fontsize=10.5)
    fig.text(.03, .025, footer, fontsize=8.5, color="#52616D")


def bootstrap_figure(s=None):
    s = summary() if s is None else s
    means = np.genfromtxt(ROOT / "results/bootstrap_means.csv", delimiter=",", names=True)["mean_ml"]
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    fig.subplots_adjust(left=.13, right=.97, bottom=.18, top=.81)
    counts, _, _ = ax.hist(means, bins=40, color=BLUE, alpha=.86, edgecolor="white", linewidth=.3)
    ax.axvline(s["observed"]["mean_ml"], color=INK, linewidth=1.9,
               label=f'Sample mean: {s["observed"]["mean_ml"]:.2f} mL')
    ax.axvline(s["config"]["population_mean_ml"], color=BLUE, linestyle=":", linewidth=2,
               label="Known true mean: 498 mL")
    ax.axvline(s["config"]["null_mean_ml"], color=RED, linestyle="--", linewidth=1.8,
               label="Label: 500 mL")
    ax.set_ylim(0, max(counts) * 1.55)
    ax.legend(loc="upper right", frameon=True, facecolor="white",
              edgecolor="white", framealpha=.98, fontsize=9.5)
    ax.grid(axis="y", color="#E8ECEF", linewidth=.7)
    ax.set_xlabel("Mean fill in a bootstrap resample (mL)")
    ax.set_ylabel("Number of resamples")
    header(fig, "One sample, 5,000 resampled means",
           f'50 simulated bottles; bootstrap standard error = {s["bootstrap"]["standard_error_ml"]:.2f} mL',
           "Simulated data. Resample the same 50 observations with replacement; 50 draws each time.")
    return fig


def coverage_figure(s=None):
    s = summary() if s is None else s
    rows = np.genfromtxt(ROOT / "results/coverage_intervals.csv", delimiter=",", names=True)[:100]
    fig, ax = plt.subplots(figsize=(7.4, 5.3))
    fig.subplots_adjust(left=.12, right=.97, bottom=.23, top=.81)
    for row in rows:
        covered = bool(row["covers_true_mean"])
        color = BLUE if covered else RED
        y = int(row["replication"])
        ax.plot([row["lower_ml"], row["upper_ml"]], [y, y], color=color, linewidth=.9)
        if not covered:
            ax.plot(row["mean_ml"], y, marker="x", color=RED, markersize=4)
    ax.axvline(s["config"]["population_mean_ml"], color=INK, linestyle="--", linewidth=1.4)
    ax.set_yticks([1, 25, 50, 75, 100])
    ax.set_ylim(102, -1)
    ax.set_xlabel("95% t confidence interval for mean fill (mL)")
    ax.set_ylabel("Independent sample")
    ax.grid(axis="x", color="#E8ECEF", linewidth=.7)
    fig.legend(handles=[Line2D([0], [0], color=BLUE, label="Contains true mean"),
                        Line2D([0], [0], color=RED, marker="x", label="Misses true mean"),
                        Line2D([0], [0], color=INK, linestyle="--", label="True mean: 498 mL")],
               loc="lower center", bbox_to_anchor=(.52, .09), ncol=3, frameon=False, fontsize=9)
    header(fig, "How often does the interval contain the truth?",
           f'{s["coverage"]["covered_count"]:,} of 5,000 intervals cover 498 mL ({100*s["coverage"]["rate"]:.1f}%)',
           "Simulated data. First 100 samples shown in generation order; the percentage uses all 5,000.")
    return fig


def null_figure(s=None):
    s = summary() if s is None else s
    values = np.genfromtxt(ROOT / "results/null_statistics.csv", delimiter=",", names=True)["t_statistic"]
    observed, critical = s["observed"]["t_statistic"], s["null"]["critical_t"]
    extent = max(4, int(np.ceil(max(abs(values).max(), abs(observed), critical + 1))))
    edges = np.linspace(-extent, extent, 65)
    fig, axes = plt.subplots(2, 1, figsize=(7.4, 6.1), sharex=True)
    fig.subplots_adjust(left=.12, right=.97, top=.80, bottom=.15, hspace=.55)
    for ax in axes:
        counts, _, _ = ax.hist(values, bins=edges, color=GREY, edgecolor="white", linewidth=.25)
        ax.set_ylim(0, max(counts) * 1.15)
        ax.set_xlim(-extent, extent)
        ax.grid(axis="y", color="#E8ECEF", linewidth=.7)
        ax.axvline(observed, color=INK, linewidth=1.8)
    for ax, threshold, color in [(axes[0], critical, RED), (axes[1], abs(observed), BLUE)]:
        ax.axvspan(-extent, -threshold, color=color, alpha=.23, zorder=0)
        ax.axvspan(threshold, extent, color=color, alpha=.23, zorder=0)
        ax.axvline(-threshold, color=color, linestyle="--", linewidth=1.2)
        ax.axvline(threshold, color=color, linestyle="--", linewidth=1.2)
    axes[0].set_title(f'A. Fixed 5% rejection rule: outside ±{critical:.2f}', loc="left", fontsize=11, pad=8)
    axes[1].set_title(f'B. Tails at least as extreme as observed: simulated p = {s["null"]["monte_carlo_p"]:.3f}',
                      loc="left", fontsize=11, pad=8)
    axes[1].set_xlabel("t statistic: distance from 500 mL, measured in standard errors")
    fig.supylabel("Number of simulated samples", x=.015, fontsize=11)
    header(fig, "What would happen if the label were correct?",
           f'5,000 independent samples with true mean 500 mL; observed t = {observed:.2f} (solid line)',
           "Simulated data. n = 50; normal fills. Shading shows rejection regions (A) and p-value tails (B).")
    return fig


def run():
    s = summary()
    for name, maker in [("bootstrap-distribution", bootstrap_figure),
                        ("confidence-coverage", coverage_figure),
                        ("null-distribution", null_figure)]:
        fig = maker(s)
        fig.savefig(ROOT / "results" / (name + ".svg"), facecolor="white", metadata={"Date": None})
        fig.savefig(ROOT / "results" / (name + ".png"), facecolor="white", dpi=180)
        plt.close(fig)
    print("Saved three figures as SVG and PNG.")


if __name__ == "__main__":
    run()
