-- One record per person's actual income year. Prefer an observed amount, then
-- the later survey, if two surveys refer to the same calendar year.
CREATE TABLE annual_income AS
SELECT generation, person_id, income_year, wave, birth_year, income_nominal
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY generation, person_id, income_year
        ORDER BY (income_nominal IS NULL), wave DESC
    ) AS record_rank
    FROM source_income
    WHERE income_year IS NOT NULL AND birth_year > 0
)
WHERE record_rank = 1;

CREATE UNIQUE INDEX annual_key ON annual_income(generation, person_id, income_year);

-- Convert each observed annual amount to 2020 dollars before averaging.
CREATE TABLE real_income AS
SELECT i.generation, i.person_id, i.income_year, i.wave,
       i.income_year - i.birth_year AS income_age,
       i.income_nominal * base.cpi / prices.cpi AS real_income
FROM annual_income AS i
JOIN cpi AS prices ON prices.year = i.income_year
JOIN cpi AS base ON base.year = 2020
WHERE i.income_nominal >= 0;

CREATE TABLE stage_income AS
SELECT *, CASE
    WHEN generation = 'mother' THEN 'mother30s'
    WHEN income_age BETWEEN 20 AND 29 THEN 'child20s'
    ELSE 'child30s'
END AS stage
FROM real_income
WHERE (generation = 'mother' AND income_age BETWEEN 30 AND 39)
   OR (generation = 'child' AND income_age BETWEEN 20 AND 39);

-- Genuine observed zeros count in both the average and the observation count.
CREATE TABLE stage_averages AS
SELECT generation, person_id, stage,
       AVG(real_income) AS mean_income,
       AVG(income_age) AS mean_age,
       COUNT(DISTINCT income_year) AS observed_years,
       SUM(real_income = 0) AS zero_years,
       MIN(income_year) AS first_year, MAX(income_year) AS last_year
FROM stage_income
GROUP BY generation, person_id, stage;

-- Select the annual observation closest to 25 or 35, before examining its value.
-- An equally close earlier year wins a tie. Zero annual earnings later exclude
-- a pair from the common logarithmic comparison; they are never replaced by 1.
CREATE TABLE stage_singles AS
SELECT generation, person_id, stage, real_income AS single_income,
       income_age AS single_age, income_year AS single_year
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY generation, person_id, stage
        ORDER BY ABS(income_age - CASE WHEN stage = 'child20s' THEN 25 ELSE 35 END),
                 income_year ASC, wave DESC
    ) AS distance_rank
    FROM stage_income
)
WHERE distance_rank = 1;

-- Aggregate first, then match on the documented mother ID. Siblings may share
-- a mother, but each child contributes one row to each regression.
CREATE TABLE matched_candidates AS
SELECT c.child_id, c.mother_id, c.birth_year AS child_birth_year,
       c.sex AS child_sex, m.birth_year AS mother_birth_year,
       ma.mean_income AS mother_mean, ma.mean_age AS mother_mean_age,
       ma.observed_years AS mother_n, ma.zero_years AS mother_zero_years,
       ms.single_income AS mother_single, ms.single_age AS mother_single_age,
       ms.single_year AS mother_single_year,
       ya.mean_income AS young_mean, ya.mean_age AS young_mean_age,
       ya.observed_years AS young_n, ya.zero_years AS young_zero_years,
       ys.single_income AS young_single, ys.single_age AS young_single_age,
       ys.single_year AS young_single_year,
       pa.mean_income AS adult_mean, pa.mean_age AS adult_mean_age,
       pa.observed_years AS adult_n, pa.zero_years AS adult_zero_years,
       ps.single_income AS adult_single, ps.single_age AS adult_single_age,
       ps.single_year AS adult_single_year
FROM children AS c
JOIN mothers AS m ON m.mother_id = c.mother_id
LEFT JOIN stage_averages AS ma ON ma.person_id = c.mother_id AND ma.stage = 'mother30s'
LEFT JOIN stage_singles AS ms ON ms.person_id = c.mother_id AND ms.stage = 'mother30s'
LEFT JOIN stage_averages AS ya ON ya.person_id = c.child_id AND ya.stage = 'child20s'
LEFT JOIN stage_singles AS ys ON ys.person_id = c.child_id AND ys.stage = 'child20s'
LEFT JOIN stage_averages AS pa ON pa.person_id = c.child_id AND pa.stage = 'child30s'
LEFT JOIN stage_singles AS ps ON ps.person_id = c.child_id AND ps.stage = 'child30s';

CREATE TABLE matched_broad AS
SELECT * FROM matched_candidates
WHERE mother_birth_year BETWEEN 1957 AND 1964
  AND child_sex IN (1, 2)
  AND mother_n >= 3 AND young_n >= 2 AND adult_n >= 2
  AND mother_mean > 0 AND young_mean > 0 AND adult_mean > 0
  AND mother_single > 0 AND young_single > 0 AND adult_single > 0;

CREATE UNIQUE INDEX broad_child ON matched_broad(child_id);


-- Explore every complete five-year band in the observed adult ages20-39.
-- Each coefficient uses one annual observation nearest that band's midpoint.
CREATE TABLE age_band_singles AS
WITH candidates AS (
    SELECT person_id AS child_id, income_age, real_income, income_year, wave,
           20 + 5 * CAST((income_age - 20) / 5 AS INTEGER) AS lower_age
    FROM real_income
    WHERE generation = 'child' AND income_age BETWEEN 20 AND 39
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY child_id, lower_age
        ORDER BY ABS(income_age - lower_age - 2), income_year, wave DESC
    ) AS band_rank
    FROM candidates
)
SELECT * FROM ranked WHERE band_rank = 1;

-- Use one common balanced sample for BOTH published figures. Keep the larger
-- broad-window sample as a sensitivity check rather than hiding its results.
CREATE TABLE matched AS
SELECT b.*, a20.real_income AS age20, a20.income_age AS age20_age,
       a25.real_income AS age25, a25.income_age AS age25_age,
       a30.real_income AS age30, a30.income_age AS age30_age,
       a35.real_income AS age35, a35.income_age AS age35_age
FROM matched_broad b
JOIN age_band_singles a20 ON a20.child_id=b.child_id AND a20.lower_age=20
JOIN age_band_singles a25 ON a25.child_id=b.child_id AND a25.lower_age=25
JOIN age_band_singles a30 ON a30.child_id=b.child_id AND a30.lower_age=30
JOIN age_band_singles a35 ON a35.child_id=b.child_id AND a35.lower_age=35
WHERE a20.real_income > 0 AND a25.real_income > 0
  AND a30.real_income > 0 AND a35.real_income > 0;
CREATE UNIQUE INDEX matched_child ON matched(child_id);
