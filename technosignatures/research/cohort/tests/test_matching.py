from types import SimpleNamespace
import numpy as np
import pytest
from research.cohort.matching import cadence_matches,local_matches
from research.conventional.events import match_tracks


def fixture():
    scan=SimpleNamespace(scan_id='synthetic_on',role='ON',df=1.,time_s=np.arange(4.),dt=1.)
    cadence=SimpleNamespace(scans=[scan],offsets_s=[0.])
    hits=[{'hit_id':'h_good','scan_id':scan.scan_id,'start_frequency_hz':100.,'drift_hz_per_s':0.},
          {'hit_id':'h_bad','scan_id':scan.scan_id,'start_frequency_hz':103.5,'drift_hz_per_s':0.}]
    events=[{**h,'event_id':'e_'+h['hit_id'],'representative_hit_id':h['hit_id']} for h in hits]
    final=[{'cadence_event_id':'global_closer_but_incoherent','start_frequency_hz':100.7,'drift_hz_per_s':0.,'member_on_event_ids':['e_h_bad']},
           {'cadence_event_id':'global_coherent','start_frequency_hz':101.,'drift_hz_per_s':0.,'member_on_event_ids':['e_h_good']}]
    processed={'searches':{scan.scan_id:SimpleNamespace(hits=hits)},'grouped':{scan.scan_id:{'events':events}},'cadence':{'events':final}}
    truths=[{'truth_id':'truth_0','start_frequency_hz':100.,'drift_hz_per_s':0.}]
    return cadence,processed,truths,hits,events


def test_compatible_ancestry_is_selected_before_minimum_global_error():
    c,p,t,h,e=fixture(); times=c.scans[0].time_s+.5
    assert match_tracks(t,p['cadence']['events'],times,1.,id_key='cadence_event_id')[0]['matched_id']=='global_closer_but_incoherent'
    matches,reservations=cadence_matches(t,c,p)
    assert matches[0]['matched_id']=='global_coherent'
    assert matches[0]['unconstrained_compatible_event_count']==2 and matches[0]['ancestry_feasible_event_count']==1
    local=local_matches(t,h,e,times,1.,reservations['synthetic_on'])
    assert local['events'][0]['matched_id']=='e_h_good' and local['hits'][0]['matched_id']=='h_good'


def test_two_truths_cannot_reuse_one_cadence_event_or_its_local_parent():
    c,p,t,h,e=fixture(); p['cadence']['events']=p['cadence']['events'][1:]
    t.append({**t[0],'truth_id':'truth_1'})
    matches,reservations=cadence_matches(t,c,p)
    assert sum(m['matched_id'] is not None for m in matches)==1
    local=local_matches(t,h,e,c.scans[0].time_s+.5,1.,reservations['synthetic_on'])
    assert sum(m['matched_id'] is not None for m in local['events'])==1
    assert len({m['matched_id'] for m in local['hits'] if m['matched_id']})==sum(m['matched_id'] is not None for m in local['hits'])


def test_no_active_samples_cannot_get_a_real_match():
    c,p,t,h,e=fixture(); t[0]['active_intervals_s']=[[10.,20.]]
    matches,reservations=cadence_matches(t,c,p)
    assert matches[0]['matched_id'] is None and not reservations['synthetic_on']


def test_missing_or_reused_parent_is_a_structural_error():
    c,p,t,h,e=fixture(); p['cadence']['events'][0]['member_on_event_ids']=['missing']
    with pytest.raises(ValueError,match='missing local-event ancestry'):cadence_matches(t,c,p)
    c,p,t,h,e=fixture(); p['cadence']['events'][0]['member_on_event_ids']=['e_h_good']
    with pytest.raises(ValueError,match='two cadence events'):cadence_matches(t,c,p)


def test_group_metadata_cannot_hide_an_incompatible_actual_hit():
    c,p,t,h,e=fixture()
    p['searches']['synthetic_on'].hits[0]['start_frequency_hz']=200.
    matches,reservations=cadence_matches(t,c,p)
    assert matches[0]['matched_id'] is None and not reservations['synthetic_on']
