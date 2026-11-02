# Blog Post 8: inference from 50 simulated bottles

Question: **What can 50 bottles tell us about a 500 mL label?**

The article is an English Quarto post for the existing blog. Every bottle is simulated. It makes no claim about a real product, business, or compliance standard.

## Source, assumptions, and pre-specified design

`config.json` records the design before the first run: iid normal fills with true mean 498 mL and SD 10 mL; original sample size 50; 5,000 bootstrap resamples, 5,000 fresh coverage samples, and 5,000 independent null samples. Root seed: **20261101**, split into four child streams in the documented order. The original sample and stream definitions were retained; no search over seeds or samples was used to select an outcome.

The null population has mean 500 mL and SD 10 mL. The interval/test uses each sample's estimated standard deviation, not the known generator SD. The test is two-sided with alpha 0.05 and 49 degrees of freedom.

### Three different experiments

1. **Bootstrap:** draw 50 values with replacement from the same 50 original observations, repeat 5,000 times, and record each mean. This illustrates the uncertainty of a mean; no bootstrap interval coverage claim is made.
2. **Coverage:** draw 5,000 new samples from the 498 mL population; compute `mean +/- t.ppf(.975,49)*sample_sd/sqrt(50)` with `ddof=1`; count intervals containing 498. Display the first 100 in generation order, report the rate across all 5,000.
3. **Null distribution:** draw 5,000 new samples from a 500 mL population; compute `(mean-500)/(sample_sd/sqrt(50))`. At 5%, reject when the absolute statistic exceeds `t.ppf(.975,49)`. Count simulated absolute statistics at least as large as the observed absolute statistic; the add-one Monte Carlo p-value is `(count+1)/(5000+1)`.

The t interval has exact 95% repeated-sample coverage under the specified independent normal model. A finite Monte Carlo experiment need not produce exactly 95%. Coverage and p-value Monte Carlo standard errors are saved in `results/summary.json`. The analytic t p-value is retained for reconciliation; it does not substitute for the null simulation.

## Reproduce

Use Python 3.11 or newer and the pinned packages in `requirements.txt`. From this directory:

```sh
python -m pip install -r requirements.txt
python code/run_all.py
python code/build_notebook.py
```

`code/analysis.ipynb` is portable, executed, and contains calculations and three native Matplotlib figures. It can also run in a normal Python 3 Jupyter kernel with the listed dependencies. `build_notebook.py` creates a temporary kernel in the ignored `.runtime/` directory using the current Python; it does not change a system kernel or environment setting.

The article is `index.qmd`, prepared for GitHub Pages with `draft: false`. See [the article](https://devinshen123.github.io/devinshen123-website/blog/posts/post8/). Article numeric text and accessibility descriptions are generated from saved results by `code/write_post.py`. The larger `data/simulation_inputs.npz` file is retained locally and excluded from Git; `python code/run_all.py` regenerates it deterministically before verification. No source download or account is required.

## Files

- `data/original_sample.csv`: the 50 simulated measurements.
- `data/simulation_inputs.npz`: all raw samples and bootstrap indices, generated locally for independent verification.
- `results/bootstrap_means.csv`: the 5,000 means plotted in Figure 1.
- `results/coverage_intervals.csv`: all 5,000 intervals and coverage indicators.
- `results/null_statistics.csv`: all 5,000 null statistics, tail and rejection indicators.
- `results/summary.json`: calculated article numbers, settings, library versions, sources, sample hash and limitations.
- `results/validation.json`: independent formula and library reconciliation.
- `results/word-count.json`: article word count and inclusion rules.
- `results/*.svg` / `*.png`: three exportable figures. SVG text is converted to paths for consistent fonts; accessibility descriptions remain in the article.

## Validation scope

`verify.py` recomputes every saved bootstrap mean, coverage interval, and null statistic from raw arrays using standard-library `statistics.mean` and `statistics.stdev`, rather than calling the analysis helpers. It cross-checks the original t statistic, p-value, and interval with `scipy.stats.ttest_1samp` and its `confidence_interval` method. It checks two-sided tails, correct null centering through calibration, repeat counts, bootstrap index reuse, and test/interval agreement.

This validates the hypothetical experiment and its implementation. It does not validate the model's assumptions for any real production line. Measurements from correlated batches, changing processes, skewed fills, or imprecise instruments require a different assessment.

## Method references

Read November 1, 2026. These are methodological references; the data are generated locally.

- [NIST: Confidence Limits for the Mean](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm): t interval, repeated-sample interpretation, two-sided rejection rule.
- [SciPy: bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html): same-size sampling with replacement and the bootstrap distribution.
- [SciPy: ttest_1samp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_1samp.html): independent implementation of the one-sample t test and matching interval.
