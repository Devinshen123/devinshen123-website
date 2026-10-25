# Blog Post 6: matching mothers and children with SQL

This tutorial links biological mothers in NLSY79 to their adult children in the NLSY79 Child and Young Adult study. It asks how the estimated earnings association changes when income is measured once, averaged over several observations, or observed at different adult ages.

## Reproduce the results

The public repository contains code, source definitions and aggregate results. Individual income records are downloaded from the official NLS site and kept locally. From this post's directory:

```sh
python -m venv .venv
# Windows:
.venv/Scripts/python -m pip install -r code/requirements.txt
.venv/Scripts/python code/acquire.py
.venv/Scripts/python code/run.py
```

On macOS/Linux, replace `.venv/Scripts/python` with `.venv/bin/python`. Python 3.14.5 was used; exact analysis packages are pinned. `acquire.py` downloads the official sources once. After that, `run.py` rebuilds the SQLite database, estimates, figures and article without network requests. The article's reported numbers come from `results/summary.json` through `code/write_post.py`.

The executed [companion notebook](code/tutorial.ipynb) shows the SQL queries, estimates and figures. Open it in a Python environment with the pinned packages, or run it top to bottom with Jupyter. Run the acquisition command before executing the notebook. Individual records and the rebuilt database remain local. The full matching SQL is in [code/match.sql](code/match.sql).

From the website root, render the post and listing:

```sh
quarto render blog/posts/post6/index.qmd
quarto render blog/index.qmd
```

Quarto uses the generated figures. It does not download data or execute earlier posts' analysis.

## Download the official source data again

```sh
.venv/Scripts/python code/acquire.py
.venv/Scripts/python code/fetch_cpi.py --output-dir data/raw
.venv/Scripts/python code/run.py
```

The two official cohort archives total about 618 MB compressed. They contain much larger uncompressed files. Acquisition streams the CSV members and retains only the columns in `data/raw/variable-crosswalk.json`; it does not expand the entire archive onto disk. Use `--cache-dir PATH` to reuse downloaded ZIPs. The archives' SHA-256 hashes are checked. A changed release stops acquisition so its definitions can be reviewed before combining it with the saved crosswalk.

Local source snapshots are `data/raw/mothers.csv.gz` and `children.csv.gz`; these are excluded from Git. They retain the original reference-number columns and negative missing codes. Only mothers whose ID appears in the children's MPUBID column are kept. The acquisition and CPI provenance files record URLs, retrieval times, release hashes and precision. Publication date and retrieval date are separate fields.

## Income and matching rules

- Mother CASEID (`R00001.00`) matches child MPUBID (`C00002.00`). CPUBID (`C00001.00`) uniquely identifies a child. The code checks the mother's sex and unique person keys. It never infers a relationship by matching names or cutting digits from an ID.
- Earnings are gross wages, salary, commissions, tips and military pay. They exclude self-employment, transfers and a partner's income. Mothers' civilian wages and military pay are combined; YA military pay is separate through 1998 and included in wages from 2000 onward. A documented military-receipt answer of no supplies a zero component. All negative wage codes remain missing; reported zero dollars remain zero.
- Maternal birth year uses corrected 1981 information, with 1979 information as a fallback; two-digit years receive 1900. Analysis mothers are restricted to births in 1957-1964. Child CYRB is already a four-digit year.
- The crosswalk's fixed income-reference year is used when the question explicitly names one. YA 2014 onward instead uses actual interview year minus one. Age is income year minus birth year: calendar-year-end age. It is not age on the interview date.
- If two surveys report the same person's income for one calendar year, an observed amount takes priority over a missing amount, then the later survey wins. The local `results/duplicate_income_years.csv` records these keys; public diagnostics report the count without individual IDs.
- Each annual amount is converted to 2020 dollars using annual CPI-U. The Minneapolis Fed table publishes one decimal. Arithmetic means are taken across observed nonnegative real amounts, then positive means are logged. Missing years are not zeros, and `log(income+1)` is not used.

SQL constructs annual records and window means before joining them to the child table, so repeated survey waves cannot multiply mother-child pairs. Maternal means use ages 30-39 with at least three observed income years; child means require at least two observations in each of the twenties and thirties windows. Observations are not consecutive annual readings: older YA respondents were generally fielded every four years from 2010.

Annual measures select the observed income nearest age 35 for mothers and adult children, and nearest 25 for the broad twenties comparison. An earlier year wins an equally close tie. The age profile uses all four complete bands 20-24, 25-29, 30-34 and 35-39, selecting the reading nearest 22, 27, 32 and 37. Selection occurs before checking whether the chosen amount is positive.

The two figures use the same complete sample, with positive selected annual earnings in all four age bands and positive broad-window annual measures. These restrictions select earlier-born children and mothers with relatively early childbearing. Exact exclusions, cohort ranges and observation counts are saved in `results/summary.json`.

## Models and interpretation

OLS regresses log child earnings on log maternal earnings. Every specification uses the same nuisance variables: mother and child thirties-window mean ages, child sex and child birth year. Those adjustment vectors stay fixed when income measures change. Mother-clustered CR1 standard errors and t intervals allow siblings' residuals to be related. Paired contrasts use the covariance between specifications; separate interval overlap is not the test of a difference.

The age profile is exploratory. Calendar periods change as the same people age. Finite-window averages are proxies for longer-run earnings, not measured lifetime income. The code also saves `broad_window_sensitivity.csv`: a larger sample without the four-band requirement. Its broad twenties/thirties comparison is weak, and it must not be treated as evidence of a large age effect.

Results are unweighted descriptions of this selected linked sample, not national estimates of U.S. mobility or causal effects of mothers' income. Round weights are included in the extraction crosswalk for inspection; this complete-case panel would need defensible custom longitudinal weights for a population claim. Public top-coded values are retained, including revised maternal wage series where available. Averaging does not undo top coding, attrition, selection or all life-cycle bias.

## Files

- `code/acquire.py`, `fetch_cpi.py`: source acquisition and provenance.
- `code/analyze.py`, `match.sql`: cleaning, SQL matching, models and checks.
- `code/plot_results.py`, `write_post.py`, `run.py`: figures, article and saved-input pipeline.
- `code/tutorial.ipynb`: executed Python and SQL walkthrough.
- `data/raw/`: public crosswalk, CPI and provenance; downloaded individual records are excluded.
- `data/processed/analysis.sqlite`: rebuilt local database, excluded from Git.
- `results/estimates.csv`, `differences.csv`: coefficients, confidence intervals and paired comparisons.
- `results/matched_sample.csv`: local person-level constructed measures, excluded from Git.
- `results/summary.json`, `audit.json`, `wave_checks.csv`: sample counts, input hashes and checks.
- `results/*.svg`, `*.png`: the two figures.

## Sources

- [Official NLS cohort downloads](https://www.nlsinfo.org/content/access-data-investigator/accessing-data-cohorts): NLSY79 1979-2022 and Child/Young Adult 1979-2020 releases.
- [NLS mother-child linkage documentation](https://www.nlsinfo.org/content/cohorts/nlsy79-children/using-and-understanding-the-data/linking-children-young-adults-and).
- [YA income definitions and top coding](https://www.nlsinfo.org/content/cohorts/nlsy79-children/topical-guide/income/introduction).
- [YA sample weights and fielding](https://www.nlsinfo.org/content/cohorts/nlsy79-children/using-and-understanding-the-data/sample-weights).
- [Annual CPI-U, Minneapolis Fed](https://www.minneapolisfed.org/about-us/monetary-policy/inflation-calculator/consumer-price-index-1913-), underlying source BLS.
- Haider and Solon (2006), [Life-Cycle Variation in the Association between Current and Lifetime Earnings](https://public.websites.umich.edu/~gsolon/workingpapers/haider.pdf), *American Economic Review*, 96(4), 1308-1320. The linked author manuscript is dated 2005.
