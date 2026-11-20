"""Separate finite-background placement uncertainty from group uncertainty."""
from collections import defaultdict
import numpy as np
from scipy.stats import beta


def clopper_pearson(successes, trials, confidence=0.95):
    if not isinstance(successes, int) or not isinstance(trials, int) or not 0 <= successes <= trials or not 0 < confidence < 1:
        raise ValueError('Invalid independent-binomial counts/confidence')
    if trials == 0: return None
    alpha = 1-confidence
    return [0.0 if successes == 0 else float(beta.ppf(alpha/2, successes, trials-successes+1)),
            1.0 if successes == trials else float(beta.ppf(1-alpha/2, successes+1, trials-successes))]


def rate(rows, outcome, searchable=False, weighted=True):
    arm = outcome.split('_')[0]
    chosen = [r for r in rows if r['eligible'] and (not searchable or r.get(arm+'_stages', {}).get('searchable', r['searchable']))]
    denominator = sum(r['weight'] if weighted else 1 for r in chosen)
    numerator = sum((r['weight'] if weighted else 1)*bool(r[outcome]) for r in chosen)
    return {'numerator': numerator, 'denominator': denominator, 'rate': numerator/denominator if denominator else None,
            'eligible_signals': len(chosen)}


def _interval(values):
    lo, hi = np.quantile(values, [0.025, 0.975]).tolist()
    return {'empirical_percentiles_95': [lo, hi], 'interval_95': [lo, hi] if lo != hi else None,
            'status': 'exploratory_percentile_interval' if lo != hi else 'degenerate_resampling_uncertainty_unresolved'}


def uncertainty(rows, outcomes, seed=20261124, replicates=10000):
    if replicates < 1000: raise ValueError('Too few bootstrap replicates')
    if not rows: return {'status': 'no_executed_outcomes'}
    if any(not np.isfinite(r['weight']) or r['weight'] <= 0 for r in rows): raise ValueError('Invalid benchmark weight')
    narm = len(outcomes)
    rng = np.random.default_rng(seed)
    strata = defaultdict(lambda: defaultdict(list))
    for r in rows:
        strata[(r['component_id'], r['family'], r['peak_power_sigma'])][r['trial_id']].append(r)
    conditional_num = np.zeros((replicates, narm)); conditional_den = np.zeros(replicates)
    for _, trials in sorted(strata.items()):
        # Collision companions share a randomized trial and are never resampled independently.
        trial_values, trial_den = [], []
        for _, signals in sorted(trials.items()):
            trial_den.append(sum(r['weight']*r['eligible'] for r in signals))
            trial_values.append([sum(r['weight']*r['eligible']*bool(r[arm]) for r in signals) for arm in outcomes])
        draws = rng.integers(len(trial_values), size=(replicates, len(trial_values)))
        conditional_den += np.asarray(trial_den)[draws].sum(axis=1)
        conditional_num += np.asarray(trial_values)[draws].sum(axis=1)
    valid = conditional_den > 0
    conditional = conditional_num[valid]/conditional_den[valid, None]
    groups = sorted({r['component_id'] for r in rows})
    group_num, group_den = [], []
    for component in groups:
        selected = [r for r in rows if r['component_id'] == component and r['eligible']]
        group_den.append(sum(r['weight'] for r in selected))
        group_num.append([sum(r['weight']*bool(r[a]) for r in selected) for a in outcomes])
    environment = None
    if len(groups) >= 2:
        draws = rng.integers(len(groups), size=(replicates, len(groups)))
        den = np.asarray(group_den)[draws].sum(axis=1); num = np.asarray(group_num)[draws].sum(axis=1)
        environment = num[den > 0]/den[den > 0, None]
    contrasts = [('new_safe', 'legacy_safe'), ('new_safe', 'new_strict')]
    result = {'component_count': len(groups), 'trial_count': len({r['trial_id'] for r in rows}),
              'replicates': replicates, 'seed': seed, 'observing_environment_few_group_warning': len(groups) < 20,
              'placement_unit': 'whole randomized trial within fixed component/family/amplitude strata',
              'environment_unit': 'whole acquisition/target/raw-data component, paired outcomes and weights retained',
              'arms': {}, 'contrasts': {}, 'population_precision_gate_passed': False}
    for j, arm in enumerate(outcomes):
        result['arms'][arm] = {'full_declared_domain': rate(rows, arm), 'searchable_domain': rate(rows, arm, True),
                              'conditional_placement': _interval(conditional[:, j]) if len(conditional) else None,
                              'observing_environment': _interval(environment[:, j]) if environment is not None and len(environment) else None}
    for right, left in contrasts:
        if right not in outcomes or left not in outcomes: continue
        j, k = outcomes.index(right), outcomes.index(left)
        key = right+'_minus_'+left
        r_rate, l_rate = rate(rows, right)['rate'], rate(rows, left)['rate']
        result['contrasts'][key] = {'point_difference': r_rate-l_rate if r_rate is not None and l_rate is not None else None,
                                   'conditional_placement': _interval(conditional[:, j]-conditional[:, k]) if len(conditional) else None,
                                   'observing_environment': _interval(environment[:, j]-environment[:, k]) if environment is not None and len(environment) else None}
    return result


def independent_cell_intervals(rows, outcome):
    """Exact diagnostic intervals only for IID single-signal placements in ONE background/cell."""
    cells = defaultdict(list)
    for row in rows: cells[(row['component_id'], row['family'], row['peak_power_sigma'])].append(row)
    result = []
    for (component, family, amplitude), cell in sorted(cells.items()):
        if len({r['trial_id'] for r in cell}) != len(cell):
            interval, status = None, 'companion_signals_correlated_use_trial_bootstrap'
        else:
            eligible = [r for r in cell if r['eligible']]
            interval = clopper_pearson(sum(bool(r[outcome]) for r in eligible), len(eligible))
            status = 'conditional_independent_random_placements_on_one_fixed_background'
        result.append({'component_id': component, 'family': family, 'peak_power_sigma': amplitude,
                       'interval_95': interval, 'status': status})
    return result
