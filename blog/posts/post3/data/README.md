# Obtain the IPUMS CPS data

1. Sign in at https://cps.ipums.org/. Registration is required.
2. Select **Basic Monthly**, January–December 2019 and January–December 2024 (24 samples). Deselect all ASEC samples and other years.
3. Add **AGE, EDUC, EMPSTAT**. Keep the preselected YEAR, MONTH, ASECFLAG, WTFINL, and identifiers. The CPS interface does not have a variable named SAMPLE; use YEAR and MONTH.
4. Request all cases as rectangular (cross-sectional) person records, fixed-width `.dat` format. The R script applies the age restriction locally.
5. Download **DOWNLOAD .DAT** (`.dat.gz`) and the **DDI** XML codebook. Save both with matching base filenames inside `data/raw/`. You may need to use “Save link as” for the XML rather than opening it in the browser.
6. From the post directory run `Rscript code/analyze.R data/raw/cps_00001.xml`, substituting your extract number.

Do not commit the raw files. The original analysis used IPUMS CPS Version 13.0; future revisions to source data or weights may change results. The public aggregate CSVs preserve the submitted results.
