# Post 3: working from home in 2024

Question: **Among U.S. workers who worked from home in 2024, was it more common to work all hours at home or only some hours?**

This directory contains the article source, replication code, and aggregate results for Blog Post 3. The article was rewritten around 2024 telework hours on October 25, 2026. The previous unemployment article was retained in a separate local backup; its older R files are not part of this analysis.

## Source and extract

- IPUMS CPS, University of Minnesota; underlying CPS data from the U.S. Census Bureau and Bureau of Labor Statistics.
- Extract number 2, created October 25, 2026 at the user's request.
- Twelve **Basic Monthly** samples, January–December 2024. No ASEC samples.
- Original compressed fixed-width data: `data/raw/cps_00002.dat.gz`.
- Original DDI codebook: `data/raw/cps_00002.xml`.
- 1,187,356 person-month records and 16 variables, including 10 preselected technical fields.
- These are repeated survey observations, not 1,187,356 distinct people.

The original files remain local and are excluded by `.gitignore`. Replicators should obtain their own IPUMS extract. Raw files, account-specific XML, and signed download URLs must not be published.

## Request the same data

1. Sign in at [IPUMS CPS](https://cps.ipums.org/).
2. Deselect default samples. Select Basic Monthly and all twelve months of 2024; keep ASEC unselected.
3. Add **AGE, EMPSTAT, AHRSWORKT, EDUC, TELWRKPAY, TELWRKHR**. Retain preselected YEAR, MONTH, SERIAL, PERNUM, ASECFLAG, WTFINL, CPSID, CPSIDP, CPSIDV, and HWTFINL.
4. Use rectangular cross-sectional, fixed-width `.dat` output. Request all cases; age/status filtering occurs in code.
5. Download both the compressed data and DDI XML, keeping matching filenames in `data/raw/`. If a new extract has a different number, adjust the two filenames in the scripts.

## Definitions and checks

The study population is civilian adults ages 16+ **at work during the reference week**, identified by `EMPSTAT == 10`. People employed but absent all week are outside the telework question's universe.

- `TELWRKPAY`: 1 = yes, 2 = no, 0 = not in universe. Codes are checked against this extract's DDI.
- `TELWRKHR`: hours of paid telework in the reference week; 999 is not in universe.
- `AHRSWORKT`: actual total hours worked across all jobs that same week.
- Some hours at home: positive telework hours smaller than valid actual hours.
- All hours at home: positive telework hours equal to valid actual hours.
- Two telework responses have incomplete/inconsistent hours and remain an explicit unknown category. They are excluded only from calculations requiring a complete hours split.
- `WTFINL` in raw fixed-width data has four implied decimals. The parser divides by 10,000 once. Libraries such as `ipumsr` already perform that adjustment.
- ASECFLAG is structurally blank outside March. These blanks must not cause non-March Basic Monthly records to be discarded.
- Annual population levels average the twelve weighted monthly totals; annual percentages are ratios of those average levels, not unweighted averages of monthly percentages.
- The within-teleworker denominator is valid some-hours plus all-hours teleworkers. Figure 1 instead uses everyone at work as its denominator.
- January 2024 telework linking keys were revised by IPUMS; this is a fresh extract, not an old telework snapshot. See [IPUMS revisions](https://cps.ipums.org/cps-action/revisions).

The data describe hours in one reference week. They do not identify permanent employment contracts, preference for remote work, or the location of remaining work hours. Telework covers all jobs and cannot be attributed to a particular job for multiple jobholders. No seasonal adjustment, causal estimates, confidence intervals, or significance tests are claimed. CPS respondents recur across months, so naive independent-row standard errors would be inappropriate.

## Reproduce

Python 3.11+ is required. Install `matplotlib`, `pandas`, `nbformat`, `nbclient`, and `ipykernel` for the complete workflow. The core data check uses only the standard library.

From this directory:

```sh
python -m pip install -r requirements.txt
python code/check_data.py
python code/verify_data.py
python code/make_figures.py
python code/write_post.py
quarto render index.qmd --to html
```

The check notebook `code/data_checks.ipynb` provides the same data checks and shows saved figures. Use a Python environment containing the listed packages.

## Files to review

- `index.qmd` / `article.md`: the English rewrite; numeric values are generated from saved results.
- `results/telework-status.svg`: shares doing no, some, or all work at home.
- `results/telework-intensity.svg`: distribution of the fraction of working hours spent at home.
- `results/telework-monthly.svg`: whether the annual split also appears within individual months.
- `results/annual_summary.csv`, `monthly_summary.csv`, `remote_fraction_distribution.csv`: exact chart inputs.
- `results/variables.csv`, `sample_counts.csv`, `inventory.json`: source-file and sample checks, hashes, and data limitations.
- `results/independent_reconciliation.json`: separate pandas import compared with the standard-library parser.
- `results/word-count.txt`: word count and inclusion rules.

## Official documentation

- [TELWRKPAY](https://cps.ipums.org/cps-action/variables/TELWRKPAY)
- [TELWRKHR](https://cps.ipums.org/cps-action/variables/TELWRKHR)
- [AHRSWORKT](https://cps.ipums.org/cps-action/variables/AHRSWORKT)
- [WTFINL](https://cps.ipums.org/cps-action/variables/WTFINL)
- [BLS telework definitions and questions](https://www.bls.gov/cps/telework.htm)
- [IPUMS citation guidance](https://cps.ipums.org/cps/citation.shtml)

