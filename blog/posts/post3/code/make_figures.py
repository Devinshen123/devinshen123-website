"""Generate the three standalone article figures from audited aggregate CSVs."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
TEAL, PALE, GREY, INK = "#216B6B", "#82ABAB", "#9099A3", "#26323D"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13,
                     "axes.labelcolor": INK, "text.color": INK,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "svg.fonttype": "path", "axes.axisbelow": True})


def read(name):
    with (OUT / name).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def save(fig, name, source):
    fig.text(.02, .025, source, fontsize=9, color="#56616B", va="bottom")
    fig.savefig(OUT / (name + ".svg"), facecolor="white")
    fig.savefig(OUT / (name + ".png"), dpi=180, facecolor="white")
    plt.close(fig)


def main():
    annual = {row["category"]: row for row in read("annual_summary.csv")}
    names = ["No telework", "Some hours teleworked", "All hours teleworked"]
    values = [float(annual[name]["share_of_people_at_work_pct"]) for name in names]
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    fig.subplots_adjust(left=.32, right=.95, top=.78, bottom=.23)
    ax.barh(range(3), values, color=[GREY, TEAL, PALE], height=.6)
    ax.set_yticks(range(3), ["No telework", "Some hours\nat home", "All hours\nat home"])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.xaxis.set_major_formatter(PercentFormatter())
    ax.tick_params(axis="y", length=0, pad=10)
    ax.grid(axis="x", color="#E6EAED", linewidth=.8)
    ax.set_xlabel("Share of people at work")
    for y, value in enumerate(values):
        ax.text(value + 1.8, y, f"{value:.1f}%", va="center", fontsize=14, weight="bold")
    fig.text(.02, .94, "Work at home during the survey week", fontsize=17, weight="bold")
    fig.text(.02, .86, "United States, 2024 annual averages; ages 16+", fontsize=11)
    save(fig, "telework-status", "Source: IPUMS CPS; WTFINL weights. Unclassified hours: less than 0.001%.")

    bands = [">0%-<25%", "25%-<50%", "50%-<75%", "75%-<100%", "100%"]
    frac = {row["share_of_actual_hours_remote"]: row for row in read("remote_fraction_distribution.csv")}
    values = [float(frac[band]["share_of_classifiable_teleworkers_pct"]) for band in bands]
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    fig.subplots_adjust(left=.14, right=.97, top=.78, bottom=.27)
    ax.bar(range(5), values, width=.84, color=[TEAL] * 4 + [PALE])
    ax.set_xticks(range(5), ["Under\n25%", "25% to\nunder 50%", "50% to\nunder 75%", "75% to\nunder 100%", "All\nhours"])
    ax.set_ylim(0, 60)
    ax.set_yticks([0, 20, 40, 60])
    ax.yaxis.set_major_formatter(PercentFormatter())
    ax.grid(axis="y", color="#E6EAED", linewidth=.8)
    ax.set_ylabel("Share of teleworkers")
    ax.set_xlabel("Share of actual working hours spent at home", labelpad=12)
    for x, value in enumerate(values):
        ax.text(x, value + 1.1, f"{value:.1f}%", ha="center", fontsize=13, weight="bold")
    fig.text(.02, .94, "How much of the working week was at home?", fontsize=17, weight="bold")
    fig.text(.02, .86, "People who teleworked; United States, 2024 annual averages", fontsize=11)
    save(fig, "telework-intensity", "Source: IPUMS CPS; WTFINL weights. Two responses with incomplete hours excluded.")

    monthly = read("monthly_summary.csv")
    share = []
    for month in range(1, 13):
        part = next(float(row["weighted_people"]) for row in monthly
                    if int(row["month"]) == month and row["category"] == "Some hours teleworked")
        full = next(float(row["weighted_people"]) for row in monthly
                    if int(row["month"]) == month and row["category"] == "All hours teleworked")
        share.append(100 * part / (part + full))
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    fig.subplots_adjust(left=.12, right=.96, top=.75, bottom=.21)
    ax.plot(range(1, 13), share, color=TEAL, linewidth=2.5, marker="o", markersize=5)
    ax.axhline(50, color="#66717A", linestyle="--", linewidth=1.1)
    ax.text(1.05, 47.7, "Equal split (50%)", color="#66717A", fontsize=11)
    ax.set_xlim(.8, 12.3)
    ax.set_ylim(40, 60)
    ax.set_yticks([40, 45, 50, 55, 60])
    ax.yaxis.set_major_formatter(PercentFormatter())
    ax.set_xticks(range(1, 13), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.tick_params(axis="x", labelsize=10.5)
    ax.grid(axis="y", color="#E6EAED", linewidth=.8)
    ax.set_ylabel("Share of teleworkers")
    ax.annotate(f"{share[6]:.1f}%", (7, share[6]), xytext=(0, 13), textcoords="offset points", ha="center", fontsize=12)
    ax.annotate(f"{share[-1]:.1f}%", (12, share[-1]), xytext=(-4, 13), textcoords="offset points", ha="center", fontsize=12)
    fig.text(.02, .94, "Some hours at home, rather than all hours", fontsize=17, weight="bold")
    fig.text(.02, .86, "Monthly share among teleworkers; United States, 2024", fontsize=11)
    save(fig, "telework-monthly", "Source: IPUMS CPS; WTFINL weights. Not seasonally adjusted. Vertical axis: 40–60%.")
    print("Saved three figures, each as SVG and PNG.")


if __name__ == "__main__":
    main()

