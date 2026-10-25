# Blog Post 7: How much extra did 15 gallons cost in California?

Question: From 2020 through 2025, how much extra did a fixed purchase of 15 U.S. gallons of regular gasoline cost at California's average price compared with the U.S. average?

After running the build, open results/Blog_Post_7_Review.html as the offline article preview. It includes the actual Plotly.js runtime, all 313 observations and controls. It needs no internet connection to draw the figure. [index.qmd](index.qmd) is prepared for GitHub Pages. This repository does not submit anything to Canvas.

## Reproduce from saved inputs

Python 3.10+ and Node.js are sufficient. No pip or npm installation is needed. From this directory:

    python code/run.py
    node code/verify_data.cjs

The first command checks saved source hashes, recomputes results and rebuilds the article and figure. The second independently checks the extracted tables, integer arithmetic and JavaScript date-window summaries.

To test browser interactions using an existing Chrome installation and Node.js 22+:

    node code/verify_browser.cjs

The checker starts a separate headless browser with an isolated profile under qa, serves only this post locally, and closes its own processes after testing. It does not use the user's open browser or account. Actual results go to results/interaction_checks.json. Screenshots remain local under qa.

Reconstruct the matched CSV and source lock from saved table extracts:

    python code/acquire.py

Download the official HTML histories again on a computer with network access:

    python code/acquire.py --refresh
    python code/run.py

Refresh can incorporate historical revisions. Review changes before replacing an analysis. Parsing uses Python's standard library. Missing observations cause a failure instead of being filled with zeros.

## Sources and definitions

- [California history](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=W&n=PET&s=EMM_EPMR_PTE_SCA_DPG), series EMM_EPMR_PTE_SCA_DPG.
- [U.S. history](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=W&n=PET&s=EMM_EPMR_PTE_NUS_DPG), series EMM_EPMR_PTE_NUS_DPG.
- [EIA definitions and survey notes](https://www.eia.gov/dnav/pet/tbldefs/pet_pri_gnd_tbldef2.asp).
- [EIA regional-price explanation](https://www.eia.gov/energyexplained/gasoline/regional-price-differences.php).

Prices are nominal U.S. dollars per U.S. gallon, for regular gasoline across all formulations, including taxes. They are Monday cash pump-price estimates, generally self-service. EIA uses volume weights within each geographic estimate. This analysis gives each observed week equal weight when averaging differences. The national benchmark includes California.

The initial inputs were programmatically retrieved from official EIA HTML tables through the connected web reader. Raw files are explicitly labeled extracted tables, not downloaded HTML. They retain published date and price cells for all 72 months. provenance.json records that route; the refresh script provides direct HTML acquisition. SHA-256 hashes identify the snapshots, normalized CSV and vendored Plotly runtime.

There are 313 matching Monday observations, January 6, 2020–December 29, 2025. Each year has 52 except 2024, which has 53. None is missing, interpolated or imputed.

## Calculation and interaction

    extra_15_gallons = 15 * (ca_price - us_price)

Python uses Decimal. The browser uses integer thousandths of a dollar until display. Prices have three decimals; currency displays use two; exports retain three. Period means include observed dates within the inclusive selected window. Ties for extrema report the earliest date.

One figure offers extra cost for 15 gallons and underlying pump prices. Year selection, date inputs, zoom/range slider, summaries, weekly details and selected-data export describe the same window. Empty windows report no observations, not a zero cost. Reversed dates are rejected without changing selection.

Fifteen gallons is a comparison quantity, not a tank size or household purchase. Results do not measure household spending, every station's prices, real purchasing power or causal policy effects. Minima and maxima show variation over dates, not confidence bounds.

## Files

- code/acquire.py: official-table parsing, source lock and optional refresh.
- code/analyze.py: data checks and exact calculations.
- code/render.py, run.py: article and offline figure build.
- code/verify_data.cjs, verify_browser.cjs: independent data/browser checks.
- assets/chart.js, style.css: figure and controls.
- assets/plotly-basic-3.0.1.min.js: vendored Plotly.js; MIT license retained.
- data/raw: public EIA extracts and provenance.
- data/processed/weekly_prices.csv: matched prices.
- data/source-lock.json: SHA-256 inputs.
- results/weekly_comparison.csv, yearly_summary.csv, summary.json: calculations.
- results/chart.html: offline figure for the Quarto iframe.
- results/Blog_Post_7_Review.html: self-contained article preview.
- results/data_checks.json, build.json, interaction_checks.json: actual check records.

The inputs contain only published aggregate fuel prices. No individual income records, course slides or credentials are included.


## Verification status in this environment

Data checks passed for all 313 dates. Independent integer calculations agree with Python Decimal results. Seventeen checks exercise the actual chart.js control handlers using a controlled DOM and Plotly API stub, including date selection, view switching, range events, empty/invalid dates, detail selection and the selected-data CSV contents.

Actual Chrome 155 and Plotly.js 3.0.1 passed native hover, all six year filters, date windows, zoom synchronization, empty/invalid dates, keyboard inspection and CSV download checks on a GitHub-hosted runner. The rendered Quarto page and its iframe also passed at 1280px and 390px with no horizontal overflow and all 313 observations present. See the [browser verification run](https://github.com/Devinshen123/devinshen123-website/actions/runs/40227252730). The browser checker uses the runner's existing Chrome installation and installs no packages. Windows Chrome could not start in the local restricted environment; the hosted check supplies the actual rendering evidence.

On publication, the workflow checks the public page, figure and downloadable files against the deployed commit and exercises the public iframe again. It records actual outcomes in results/public_checks.json and results/interaction_checks.json.

The preview footer includes a downloadable source ZIP with this post's code, public data, saved calculations and check records. It excludes browser profiles, screenshots and all other blog posts.
