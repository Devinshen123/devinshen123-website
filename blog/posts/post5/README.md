# Blog Post 5: rent pressure in Los Angeles County

Question: Do Los Angeles County's highest-rent census tracts also have the largest shares of renters spending at least 30% of household income on gross rent?

## Reproduce the analysis

Tested with Python 3.14.5, GeoPandas 1.2.0 and Quarto 1.10.18. Package versions are pinned in `requirements.txt`. From this post's directory:

```sh
python -m venv .venv
# Windows:
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python code/analyze.py
.venv/Scripts/python code/write_post.py
```

On macOS/Linux, replace `.venv/Scripts/python` with `.venv/bin/python`. The saved-input analysis makes no network requests. It generates both maps, the grouped comparison, all CSVs, the summary and audit, then the article's numerical references.

To download a fresh source snapshot:

```sh
.venv/Scripts/python code/fetch.py --refresh
.venv/Scripts/python code/analyze.py
.venv/Scripts/python code/write_post.py
```

`fetch.py` downloads Census tables B25064 and B25070 and the 2024 California tract boundaries, then selects Los Angeles County (FIPS 037). It preserves the published estimates and margins of error and uses ACS variable names. The county geometry and tabular snapshot are included in this folder; the larger download cache is excluded from Git. Existing snapshots are reused unless `--refresh` is supplied.

From the website repository root, render the post and listing:

```sh
quarto render blog/posts/post5/index.qmd
quarto render blog/index.qmd
```

These commands use the saved figures. GitHub Pages publishes the compiled `docs/` directory.

## Files

- `index.qmd`: article, figure captions, accessible descriptions and sources.
- `code/fetch.py`: reproducible acquisition, safe extraction and source hashes.
- `code/analyze.py`: cleaning, GIS join, projection, calculations, figures and audit.
- `code/write_post.py`: inserts saved numerical results into the article.
- `data/raw/acs_tracts.json`, `acs_county.json`: header-plus-row arrays of official estimates and margins of error.
- `data/raw/la_tracts.geojson`: county subset of official 2024 cartographic geometry; source CRS EPSG:4269.
- `data/raw/provenance.json`, `geometry-provenance.json`: exact source URLs, retrieval time, hashes and geographic selection.
- `results/tract_results.csv`: all 2,498 tract records, original variables, derived values, uncertainty and exclusion flags.
- `results/rent_bands.csv`: pooled results for the four fixed rent bands.
- `results/sensitivity_50.csv`: alternative estimated-household cutoff.
- `results/*.png`: programmatically generated figures.
- `results/summary.json`, `audit.json`: numerical results, source hashes, software versions and checks.

## Definitions and geographic checks

The survey is the **2020–2024 ACS five-year estimate**, not a current rental listing dataset. ACS dollar amounts are already in 2024 purchasing power. B25064 is median gross rent for occupied units paying cash rent, including the utilities covered by the Census definition. B25070 covers all renter-occupied units. Its not-computed category includes no-rent-paid units and households with zero or negative income.

Eligible denominator = `B25070_001E - B25070_011E`. At-least-30% numerator = sum of `007E` through `010E`; at-least-50% numerator = `010E`. Counts in every tract reconcile with the total, and summing tract B25070 estimates reproduces every corresponding county count. County median rent comes from the county table, never from averaging tract medians.

Negative missing-value sentinels become missing. Reported median values of 3501 or plus annotations mean **$3,500 or more**, not precisely $3,501. The map's top class is $3,000+, and the grouped comparison's top band is $2,500+, so upper censoring does not create ambiguous band assignments.

The maps and grouped figures use 2,325 tracts with valid median rent and at least 100 estimated households with computable ratios, accounting for 99.23% of the county's eligible households. This is an author stability rule, not an unweighted sample-size threshold. A 50-household cutoff changes each band's burden rate by less than 0.063 percentage point. Group rates sum household counts first rather than averaging tract rates.

Geometry joins one-to-one on 11-digit GEOID and is projected to California Albers (EPSG:3310). The boundary file has 2,495 features. Three tracts found only in the ACS tables (9901.00, 9902.00 and 9903.00) each have zero renter households. Both maps use the same urban zoom, a full-county inset and fixed legend classes. Place labels provide orientation. Map area represents land, not household counts.

## Uncertainty and interpretation

The charts retain original Census 90% MOEs. Derived sums and differences use root-sum-of-squares approximations. Shares use the Census subset-proportion approximation and the ratio fallback when its subtraction radicand is negative. Group intervals cannot account for unavailable covariances or uncertainty in assigning a tract to a rent band. They are approximate; the article makes no claim of statistical significance for close tract differences.

These are descriptive comparisons among areas and their existing renters, not effects of moving or causal estimates of housing policy. Tracts are statistical units, not official neighborhoods. The burden measure omits households without a computable ratio and does not account for transport costs, household size, savings or housing quality. It does not measure the full affordability of a new lease.

## Sources

- [2024 ACS table-based Summary File documentation](https://www.census.gov/programs-surveys/acs/data/summary-file.2024.html).
- [B25064 public data file](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25064.dat).
- [B25070 public data file](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25070.dat).
- [2024 California tract cartographic boundaries, 1:500,000](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_06_tract_500k.zip).
- [2024 ACS subject definitions](https://www2.census.gov/programs-surveys/acs/tech_docs/subject_definitions/2024_ACSSubjectDefinitions.pdf).
- [Census guide to derived margins of error](https://www.census.gov/content/dam/Census/library/publications/2019/acs/acs_aian_handbook_2019_ch08.pdf).

Retrieved October 19, 2026, Pacific time. The snapshot and source hashes preserve the published results if historical data are revised.
