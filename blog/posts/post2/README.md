# Blog Post 2: Which data skills should I learn first?

This project uses R and rvest to scrape public DataAnalyst.com job pages, count six technical skills, and suggest a practical learning priority. The sample is deliberately small; it is not an estimate for the US labor market.

## Files

- `index.qmd`: blog article; numerical findings are read from generated result files.
- `code/scrape.R`: collect job HTML with rvest, extract text and metadata, filter and deduplicate listings.
- `code/analyze.R`: skill indicators, counts, audit contexts, and a bar chart.
- `data/raw/`: saved source HTML, robots rules, and collection timestamp.
- `data/listing_audit.csv`: the 100 regular cards on the listing page, with inclusion flags.
- `data/jobs.csv`: the 50 selected postings and extracted responsibilities/requirements.
- `results/`: generated chart, skill counts, job-level flags, match contexts, metrics, and R session information.

## Reproduce the saved analysis

Install R and these CRAN packages once:

```r
install.packages(c("rvest", "knitr", "rmarkdown"), repos = "https://cloud.r-project.org")
```

Open a terminal in this folder (`blog/posts/post2`), then run:

```sh
Rscript code/scrape.R
Rscript code/analyze.R
```

The supplied HTML snapshot allows the first command to reproduce the extraction without requesting the site again. The second command uses only the saved CSV. See `results/session-info.txt` for the versions actually used. Base R handles the analysis and plotting; no API key, Python, or database is needed.

To build the website, install Quarto, return to the repository root, and run `quarto render`. The output is in `docs/`. Rendering reads saved results and does not scrape the website.

## Collect a fresh sample (optional)

First review the website's current robots rules and policies. Then, from this folder:

```sh
Rscript code/scrape.R --live
Rscript code/analyze.R
```

Live mode puts newly downloaded HTML in a separate dated snapshot folder and replaces the extracted CSV and result files. It can produce different results as listings change. The original HTML in `data/raw` remains available; running the default commands restores its results. Review the article's interpretation before publishing a new sample.

The scraper pauses three seconds before every HTML request, fetches just one listing page and at most 50 detail pages, and stops on request errors. It does not use authentication, CAPTCHA solving, proxy rotation, employer application pages, or automatic retries. For a new collection, the script stops if it finds a nonempty Disallow rule, so changed rules can be reviewed manually. This intentionally conservative check is not a general-purpose robots parser.

## Selection and measurement

Source: https://www.dataanalyst.com/job-experience/entry-level-data-analyst-jobs

From the first listing page's regular cards, keep listings labeled `0 - 3 years` and `Active`, with `data analyst` in the title. Exclude titles containing senior, sr, lead, principal, manager, or director. Deduplicate by URL and company/title/location, then take the first 50 in displayed order. Featured advertisements and additional pages are excluded. This is a convenience sample from the board's category, not a guarantee that every description requires at most three years or that every opening remains available.

Use only responsibilities and requirements, not company biographies, benefits, or related listings. Each posting contributes at most one count per skill. SQL, Python, Tableau, and Power BI are matched without regard to case; PowerBI is also accepted. Capitalized Excel avoids matching the ordinary verb; uppercase standalone R avoids matching other words. This can miss unusual spellings. Contexts for every positive match are saved in `results/match_audit.csv` for review. Requirements-section counts provide a sensitivity check, but still include preferred skills and alternatives, not only mandatory requirements.

Skills can overlap, so percentages need not sum to 100%. A mention is not evidence of the skill's hiring impact. The chart covers only the six prespecified tools. A single board, repeated employers, remote-work concentration, older listings, and category errors limit generalization.

## Access review

At collection, https://www.dataanalyst.com/robots.txt had an empty `Disallow:` entry for `User-agent: *`. Public pages worked without access restrictions. The linked privacy policy was reviewed; no separate scraping prohibition was found there. This is not a claim of explicit permission from the operator. Collection was small and cached. Source HTML is retained for reproducibility, not to create a competing job board; the article reports aggregate counts.

Package documentation: https://rvest.tidyverse.org/reference/read_html.html
