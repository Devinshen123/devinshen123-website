# Blog Post 4: home prices and mortgage payments

Analysis of U.S. new-home prices and illustrative mortgage payments, 2021–2024.

## Reproduce the saved analysis

Install Node.js 18 or later. No npm packages are required. From this directory, run:

```sh
node code/analyze.mjs
```

This reads three saved CSVs, validates their coverage, computes 16 quarterly observations, and writes three SVG figures, quarterly results, a summary, and an audit with source-file hashes. The offline analysis and the programmatic FRED refresh workflow have both been verified.

To download current FRED data first:

```sh
node code/analyze.mjs --refresh
```

The network refresh path was executed successfully for all three FRED series. It can change historical values because the providers revise data. Preserve the current raw CSVs and provenance if exact reproduction of this draft is needed.

Install Quarto and render from the existing website repository root:

```sh
quarto render
```

The site configuration includes this article in the render list.

## Files

- `index.qmd`: English article with three figures, interpretations, methods, and references.
- `data/raw/*.csv`: official-source observations for 2021–2024.
- `data/raw/provenance.json`: retrieval date, method, and source URLs.
- `code/analyze.mjs`: full analysis and SVG plot generation, plus optional CSV retrieval.
- `results/quarterly.csv`: all plotted and interpreted values.
- `results/*.svg`: scalable charts with labels and units.
- `results/audit.json`: observation counts, validation checks, runtime, and SHA-256 hashes.
- `results/summary.json`: exact numerical values used in the prose.

## Methods

MSPUS is the median price of **new** homes sold. It is quarterly and not seasonally adjusted. CPIAUCSL is monthly and seasonally adjusted. MORTGAGE30US is weekly and not seasonally adjusted. Rates are equal-weight means of published weekly rates assigned by date to a calendar quarter, and CPI is the mean of the three months in each quarter. No interpolation is used.

The loan is 80% of the median sale price, with 360 equal monthly principal-and-interest payments. All quarters describe hypothetical newly originated loans, not payments on one continuing mortgage. Payments are calculated from the mean rate, not averaged over individual weekly hypothetical loans. Prices and payments in real terms use the 2021 Q1 CPI as their base. Chart 1 uses indexed prices and a clearly disclosed nonzero vertical-axis origin. Rate and payment charts use zero as their lower bound. Color and solid/dashed lines distinguish the two price/payment series.

The constant-rate comparison changes only the mortgage-rate input, fixing it at the 2021 Q1 mean, 2.875833333333333%. It is a mechanical scenario, not a causal estimate or an equilibrium policy counterfactual. Figures do not imply that rate changes caused the observed price changes.

