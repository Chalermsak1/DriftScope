import pytest
from research.cohort.statistics import clopper_pearson, uncertainty, independent_cell_intervals


def rows():
    return [{'trial_id': f'{g}_{i}', 'component_id': str(g), 'family': 'linear', 'peak_power_sigma': 1.,
             'weight': 1., 'eligible': True, 'searchable': i != 0, 'new_safe': i != 0,
             'new_strict': i == 3, 'legacy_safe': i == 3} for g in range(3) for i in range(4)]


def test_exact_binomial_intervals_do_not_hide_zero_failure_uncertainty():
    assert clopper_pearson(0, 0) is None
    assert clopper_pearson(0, 8)[0] == 0
    assert clopper_pearson(8, 8)[1] == 1
    assert 0.6 < clopper_pearson(8, 8)[0] < 0.7
    assert clopper_pearson(1, 2) == pytest.approx([0.0125791171, 0.9874208829])


def test_conditional_and_cluster_uncertainties_are_separate_and_paired():
    a = uncertainty(rows(), ['new_safe', 'new_strict', 'legacy_safe'], replicates=1000)
    b = uncertainty(rows(), ['new_safe', 'new_strict', 'legacy_safe'], replicates=1000)
    assert a == b and a['component_count'] == 3
    contrast = a['contrasts']['new_safe_minus_legacy_safe']
    assert contrast['point_difference'] == 0.5
    assert contrast['conditional_placement']['interval_95'] is not None
    assert contrast['observing_environment']['interval_95'] is None
    assert a['observing_environment_few_group_warning']


def test_collision_companions_resample_as_trials_and_do_not_get_binomial_ci():
    r = rows()[:4]; companion = {**r[1], 'new_safe': False}; r.append(companion)
    result = uncertainty(r, ['new_safe', 'new_strict', 'legacy_safe'], replicates=1000)
    assert result['trial_count'] == 4 and result['component_count'] == 1
    assert result['arms']['new_safe']['observing_environment'] is None
    assert independent_cell_intervals(r, 'new_safe')[0]['interval_95'] is None


def test_full_and_searchable_denominators_remain_distinct():
    result = uncertainty(rows(), ['new_safe', 'legacy_safe'], replicates=1000)
    arm = result['arms']['new_safe']
    assert arm['full_declared_domain']['rate'] == 0.75
    assert arm['searchable_domain']['rate'] == 1
