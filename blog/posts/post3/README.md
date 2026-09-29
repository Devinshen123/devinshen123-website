# Blog Post 3: education and jobs

Question: How do unemployment, labor-force participation, and employment differ by education among civilians ages 25–64 in 2019 and 2024?

## Files

- `index.qmd`: article; numerical results are inserted from the saved CSV using R.
- `code/analyze.R`: imports IPUMS microdata, checks samples, recodes, weights, aggregates, and draws three figures.
- `data/README.md`: instructions for obtaining the source data yourself.
- `results/annual_rates.csv`: eight education/year rows, weighted annual-average population levels and percentage rates.
- `results/monthly_totals.csv`: weighted components and unweighted record counts for all 96 education/year/month cells.
- `results/sample_audit.csv`, `observed_codes.csv`, and `code-labels.txt`: sample and recode checks.
- `results/*.png`: programmatically generated figures.
- `results/session-info.txt`: R and package versions used.

## Reproduce

Install R and these packages:

```r
install.packages(c("ipumsr", "dplyr", "ggplot2", "knitr", "rmarkdown"))
```

Obtain the data as described in `data/README.md`, then run from this post's directory:

```sh
Rscript code/analyze.R data/raw/cps_00001.xml
```

Replace the filename if your extract has a different number. Keep its matching `.dat.gz` alongside the XML. `ipumsr` reads the compressed file and applies implied weight decimals automatically; do not divide the imported weight by 10,000 again.

Install Quarto, then run `quarto render` from the website repository root. Rendering reads saved aggregate results, so it does not need access to the private microdata or contact IPUMS. To reproduce the estimates, run the analysis first.

## Methods and checks

The extract contains 24 Basic Monthly samples, all months of 2019 and 2024; no ASEC. YEAR and MONTH identify monthly samples. ASECFLAG must not equal 1. March Basic is coded 2. The code checks that each year contains all twelve months.

Restrict AGE to 25–64. Education groups use EDUC codes:

| Group | Codes |
|---|---|
| Less than high school | 002, 010, 020, 030, 040, 050, 060, 071 |
| High school diploma or equivalent | 073 |
| Some college / associate degree | 081, 091, 092 |
| Bachelor's or higher | 111, 123, 124, 125 |

EMPSTAT 10 and 12 are employed; 20, 21, and 22 are unemployed; 30–36 are outside the labor force. The actual modern samples use 21/22 and 32/34/36. Code 1 (Armed Forces) and 0 (not in universe) are excluded. Missing education/status and nonpositive/nonfinite weights are excluded. In this extract, 1,331,759 records met the age restriction; 7,093 Armed Forces records were excluded, leaving 1,324,666 person-month observations. No other age-eligible records were excluded. These are repeated observations, not this many distinct individuals.

For every month and education group, sum **WTFINL**, the Basic Monthly person weight, for population (P), employed (E), unemployed (U), and labor force (L = E + U). Average the twelve monthly totals for each year. Calculate:

- unemployment rate = 100 × U / L;
- participation rate = 100 × L / P;
- employment-to-population ratio = 100 × E / P.

Ratios of annual-average levels are equivalent to using WTFINL/12 on pooled monthly records. They are not the unweighted average of twelve monthly rates. Retain nonparticipants in P. The code checks the identity E/P = (L/P) × (1 − U/L).

All estimates are unadjusted descriptive annual averages for the civilian noninstitutional population in the age range. No regression, seasonal adjustment, or confidence intervals are used. CPS respondents recur across months; naive independent-observation standard errors would be inappropriate. Education groups have different demographic compositions, and the comparisons do not identify a causal effect of schooling. Small year-to-year differences are not claims of statistical significance.

## Source

Flood et al. (2025), *IPUMS CPS: Version 13.0*. https://doi.org/10.18128/D030.V13.0. Full citation in the article. Extract generated September 28, 2026, Pacific time (XML production date September 29 UTC).

- https://cps.ipums.org/cps-action/variables/WTFINL
- https://cps.ipums.org/cps-action/variables/EDUC
- https://cps.ipums.org/cps-action/variables/EMPSTAT
- https://cps.ipums.org/cps/resources/cpr/tp66.pdf (annual-average method, printed p. 10–15)

The public repository contains aggregate results and code. Raw IPUMS files and account-specific XML metadata are kept locally and excluded from Git.
