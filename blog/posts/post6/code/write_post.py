"""Generate the article from saved NLS estimates."""
from __future__ import annotations
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/Devinshen123/devinshen123-website/tree/main/blog/posts/post6"

def visible_word_count(text):
    body = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    body = re.sub(r"!\[([^\]]*)\]\([^\n]*?\)\{[^\n]*\}", r"\1", body)
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
    body = re.sub(r"^```[^\n]*$", "", body, flags=re.M)
    return len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", body))

def main():
    summary = json.loads((ROOT / "results/summary.json").read_text(encoding="utf-8"))
    estimates = {r["specification"]: r for r in summary["estimates"]}
    differences = {r["comparison"]: r for r in summary["differences"]}
    annual = estimates["annual_both"]["ige"]
    parent_average = estimates["average_mother"]["ige"]
    averaged = estimates["average_both"]["ige"]
    change = differences["average_both minus annual_both"]
    age_change = differences["age35 minus age20"]
    age_values = ", ".join(f"{estimates[f'age{age}']['ige']:.3f}" for age in [20, 25, 30, 35])
    averaging_note = ("The confidence interval for the change includes zero, so the difference is uncertain." if change["ci_low"] <= 0 <= change["ci_high"] else "The paired confidence interval for the change excludes zero.")
    age_note = ("The oldest-minus-youngest confidence interval includes zero, so the apparent age difference is uncertain." if age_change["ci_low"] <= 0 <= age_change["ci_high"] else "The paired oldest-minus-youngest confidence interval excludes zero.")
    article = f'''---
title: "Does one year's pay tell the whole story?"
description: "Match mothers and children with SQL in Python, then test how income averaging and measurement age change the estimated earnings link."
author: "Defang Shen"
date: 2026-10-23
categories: [SQL, Economic mobility]
image: results/income-age.png
lightbox: true
format:
  html:
    toc: false
---

Does a single year's pay tell us how closely children's earnings track their mothers'? Using {summary['children']:,} children linked to {summary['mothers']:,} mothers, I find little change when I replace annual earnings with averages. Measuring children at different ages also changes the estimates, but those differences are uncertain.

This tutorial uses the NLSY79 and its Child/Young Adult study. Here, income means wages, salaries and military pay, rather than total household resources. Using the same definition avoids comparing a mother's family budget with a child's own paycheck. The [notebook]({REPO}/code/tutorial.ipynb) runs the complete Python and SQL workflow; the steps below explain the matching and comparisons.

## Build one row per child

Start with the identifiers. A child's `CPUBID` identifies that child; `MPUBID` identifies their biological mother and matches her `CASEID` in NLSY79. Siblings share a mother ID. A household number alone cannot establish this relationship because household membership changes.

Python loads the extracts into SQLite, cleans missing codes and assigns amounts to the year earned. SQL adjusts earnings to 2020 dollars. From `stage_income`, summarize each person's age window:

```sql
SELECT generation, person_id, stage,
       AVG(real_income) AS mean_income,
       COUNT(DISTINCT income_year) AS observed_years
FROM stage_income
GROUP BY generation, person_id, stage;
```

`SELECT` chooses columns; `GROUP BY` collects person-window records; `AVG` and `COUNT` calculate mean earnings and observed years. Save these as `stage_averages`. Then `JOIN` links each child to both generations' summaries:

```sql
SELECT c.child_id, c.mother_id,
       m.mean_income AS mother_mean, a.mean_income AS adult_mean
FROM children AS c
JOIN stage_averages AS m
  ON m.person_id = c.mother_id AND m.stage = 'mother30s'
JOIN stage_averages AS a
  ON a.person_id = c.child_id AND a.stage = 'child30s';
```

Summarizing first prevents repeated survey years from multiplying matches. The full query applies eligibility rules and creates `matched`, with one row per child. Check that child IDs are unique after matching; duplicates would give some children extra weight in the regression.

## Compare annual earnings with averages

Compare the annual observation nearest age 35 with average earnings at ages 30–39. Mothers need at least three observed years; children need at least two. Years need not be consecutive. Average inflation-adjusted amounts before taking logs. Include genuine zeros in averages, exclude missing answers, and require positive measures for logarithms.

With pandas, NumPy and statsmodels imported, estimate the averaged model:

```python
sample = pd.read_sql_query("SELECT * FROM matched", connection)
x = pd.DataFrame({{
    "log_mother": np.log(sample.mother_mean),
    "mother_age": sample.mother_mean_age - 35,
    "child_age": sample.adult_mean_age - 35,
    "female": (sample.child_sex == 2).astype(int),
    "birth_year": sample.child_birth_year - 1978,
}})
fit = sm.OLS(np.log(sample.adult_mean), sm.add_constant(x)).fit(
    cov_type="cluster", cov_kwds={{"groups": sample.mother_id}},
    use_t=True)
```

The `log_mother` coefficient is the intergenerational earnings elasticity (IGE). An estimate of {averaged:.3f} associates 10% higher maternal earnings with roughly {10 * averaged:.1f}% higher child earnings. This is an association, not a causal effect. Keep children and adjustments fixed across models; cluster uncertainty by mother because siblings share a parent.

![Figure 1. IGE using annual or averaged earnings for the same {summary['children']:,} children. Bars show 95% confidence intervals clustered by mother.](results/annual-versus-average.svg){{fig-alt="Three elasticities compare annual earnings, averaged maternal earnings with annual child earnings, and averages in both generations."}}

Figure 1 gives {annual:.3f} with annual earnings, {parent_average:.3f} after averaging mothers' earnings, and {averaged:.3f} after averaging both generations. {averaging_note} Averaging spreads a temporary bonus or job loss across several observations, improving the proxy for longer-run earnings. It does not guarantee a higher IGE.

## Check the child's age

Hold maternal averages and adjustments fixed. Select each child's annual observation nearest the midpoint of each five-year band, from 20–24 to 35–39. Keep the same children throughout, so changing participants cannot explain differences.

![Figure 2. IGE at four child-age bands, holding maternal averages fixed. The sample and confidence-interval method match Figure 1.](results/income-age.svg){{fig-alt="Elasticities for child income measured at ages 20 to 24, 25 to 29, 30 to 34, and 35 to 39."}}

The estimates are {age_values}, in age order. {age_note} [Haider and Solon](https://public.websites.umich.edu/~gsolon/workingpapers/haider.pdf) explain the life-cycle problem: people with higher lifetime earnings can have faster earnings growth, so early earnings can understate eventual differences. Figure 2 checks sensitivity to age; it cannot measure bias against unobserved lifetime income.

Check both how many income observations were used and when they were measured. Averaging addresses short-term fluctuations; it does not automatically fix life-cycle bias.

These unweighted results describe selected families with repeated observations and positive selected annual earnings in every age band. They are not national mobility estimates. Earnings exclude self-employment, and age changes alongside calendar time.

## Sources

[NLS data](https://www.nlsinfo.org/content/access-data-investigator/accessing-data-cohorts), [family linkage](https://www.nlsinfo.org/content/cohorts/nlsy79-children/using-and-understanding-the-data/linking-children-young-adults-and), [earnings definitions](https://nlsinfo.org/content/cohorts/nlsy79-children/topical-guide/income/introduction), and [annual CPI-U](https://www.minneapolisfed.org/about-us/monetary-policy/inflation-calculator/consumer-price-index-1913-).
'''
    (ROOT / "index.qmd").write_text(article, encoding="utf-8")
    without_code = re.sub(r"^```.*?^```\s*$", "", article, flags=re.M | re.S)
    print(json.dumps({"visible_words_including_captions_and_code": visible_word_count(article),
                      "prose_words_including_captions": visible_word_count(without_code),
                      "children": summary["children"], "mothers": summary["mothers"]}))

if __name__ == "__main__":
    main()
