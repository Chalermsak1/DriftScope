"""Validate published v2 ledgers and reproduce the delivery validation record.

Run with the project environment: python scripts/cohort_validation.py.
This checks retained records; source/offline assertions refer to separately
executed verification. It does not reacquire or silently invent observations.
"""
import json,collections,xml.etree.ElementTree as ET
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"technosignatures"))
from research.cohort.frame import HERE,write,digest
from research.pilot.run import preserved_original
p=HERE/'results/pilot_v2'; summary=json.load(open(p/'summary.json'))
rows=[json.loads(line) for line in (p/'signal_rows.jsonl').read_text().splitlines()]
metrics=[json.loads(line) for line in (p/'trial_metrics.jsonl').read_text().splitlines()]
acq=json.load(open(HERE/'evidence/acquisition.json')); source=json.load(open(HERE/'evidence/source_verification.json'))
repeat=json.load(open(HERE/'evidence/repeat_verification_v2.json')); controls=json.load(open(p/'native_controls.json'))
checks={'planned_trials_executed':summary['trial_count']==1152==len(metrics)==len({r['trial_id'] for r in rows}),
        'physical_signal_count_reconciles':summary['physical_signal_count']==1344==len(rows)==len({r['truth_id'] for r in rows}),
        'strict_implies_safe':all(not r[a+'_strict'] or r[a+'_safe'] for a in ['new','legacy'] for r in rows),
        'no_technical_failures':all(r['failure_type'] is None for r in rows),
        'all_42_sources_acquired':acq['files_acquired']==42 and acq['acquired_complete_cadences']==7,
        'offline_reconstruction_exact':source['offline_reconstruction']['all_checks_passed'],
        'all_42_source_maps_exact':source['source_checks']['source_map_count']==42 and source['source_checks']['all_source_maps_identical'],
        'fresh_numerical_repeat_exact':repeat['numerical_repeat']['all_checks_passed'],
        'full_design_weight_sum':abs(sum(r['weight'] for r in rows)-36*182)<1e-8,
        'experiment_inputs_unchanged':json.load(open(p/'input_manifest.json'))['acquisition_sha256']==digest(HERE/'evidence/acquisition.json')}
for a in ['new_safe','new_strict','legacy_safe','legacy_strict']:
 checks[a+'_loss_reconciliation']=sum(r[a] for r in rows)==sum(r[a+'_first_loss']=='retained' for r in rows)
 denominator=sum(r['weight'] for r in rows if r['eligible']); numerator=sum(r['weight'] for r in rows if r['eligible'] and r[a])
 checks[a+'_weighted_rate_reconciliation']=abs(numerator/denominator-summary['arms'][a]['conservative']['rate'])<1e-12
sources=[r for c in acq['cadences'] for r in c['source_records']]
new_cov=[v for c in controls for v in c['arms']['new']['coverage'].values()]
legacy_cov=[v for c in controls for v in c['arms']['legacy']['coverage'].values()]
coverage={'new_physical_track_trials':sum(r['physical_track_trials'] for r in new_cov),'new_evaluated_track_trials':sum(r['evaluated_track_trials'] for r in new_cov),'new_masked_track_trials':sum(r['masked_track_trials'] for r in new_cov),'new_unscorable_track_trials':sum(r['unscorable_track_trials'] for r in new_cov),'legacy_evaluated_track_trials':sum(r['evaluated_track_trials'] for r in legacy_cov),'legacy_valid_tracks_omitted_by_common_guard':sum(r['coverage_accounting']['valid_discrete_tracks_omitted_by_common_guard'] for r in legacy_cov),'legacy_native_candidates_lost_to_cap':sum(r['candidates_lost_to_cap'] for r in legacy_cov),'scope':'Once per source scan in uninjected controls; repeated OFF reuse and injected trials are not multiplied into observing coverage.'}
checks['coverage_decomposition']=coverage['new_physical_track_trials']==coverage['new_evaluated_track_trials']+coverage['new_masked_track_trials']+coverage['new_unscorable_track_trials']
q=source['source_checks']['quadrature_audits']
suites=list(ET.parse(HERE/'evidence/tests_complete_pipeline.xml').getroot().iter('testsuite'))
tests={k:sum(int(s.get(k,0)) for s in suites) for k in ['tests','errors','failures','skipped']}
checks['full_regression_suite_passed']=tests['tests']==159 and not any(tests[k] for k in ['errors','failures','skipped'])
result={'all_checks_passed':all(checks.values()),'checks':checks,'tests':tests,'preservation':preserved_original(),
 'observational_samples':{'source_files':len(sources),'cadences':len(acq['cadences']),'linked_components':7,'power_samples':sum(r['sample_count'] for r in sources),'usable_samples':sum(r['usable_sample_count'] for r in sources),'stored_integrations':sum(r['excerpt_shape'][0] for r in sources),'exposure_s':sum(r['excerpt_shape'][0]*r['header']['tsamp'] for r in sources),'on_exposure_s':sum(r['excerpt_shape'][0]*r['header']['tsamp'] for c in acq['cadences'] for r in c['source_records'] if r['scan_index']%2==0),'full_original_checksums_verified':False},
 'unweighted_eligible_signals':sum(r['eligible'] for r in rows),'outside_declared_domain_signals':sum(not r['eligible'] for r in rows),
 'unweighted_recoveries':{a:sum(r[a] for r in rows) for a in ['new_safe','new_strict','legacy_safe','legacy_strict']},
 'native_control_burden':{a:{key:sum(c['arms'][a][key] for c in controls) for key in ['hit_count','cadence_event_count','strict_retained_events']} for a in ['new','legacy']},
 'native_burden_caution':'Native origin is unresolved. These are candidate/association counts, not transmitter counts or labeled false positives.',
 'coverage':coverage,'quadrature_max_abs_difference_over_continuous_peak':{f:{str(n):max(r[f'{n}_versus_128_max_abs_difference_over_continuous_peak'] for r in q if r['family']==f) for n in [32,64]} for f in dict.fromkeys(r['family'] for r in q)},
 'main_60_component_gate_passed':False,'scope':'Exploratory reduced finite-frame sensitivity pilot. No calibrated flux sensitivity, population completeness, main-study precision, noninferiority or confirmed origin claim.'}
v1=HERE/'results/pilot_v1'
old_rows=[json.loads(line) for line in (v1/'signal_rows.jsonl').read_text().splitlines()]
paired_checks={'same_trial_parameters':json.load(open(v1/'injection_design.json'))['trials']==json.load(open(p/'injection_design.json'))['trials'],
               'same_observational_inputs':(v1/'input_manifest.json').read_bytes()==(p/'input_manifest.json').read_bytes(),
               'same_native_control_scores_and_coverage':(v1/'native_controls.json').read_bytes()==(p/'native_controls.json').read_bytes(),
               'same_per_trial_injection_and_blind_output_metrics':(v1/'trial_metrics.jsonl').read_bytes()==(p/'trial_metrics.jsonl').read_bytes()}
for trial in {r['trial_id'] for r in rows}:
    chosen=[r for r in rows if r['trial_id']==trial]
    for arm in ['new','legacy']:
        ids=[r[arm+'_stages']['matched_cadence_event_id'] for r in chosen if r[arm+'_stages']['matched_cadence_event_id'] is not None]
        if len(set(ids))!=len(ids):raise AssertionError('Cadence event reused by physical signals')
        parent_ids=[parent for r in chosen for parent in r[arm+'_stages']['coherent_association_parent_event_ids']]
        if len(set(parent_ids))!=len(parent_ids):raise AssertionError('Local parent reused by physical signals')
checks.update(paired_checks)
result['assignment_amendment_comparison']={'checks':paired_checks,'v1_unweighted_recoveries':{a:sum(r[a] for r in old_rows) for a in ['new_safe','new_strict','legacy_safe','legacy_strict']},'v2_unweighted_recoveries':result['unweighted_recoveries'],'interpretation':'Post-search evaluator correction on the same fixed development experiment; not a new independent observing cohort or confirmatory validation.'}
result['all_checks_passed']=all(checks.values())
result['strict_retention_decisions']={a:dict(collections.Counter(r[a+'_stages']['strict_decision'] for r in rows if r[a+'_strict'])) for a in ['new','legacy']}
result['actual_legacy_cap_losses_in_represented_trial_searches']=sum(m['arm_metrics']['legacy']['candidate_cap_loss_count'] for m in metrics)
old_conflicts=[r for r in old_rows if r['new_first_loss']=='cadence_ancestry_or_assignment']
new_by_id={r['truth_id']:r for r in rows}
result['assignment_amendment_comparison']['former_conflicts']=len(old_conflicts)
result['assignment_amendment_comparison']['former_conflicts_now_retained']=sum(new_by_id[r['truth_id']]['new_safe'] for r in old_conflicts)
write(HERE/'evidence/delivery_validation.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in ['checks','quadrature_max_abs_difference_over_continuous_peak']},indent=2))
assert result['all_checks_passed'],checks
