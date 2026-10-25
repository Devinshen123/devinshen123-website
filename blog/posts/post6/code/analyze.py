"""Clean the saved NLS extracts, run SQL matching, and estimate earnings IGEs."""
from __future__ import annotations
import hashlib
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import numpy as np
import pandas as pd
from scipy.stats import t
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
RESULTS = ROOT / 'results'
PROCESSED = ROOT / 'data/processed'


def load_inputs():
    provenance = json.loads((RAW / 'source-provenance.json').read_text(encoding='utf-8'))
    for cohort in ['mothers', 'children']:
        digest = hashlib.sha256(gzip.open(RAW / (cohort + '.csv.gz'), 'rb').read()).hexdigest()
        assert digest == provenance['selected_csv_sha256'][cohort], 'Saved NLS source extract changed.'
    cpi_provenance = json.loads((RAW / 'cpi-provenance.json').read_text(encoding='utf-8'))
    cpi_bytes = (RAW / 'cpi_annual.csv').read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(cpi_bytes).hexdigest() == cpi_provenance['output_sha256']
    mapping = json.loads((RAW / 'variable-crosswalk.json').read_text(encoding='utf-8'))
    frames = {cohort: pd.read_csv(RAW / (cohort + '.csv.gz')) for cohort in ['mothers', 'children']}
    people = {}
    records = []
    wave_checks = []
    for cohort, frame in frames.items():
        rule = mapping[cohort]
        generation = 'mother' if cohort == 'mothers' else 'child'
        person_id = frame[rule['id']['column']].astype(int)
        assert person_id.is_unique
        if cohort == 'mothers':
            birth = frame[rule['birth_year_primary']['column']]
            birth = birth.where(birth.ge(0), frame[rule['birth_year_fallback']['column']])
            birth = birth.where(birth.between(0, 99)) + 1900
            people[cohort] = pd.DataFrame({'mother_id': person_id, 'birth_year': birth})
        else:
            birth = frame[rule['birth_year']['column']].where(lambda s: s.ge(1900))
            people[cohort] = pd.DataFrame({
                'child_id': person_id, 'mother_id': frame[rule['mother_id']['column']].astype(int),
                'birth_year': birth, 'sex': frame[rule['sex']['column']],
            })
        for wave in rule['waves']:
            civilian = frame[wave['wage']['column']].where(lambda s: s.ge(0))
            if wave['includes_military_in_wage']:
                earnings = civilian
            else:
                receipt = frame[wave['military_received']['column']]
                amount = frame[wave['military_amount']['column']]
                military = amount.where(receipt.eq(1) & amount.ge(0))
                military = military.mask(receipt.eq(0), 0)
                earnings = civilian + military
            if wave['income_year'] is None:
                interview_year = frame[wave['actual_interview_year']['column']]
                year = interview_year.where(interview_year.between(1900, 2100)) - 1
            else:
                year = pd.Series(wave['income_year'], index=frame.index, dtype=float)
                assert year.eq(wave['income_year']).all()
            records.append(pd.DataFrame({
                'generation': generation, 'person_id': person_id, 'wave': wave['survey_year'],
                'income_year': year, 'birth_year': birth, 'income_nominal': earnings,
            }))
            wave_checks.append({
                'generation': generation, 'wave': wave['survey_year'],
                'valid_amounts': int(earnings.notna().sum()), 'reported_zeros': int(earnings.eq(0).sum()),
                'observed_amount_missing_year': int((earnings.notna() & year.isna()).sum()),
                'income_year_min': float(year.min()), 'income_year_max': float(year.max()),
            })
    return people, pd.concat(records, ignore_index=True), pd.DataFrame(wave_checks)


def fit_model(sample, mother_measure, child_measure, key, label):
    # Freeze nuisance variables across all specifications. Age-band changes
    # change the outcome measure, not the sample or these adjustment vectors.
    parent_age = 'mother_mean_age'
    child_age = 'adult_mean_age'
    x = pd.DataFrame({
        'constant': np.ones(len(sample)),
        'log_mother_income': np.log(sample[mother_measure]),
        'mother_age': sample[parent_age] - 35,
        'child_age': sample[child_age] - 35,
        'child_female': sample['child_sex'].eq(2).astype(int),
        'child_birth_year': sample['child_birth_year'] - 1978,
    })
    assert np.linalg.matrix_rank(x.to_numpy()) == x.shape[1]
    y = np.log(sample[child_measure])
    groups = sample['mother_id'].to_numpy()
    fit = sm.OLS(y, x, missing='raise').fit(
        cov_type='cluster', cov_kwds={'groups': groups, 'use_correction': True, 'df_correction': True}, use_t=True
    )
    interval = fit.conf_int().loc['log_mother_income']
    row = {'specification': key, 'label': label, 'ige': float(fit.params['log_mother_income']),
           'standard_error': float(fit.bse['log_mother_income']), 'ci_low': float(interval.iloc[0]),
           'ci_high': float(interval.iloc[1]), 'children': len(sample), 'mothers': int(sample.mother_id.nunique()),
           'mother_measure': mother_measure, 'child_measure': child_measure}
    # Independently check the coefficient and mother-clustered sandwich variance.
    matrix = x.to_numpy()
    coefficient = np.linalg.lstsq(matrix, y.to_numpy(), rcond=None)[0]
    assert np.max(np.abs(coefficient - fit.params.to_numpy())) < 1e-9
    bread = np.linalg.inv(matrix.T @ matrix)
    influence = (matrix @ bread[:, 1]) * fit.resid.to_numpy()
    cluster_influence = pd.Series(influence).groupby(groups).sum()
    n, k = matrix.shape
    g = len(cluster_influence)
    correction = g / (g - 1) * (n - 1) / (n - k)
    independent_se = np.sqrt(correction * np.square(cluster_influence).sum())
    assert abs(independent_se - row['standard_error']) < 1e-9
    return row, cluster_influence, correction


def main():
    RESULTS.mkdir(exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    people, incomes, wave_checks = load_inputs()
    database = PROCESSED / 'analysis.sqlite'
    if database.exists():
        database.unlink()
    with sqlite3.connect(database) as connection:
        for name, frame in people.items():
            frame.to_sql(name, connection, index=False)
        incomes.to_sql('source_income', connection, index=False)
        cpi = pd.read_csv(RAW / 'cpi_annual.csv')
        assert cpi.year.is_unique and cpi.cpi.gt(0).all()
        cpi.to_sql('cpi', connection, index=False)
        connection.executescript((ROOT / 'code/match.sql').read_text(encoding='utf-8-sig'))
        sample = pd.read_sql_query('SELECT * FROM matched ORDER BY child_id', connection)
        candidates = pd.read_sql_query('SELECT * FROM matched_candidates', connection)
        broad = pd.read_sql_query('SELECT * FROM matched_broad ORDER BY child_id', connection)
        duplicate_years = pd.read_sql_query('''
            SELECT generation, person_id, income_year, COUNT(*) AS source_readings
            FROM source_income WHERE income_year IS NOT NULL
            GROUP BY generation, person_id, income_year HAVING COUNT(*) > 1
        ''', connection)
        observed = pd.read_sql_query('''
            SELECT i.generation, COUNT(*) AS observed_years, SUM(i.income_nominal=0) AS zero_years,
                   MIN(i.income_year) AS first_year, MAX(i.income_year) AS last_year
            FROM annual_income i WHERE i.income_nominal >= 0 GROUP BY i.generation
        ''', connection)
        uncovered = connection.execute('''
            SELECT COUNT(*) FROM annual_income i LEFT JOIN cpi p ON i.income_year=p.year
            WHERE i.income_nominal >= 0 AND p.year IS NULL
        ''').fetchone()[0]
        assert uncovered == 0, 'An observed income year has no matching CPI.'
        stage_summary = pd.read_sql_query('''
            SELECT stage, COUNT(*) AS people, SUM(observed_years) AS observations
            FROM stage_averages GROUP BY stage
        ''', connection)
    assert sample.child_id.is_unique and len(sample) > 100
    assert len(candidates) == len(people['children']), 'Mother join lost or multiplied children.'
    assert sample[['mother_mean','young_mean','adult_mean','mother_single','young_single','adult_single']].gt(0).all().all()
    specifications = [
        ('annual_both','mother_single','adult_single','One annual income per generation'),
        ('average_mother','mother_mean','adult_single',"Average mother; annual adult child"),
        ('average_both','mother_mean','adult_mean','Average both generations'),
        ('young_annual','mother_mean','young_single','Child in twenties: annual'),
        ('young_average','mother_mean','young_mean','Child in twenties: average'),
        ('age20','mother_mean','age20','Child ages20-24'),
        ('age25','mother_mean','age25','Child ages25-29'),
        ('age30','mother_mean','age30','Child ages30-34'),
        ('age35','mother_mean','age35','Child ages35-39'),
    ]
    estimates = []
    influence = {}
    for key, parent, child, label in specifications:
        row, scores, correction = fit_model(sample, parent, child, key, label)
        estimates.append(row)
        influence[key] = (scores, correction)
    differences = []
    lookup = {r['specification']: r for r in estimates}
    comparisons = [('average_both','annual_both'),('average_mother','annual_both'),
                   ('average_both','average_mother'),('average_mother','young_annual'),
                   ('average_both','young_average'), ('age35','age20')]
    for a, b in comparisons:
        delta = lookup[a]['ige'] - lookup[b]['ige']
        scores_a, correction_a = influence[a]
        scores_b, correction_b = influence[b]
        assert abs(correction_a - correction_b) < 1e-12
        se = np.sqrt(correction_a * np.square(scores_a - scores_b).sum())
        critical = t.ppf(.975, len(scores_a) - 1)
        differences.append({'comparison': a + ' minus ' + b, 'difference': delta, 'standard_error': se,
                            'ci_low': delta-critical*se, 'ci_high': delta+critical*se})
    broad_estimates = [fit_model(broad, parent, child, key, label)[0]
                       for key, parent, child, label in specifications[:5]]
    pd.DataFrame(broad_estimates).to_csv(RESULTS / 'broad_window_sensitivity.csv', index=False)
    pd.DataFrame(estimates).to_csv(RESULTS / 'estimates.csv', index=False)
    pd.DataFrame(differences).to_csv(RESULTS / 'differences.csv', index=False)
    sample.to_csv(RESULTS / 'matched_sample.csv', index=False)
    duplicate_years.to_csv(RESULTS / 'duplicate_income_years.csv', index=False)
    wave_checks.to_csv(RESULTS / 'wave_checks.csv', index=False)
    age_stats = sample[['mother_n','young_n','adult_n','mother_mean_age','young_mean_age','adult_mean_age',
                        'mother_single_age','young_single_age','adult_single_age']].describe().to_dict()
    valid_cohort = candidates.mother_birth_year.between(1957,1964) & candidates.child_sex.isin([1,2])
    enough = valid_cohort & candidates.mother_n.ge(3) & candidates.young_n.ge(2) & candidates.adult_n.ge(2)
    positive_means = enough & candidates[['mother_mean','young_mean','adult_mean']].gt(0).all(axis=1)
    summary = {
        'children': len(sample), 'mothers': int(sample.mother_id.nunique()),
        'child_birth_year_min': int(sample.child_birth_year.min()), 'child_birth_year_max': int(sample.child_birth_year.max()),
        'female_share': float(sample.child_sex.eq(2).mean()), 'estimates': estimates,
        'differences': differences, 'age_and_observation_counts': age_stats,
        'sample_flow': {'raw_children': len(candidates), 'valid_maternal_cohort_and_child_sex': int(valid_cohort.sum()),
                        'enough_annual_observations': int(enough.sum()), 'positive_means': int(positive_means.sum()),
                        'positive_broad_window_annuals': len(broad), 'positive_annuals_all_four_age_bands': len(sample)},
        'observed_income_coverage': observed.to_dict(orient='records'), 'stage_summary': stage_summary.to_dict(orient='records'),
        'duplicate_income_year_keys': len(duplicate_years),
        'broad_window_sensitivity': broad_estimates,
        'age_band_design': 'All four complete five-year bands20-24,25-29,30-34,35-39; nearest midpoint22,27,32,37. Same positive-earnings child-mother pairs across all bands and both figures. Exploratory age profile, not a true lifetime-income benchmark.',
        'model': 'OLS log child earnings on log mother earnings, common thirties-window mean ages for both generations, child sex and child birth year; unweighted; CR1 mother-clustered 95% t intervals.',
        'annual_selection': 'Nearest observed age35 in each thirties window, nearest25 in child twenties; earlier income year breaks ties. Chosen before positivity restriction.',
        'averaging': 'Arithmetic average of observed nonnegative real annual incomes; mother ages30-39>=3years, child20-29>=2years and30-39>=2years. These are not consecutive annual readings.',
    }
    (RESULTS / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    audit = {'checks': {'unique_child_regression_rows': True, 'all_specifications_same_children': True,
                        'mother_join_preserves_children': True, 'observed_years_have_cpi': True,
                        'independent_ols_and_cluster_se_agreement': True},
             'input_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.iterdir() if p.is_file()},
             'versions': {'python': sys.version, 'pandas': pd.__version__, 'numpy': np.__version__, 'statsmodels': sm.__version__},
             'income_records': len(incomes), 'duplicate_income_year_keys': len(duplicate_years),
             'unweighted_selected_sample': True}
    (RESULTS / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'sample': summary['sample_flow'], 'mothers': summary['mothers'], 'estimates': estimates}, indent=2), flush=True)
    return summary

if __name__ == '__main__':
    main()
