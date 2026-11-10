# Blog Post 9: replication

This draft asks whether one extra predictor, stock momentum relative to SPY, improves return forecasts and investment results. The article reports one held-out period and does not optimize against the test data.

## Inputs and how to run

1. From the post directory, run `python code/download_yahoo.py`. It uses the 95 stocks, SPY, and date bounds in `study_config.json` and defaults to November 9, 2026. Provider revisions can change prices and results. See [data notes](data/README.md).
2. Install the R packages `dplyr`, `tidymodels`, `slider`, `xgboost`, and `jsonlite`. Run `Rscript code/compare_models.R .` from the post directory. The settings and seed from the [instructor's model](https://canvas.upenn.edu/courses/1942733/files?search_term=stock&preview=166069948) are recorded in `study_config.json`; the market analysis does not require Canvas access. The reference run used R 4.6.2, tidymodels 1.5.0 and xgboost 3.2.1.1.
3. Run `python code/verify_comparison.py` for independent checks and `python code/render_wealth.py` with Matplotlib to rebuild the plot.
4. If you have access to Penn Canvas, `Rscript code/summarize_class_game.R PATH_TO_RESULTS.xlsx results/comparison/classroom_summary.csv` (with readxl) rebuilds the aggregate classroom comparison from the [instructor's spreadsheet](https://canvas.upenn.edu/courses/1942733/discussion_topics/11420590).

## Design

- Target and trading: at signal date t, the target is the adjusted close at t+20 divided by the adjusted close at t+1, minus one. The order is filled at the next close. The 34 monthly holding windows do not overlap. They use each month's first trading day as the signal and compound on exit, with zero cash return between windows. No trading costs are included.
- Training cutoff: every retained training target ends before 2024-01-01. Models fit once and use the same test rows, with signals from 2024-01-02 to 2026-10-12. Portfolio windows run from the first entry on 2024-01-03 to the final exit on 2026-10-29.
- Models: the original uses the instructor's XGBoost settings and feature definitions (including the original lagged price ratios). The new model adds only the stock's lagged 21-session total return minus SPY's lagged return over the same window, measured from t-22 to t-1.
- Benchmarks: one constant equal to the pooled training return mean for forecasting, equal weights across the same 95 stocks for the no-selection portfolio, and SPY over exactly the same entry and exit dates for a market comparison.
- The provider can retrospectively rescale nominal prices and volume. In the robustness run, both models omit raw price and volume levels. The direction of the comparison persists, but the precise values differ. The main results keep the original inputs to isolate the new feature. The fixed stock list is not a point-in-time market universe.
- Positive forecasts are weighted proportionally after truncating negative values to zero; if all ten forecasts are nonpositive, the model allocates equal weights to those ten. Portfolio totals are checked against 100% every month. The original script's daily annualization factors are not used.

Source, code, and results are organized separately. The instructor's private files and raw provider responses are not bundled. See the output CSVs and `results/comparison/audit.json` for exact values.
