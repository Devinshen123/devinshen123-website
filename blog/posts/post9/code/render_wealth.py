"""Render the four strategies on the exact same holding-window exits."""

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

ROOT = Path(__file__).resolve().parents[1]
STYLES = [
    ("relative_momentum_xgb", "XGBoost + relative momentum", "#006b62", "-", "o"),
    ("original_xgb", "Original XGBoost, corrected test", "#24468a", "--", "s"),
    ("equal_weight_95", "Equal weight, 95 stocks", "#8a4c15", "-.", "D"),
    ("spy", "SPY, same dates", "#656773", ":", "^"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "comparison")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (ROOT / "results" / "comparison" / "portfolio_periods.csv").open(
        encoding="utf-8", newline=""
    ) as f:
        periods = list(csv.DictReader(f))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(8.4, 4.7))
    fig.subplots_adjust(left=.095, right=.915, bottom=.17, top=.73)
    fig.text(.095, .953, "How a dollar grew across 34 holding windows",
             fontsize=18, weight="bold", color="#172537")
    fig.text(.095, .897, "Same buy and sell dates for all strategies  •  Before trading costs",
             fontsize=11, color="#435162")
    for strategy, label, color, linestyle, marker in STYLES:
        series = sorted((r for r in periods if r["model"] == strategy), key=lambda r: r["exit_date"])
        dates = [date.fromisoformat(series[0]["entry_date"])] + [date.fromisoformat(r["exit_date"]) for r in series]
        wealth = [1] + [float(r["wealth"]) for r in series]
        ax.plot(dates, wealth, color=color, linestyle=linestyle, linewidth=2.3, marker=marker,
                markersize=4.6, markevery=[len(dates)-1], label=label)
        offset = {"relative_momentum_xgb": 6, "original_xgb": -6, "equal_weight_95": 7, "spy": -7}[strategy]
        ax.annotate(f"${wealth[-1]:.2f}", (dates[-1], wealth[-1]), xytext=(7, offset),
                    textcoords="offset points", color=color, weight="bold", fontsize=10,
                    va="center", annotation_clip=False)
    ax.set_xlim(date(2024, 1, 1), date(2026, 10, 29) + timedelta(days=25))
    ax.set_ylim(.96, 2.41)
    ax.set_yticks([1, 1.25, 1.5, 1.75, 2, 2.25])
    ax.yaxis.set_major_formatter(StrMethodFormatter("${x:.2f}"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.grid(axis="y", color="#e0e6ec", linewidth=.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#a4aebb")
    ax.tick_params(length=0, pad=8, labelcolor="#334357")
    ax.legend(loc="lower left", bbox_to_anchor=(-.01, 1.01), ncols=2, fontsize=9.6,
              handlelength=2.7, frameon=False, borderaxespad=0, columnspacing=1.4)
    fig.text(.095, .047, "Points show portfolio value at each exit. Cash earns 0% between holding windows.",
             fontsize=9, color="#435162")
    for ext in ("svg", "png"):
        fig.savefig(args.output / f"wealth-path.{ext}", dpi=180, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
