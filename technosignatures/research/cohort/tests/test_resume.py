import json
from pathlib import Path
import pytest

from research.cohort.frame import write
from research.cohort.run import run
from test_evaluation import background


def test_interrupted_experiment_resumes_to_identical_scientific_records(tmp_path, monkeypatch):
    import research.cohort.run as module
    cadence = background()
    monkeypatch.setattr(module, 'load_cadence', lambda *args: cadence)
    cfg = {'version': 'synthetic_resume_fixture', 'seed': 7, 'placements_per_family_amplitude_total': 2,
           'families': ['continuous_linear'], 'amplitudes': [8.], 'search': {'max_abs_drift_hz_per_s': .25},
           'legacy_cap': 50, 'time_subsamples': 8, 'group_tolerance_channels': 3., 'cadence_off_score_threshold': 6.,
           'bootstrap_replicates': 1000, 'max_wall_s': 120}
    config = tmp_path/'config.json'; write(config, cfg)
    acquisition = tmp_path/'acquisition.json'
    write(acquisition, {'acquired_complete_cadences': 1, 'selected_cadences': 1,
                        'selection_sha256': 'synthetic_unit', 'frequency_plan_sha256': 'synthetic_unit',
                        'cadences': [{'selection': {'component_id': 'synthetic', 'sampling_weight': 1., 'partition': 'development'},
                                      'source_records': [{'archive_id': 'synthetic', 'scientific_array_sha256': {}}]}]})
    original = module.evaluate_trial; calls = []
    def interrupt(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2: raise KeyboardInterrupt('synthetic controlled interruption')
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'evaluate_trial', interrupt)
    with pytest.raises(KeyboardInterrupt): run(tmp_path/'resumed', acquisition, tmp_path, config)
    assert len(list((tmp_path/'resumed/trials').glob('*.json'))) == 1
    monkeypatch.setattr(module, 'evaluate_trial', original)
    run(tmp_path/'resumed', acquisition, tmp_path, config, resume=True)
    run(tmp_path/'fresh', acquisition, tmp_path, config)
    for name in ['signal_rows.jsonl', 'trial_metrics.jsonl', 'summary.json', 'uncertainty.json', 'sensitivity_cells.json']:
        assert (tmp_path/'resumed'/name).read_bytes() == (tmp_path/'fresh'/name).read_bytes(), name
    cfg['trial_workers'] = 2; write(config, cfg)
    run(tmp_path/'threaded', acquisition, tmp_path, config)
    for name in ['signal_rows.jsonl', 'trial_metrics.jsonl', 'summary.json', 'uncertainty.json', 'sensitivity_cells.json']:
        assert (tmp_path/'threaded'/name).read_bytes() == (tmp_path/'fresh'/name).read_bytes(), name
    cfg['seed'] = 8; write(config, cfg)
    with pytest.raises(ValueError, match='Resume rejected'): run(tmp_path/'resumed', acquisition, tmp_path, config, resume=True)
