"""Generate article prose and numeric labels from the retained simulation results."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def run():
    s = json.loads((ROOT / "results/summary.json").read_text(encoding="utf-8"))
    observed, boot, coverage, null = (s[k] for k in ("observed", "bootstrap", "coverage", "null"))
    body = f'''A 500 mL label gives us a number to check. Suppose individual bottles vary, and inspecting every bottle is expensive. **What can a random sample of 50 bottles tell us about whether the average fill really equals 500 mL?**

The question concerns the average across a stable production process. It does not ask whether every bottle contains 500 mL, or how many bottles fall below it. Those would require different calculations.

I explored this with a simulated bottling line: independent, normally distributed fills with a true mean of 498 mL and a standard deviation of 10 mL. These are teaching assumptions, not measurements of a real product. Knowing the true mean lets us check whether our statistical methods work. An inspector examining real bottles would not know that number.

The first sample averaged {observed["mean_ml"]:.2f} mL. That is below the label, but a sample average can differ from the population average by chance. I used three experiments to examine what the difference means.

## How much could a sample average move?

![Bootstrap means from the same 50 simulated bottles. The reference lines identify the sample mean, known population mean, and label.](results/bootstrap-distribution.svg){{#fig-bootstrap fig-alt="Histogram of 5,000 bootstrap sample means, centered near {observed['mean_ml']:.2f} mL; the true mean is 498 mL and the label is 500 mL."}}

For the bootstrap, I repeatedly drew 50 observations from the original sample, with replacement. A bottle's measurement could appear several times or not at all. After each draw, I calculated another average. This follows [SciPy's description of bootstrap resampling](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html).

@fig-bootstrap shows the resulting 5,000 averages. They cluster around the sample average, with a standard deviation of {boot["standard_error_ml"]:.2f} mL. This is the bootstrap estimate of the average's standard error: uncertainty about an average, rather than the variation between individual bottles.

Resampling cannot reveal the true mean automatically. Here the histogram is centered below the known 498 mL because the original sample happened to underestimate it.

## What does 95% confidence look like in practice?

![First 100 of 5,000 independently generated samples and their 95% t intervals. The reported coverage uses all 5,000.](results/confidence-coverage.svg){{#fig-coverage fig-alt="One hundred horizontal confidence intervals with a vertical line at the known true mean of 498 mL. Intervals missing that line have cross markers. Across all 5,000 trials, {100*coverage['rate']:.2f} percent cover the true mean."}}

Next, I generated 5,000 fresh samples from the 498 mL population. For each, I constructed a two-sided Student's t interval with 49 degrees of freedom: the sample average plus or minus about {null["critical_t"]:.2f} estimated standard errors. These are t intervals; the bootstrap histogram above is a separate experiment.

Of the intervals, {coverage["covered_count"]:,} contained 498 mL: {100*coverage["rate"]:.2f}%. @fig-coverage displays the first 100 in generation order. Most cross the true-mean line; a few miss it. The overall rate need not equal exactly 95% in a finite simulation.

As [NIST explains](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm), confidence describes the procedure's long-run coverage. It is not a statement that 95% of bottles are adequately filled. For our original sample, the same procedure gives an interval from {observed["ci95_lower_ml"]:.2f} to {observed["ci95_upper_ml"]:.2f} mL.

The known 498 mL lies inside it, whereas 500 mL does not. This distinction becomes useful when we ask whether the sample is consistent with the label.

## Would this result be unusual if the label were correct?

![The same simulated null distribution shown twice: fixed rejection regions above, and the tails used to estimate this sample's p-value below.](results/null-distribution.svg){{#fig-null fig-alt="Two histograms of 5,000 t statistics generated under a 500 mL mean. The upper panel shades the fixed two-sided 5 percent rejection regions beyond plus or minus {null['critical_t']:.2f}; the lower panel shades values at least as extreme as the observed t of {observed['t_statistic']:.2f}."}}

The last experiment assumes the true mean really is 500 mL. From 5,000 new samples, I calculated [t statistics](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_1samp.html), which measure the distance between a sample average and 500 mL in estimated standard errors.

In @fig-null, the upper panel shows the pre-set 5% rejection rule: reject equality when the statistic falls beyond approximately {null["critical_t"]:.2f} in either direction. Our sample's statistic is {observed["t_statistic"]:.2f}, inside the left rejection region.

The lower panel answers the p-value question. Under that 500 mL model, how often would a statistic be at least as far from zero as ours, in either direction? There were {null["extreme_count"]} such simulations. With a one-count correction, the estimated p-value is {null["monte_carlo_p"]:.4f}, comfortably below 0.05. This is evidence against the 500 mL mean under the model, not the probability that the label is correct.

The simulation's Monte Carlo standard error is about {null["mc_p_standard_error"]:.4f}. Extra repetitions would stabilize the p-value estimate; they would not add information to the original bottle sample.

This sample detects a shortfall, but its estimated size is noisy: the sample average is below even the known 498 mL. The interval communicates that uncertainty. Applying these methods to a real production line would require checking independence and process stability; repeated bottles from one batch could tell us less than this simulation assumes.

Data: entirely simulated. [Replication and assumptions](README.md) · [Saved calculations](results/summary.json) · [Runnable notebook](code/analysis.ipynb).
'''
    title = "What Can 50 Bottles Tell Us About a 500 mL Label?"
    visible = re.sub(r'!\[([^\]]*)\]\([^)]*\)\{[^}]*\}', r'\1', body)
    visible = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', visible)
    visible = re.sub(r'@fig-[a-z-]+', 'Figure', visible)
    token_pattern = r"[0-9]+(?:[,.][0-9]+)*|[A-Za-z]+(?:[’'-][A-Za-z]+)*"
    count = len(re.findall(token_pattern, title + "\n" + visible))
    prose = re.sub(r'!\[[^\]]*\]\([^)]*\)\{[^}]*\}', '', body)
    prose = re.sub(r'^#+ .*$', '', prose, flags=re.M)
    prose = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', prose)
    prose = re.sub(r'@fig-[a-z-]+', 'Figure', prose)
    prose_count = len(re.findall(token_pattern, prose))
    assert 600 <= count <= 800, f"Article length: {count} words"
    assert 600 <= prose_count <= 800, f"Prose length: {prose_count} words"
    header = '''---
title: "What Can 50 Bottles Tell Us About a 500 mL Label?"
description: "Three simulation experiments explain sampling uncertainty, confidence intervals, and p-values."
author: "Defang Shen"
date: 2026-11-01
categories: [Simulation, Statistical inference]
draft: false
image: results/bootstrap-distribution.png
format:
  html:
    toc: false
    lightbox: true
resources:
  - README.md
  - config.json
  - results/summary.json
  - results/coverage_intervals.csv
  - results/bootstrap_means.csv
  - results/null_statistics.csv
  - code/analysis.ipynb
---

'''
    (ROOT / "index.qmd").write_text(header + body, encoding="utf-8")
    (ROOT / "article.md").write_text("# " + title + "\n\n" + body, encoding="utf-8")
    (ROOT / "results/word-count.json").write_text(json.dumps({
        "words": count,
        "prose_words_excluding_headings_and_captions": prose_count,
        "included": "Page title, section headings, prose, figure captions and source/replication note",
        "excluded": "YAML metadata, URLs, accessibility alt text and text inside chart graphics",
        "method": "Regex tokenization; numbers with decimal points or thousands separators count as one token"
    }, indent=2) + "\n", encoding="utf-8")
    print(f"English article written: {count} words including title and captions.")
    return count


if __name__ == "__main__":
    run()
