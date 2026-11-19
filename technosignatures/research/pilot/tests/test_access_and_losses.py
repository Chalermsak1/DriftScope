"""Scientific tests for observational integrity and honest loss accounting."""
import copy
import io
import json
import pickle
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import pipeline as legacy
from research.pilot.observations import HERE, RestrictedReleaseUnpickler, inspect_cadence, load_release, digest
from research.pilot.accounting import coverage, traced_search, survival_record, path_error
from research.pilot.run import gaussian_fixture, preserved_original


@pytest.fixture(scope="module")
def release():
    return load_release()[0]


@pytest.fixture(scope="module")
def config():
    return json.loads((HERE/"configs/audit.json").read_text())


@pytest.fixture(scope="module")
def original():
    return json.loads((ROOT/"config.json").read_text())


@pytest.mark.parametrize("key",[f"mlc{i}" for i in range(1,9)])
def test_real_release_six_scan_integrity(release,key):
    meta,data,freq,starts=inspect_cadence(key,release[key])
    assert meta["passes_structural_cadence_checks"], meta["checks"]
    assert data.shape==(6,16,4096)
    assert np.all(np.diff(freq)>0)
    assert np.all(np.diff(starts)>0)
    assert all(s["role"]==("ON" if i%2==0 else "OFF") for i,s in enumerate(meta["scans"]))
    np.testing.assert_array_equal(data,release[key]["data"][:,:,0,::-1])
    assert meta["represented_exposure_s"] < meta["elapsed_span_s"]


def test_source_integrity_rejects_changed_payload(tmp_path):
    path=tmp_path/"invalid.pkl"
    path.write_bytes(b"not the pinned observation release")
    with pytest.raises(ValueError,match="checksum"):
        load_release(path)


def test_unapproved_pickle_constructor_rejected():
    # Built-in complex is innocuous but unapproved: proves no generic globals.
    with pytest.raises(pickle.UnpicklingError,match="Unapproved global"):
        RestrictedReleaseUnpickler(io.BytesIO(pickle.dumps(complex(1,2)))).load()


def test_reordered_scans_rejected_by_cadence_checks(release):
    changed=copy.deepcopy(release["mlc1"])
    changed["all_header"][1],changed["all_header"][2]=changed["all_header"][2],changed["all_header"][1]
    meta,*_=inspect_cadence("reordered",changed)
    assert not meta["passes_structural_cadence_checks"]
    assert not meta["checks"]["chronological_order"]


def test_off_pointing_on_source_is_not_accepted(release):
    changed=copy.deepcopy(release["mlc1"])
    for key in ["source_name","src_raj","src_dej"]:
        changed["all_header"][1][key]=changed["all_header"][0][key]
    meta,*_=inspect_cadence("false_off",changed)
    assert not meta["checks"]["off_coordinates_distinct_over_1_arcmin"]
    assert not meta["checks"]["off_target_names_differ"]


def test_frequency_bound_shape_mismatch_recorded(release):
    changed=copy.deepcopy(release["mlc1"])
    changed["freq"][1]+=1e-6
    meta,*_=inspect_cadence("bad_frequency_bounds",changed)
    assert not meta["checks"]["frequency_interval_matches_cutout_shape"]


def test_original_coverage_reproduced_exactly(original):
    data,freq,times,_=legacy.load_observation(ROOT/original["dataset"]["path"],original["dataset"])
    result,trace,c=traced_search(data,freq,times,original["detector"])
    assert c["legacy_start_channel_count"]==764
    assert c["legacy_searched_track_trials"]==390404
    assert c["legacy_start_channel_fraction"]==0.74609375
    assert c["valid_discrete_tracks_omitted_by_common_guard"]>0
    assert trace["summary"]["legacy_output_exactly_reproduced"]
    assert trace["summary"]["candidates_lost_to_cap"]==0


def test_per_drift_coverage_matches_brute_force(original):
    cfg={**original["detector"],"max_abs_drift_hz_per_s":1.0}
    times=np.arange(4,dtype=float)
    c=coverage(32,times,1.0,cfg)
    total=0
    for row in c["per_drift"]:
        shifts=np.rint(row["drift_hz_per_s"]*times).astype(int)
        valid=[]
        for start in range(32):
            positions=np.array([start+shift+box for shift in shifts for box in [-1,0,1]])
            if np.all((positions>=0)&(positions<32)):valid.append(start)
        assert len(valid)==row["valid_start_count"]
        total+=len(valid)
    assert total==c["valid_discrete_track_trials_over_full_input"]


def test_cap_loss_exposed_in_seeded_80_line_case(config,original):
    before,after,freq,times,truths,cfg=gaussian_fixture(config["fully_synthetic_crowded_fixture"],original["detector"])
    control,*_=traced_search(before,freq,times,cfg)
    result,trace,_=traced_search(after,freq,times,cfg)
    # Eighty physical tracks can yield more than eighty search maxima.
    assert trace["summary"]["uncapped_nms_candidates"]>=80
    assert trace["summary"]["retained_candidates"]==50
    assert trace["summary"]["candidates_lost_to_cap"]==trace["summary"]["uncapped_nms_candidates"]-50
    records=[survival_record(t["id"],t,freq,times,cfg,control,result,trace,"fully_synthetic") for t in truths]
    assert all(r["matching_uncapped_nms"]>=1 for r in records)
    assert sum(r["first_loss_category"]=="catalogue_truncation_loss" for r in records)==30
    assert sum(r["conservative_attributable_recovery"] for r in records)==50


def test_trace_matches_original_with_smaller_cap(config,original):
    _,after,freq,times,_,cfg=gaussian_fixture(config["fully_synthetic_crowded_fixture"],original["detector"])
    cfg={**cfg,"max_candidates":7}
    result,trace,_=traced_search(after,freq,times,cfg)
    assert len(result["candidates"])==7
    assert trace["summary"]["candidates_lost_to_cap"]==trace["summary"]["uncapped_nms_candidates"]-7
    assert trace["summary"]["candidates_lost_to_cap"]>=73
    assert trace["retained_candidates"][-1]["uncapped_rank"]==7


def test_common_guard_loss_is_not_threshold_loss(config,original):
    before,freq,times,_=legacy.load_observation(ROOT/original["dataset"]["path"],original["dataset"])
    control,*_=traced_search(before,freq,times,original["detector"])
    injection={**original["injection"],"start_channel_ascending":64}
    after,_,truth=legacy.inject_signal(before,freq,times,injection)
    result,trace,_=traced_search(after,freq,times,original["detector"])
    record=survival_record("guard",truth,freq,times,original["detector"],control,result,trace,"synthetic_in_real")
    assert record["discrete_signal_path_supported"]
    assert not record["common_start_searchable"]
    assert record["first_loss_category"]=="valid_path_omitted_by_common_guard"
    assert next(s for s in record["stages"] if s["stage"]=="score_threshold")["status"]=="not_reached"


def test_saved_source_overlap_is_not_counted_as_independent():
    p=HERE/"results/milestone_001/access_summary.json"
    if not p.exists():pytest.fail("Run research.pilot.run before saved evidence tests")
    s=json.loads(p.read_text())
    assert s["released_cutouts"]==8
    assert s["distinct_scan_sequence_count"]==6
    assert len(s["conservative_target_or_utc_day_proxy_groups"])==5
    assert not s["representative_cohort_gate_passed"]


def test_global_chirp_keeps_actual_scan_gaps_and_off_arrays_unchanged():
    p=HERE/"results/milestone_001"
    with np.load(p/"mlc1_one_global_injected_track.npz",allow_pickle=False) as a:
        before,after,delta=a["before"],a["after"],a["added_power"]
        starts,dt,freq=a["scan_start_elapsed_s"],a["integration_s"],a["frequency_hz"]
        np.testing.assert_array_equal(before[1::2],after[1::2])
        np.testing.assert_array_equal(delta[1::2],np.zeros_like(delta[1::2]))
        np.testing.assert_allclose(after-before,delta,rtol=1e-7,atol=float(delta.max())*1e-7)
        df=legacy.channel_spacing(freq)
        for scan in [0,2,4]:
            expected=800+0.5*(starts[scan]+np.arange(16)*dt[scan])/df
            observed=np.argmax(delta[scan],axis=1)
            assert np.max(np.abs(observed-expected))<=0.5+1e-8
        assert np.argmax(delta[4,0])-np.argmax(delta[0,0])>200
    s=json.loads((p/"cadence_injection_survival.json").read_text())
    assert s["signal_count"]==1 and s["scan_pieces"]==3
    assert s["summary"]["conservatively_attributed_retained"]==3


def test_later_stages_never_marked_pass_without_execution():
    p=HERE/"results/milestone_001/fixture_survival.json"
    s=json.loads(p.read_text())
    for record in s["records"]:
        for stage in record["stages"]:
            if stage["stage"] in ["event_grouping","cadence_filtering","triage"]:
                assert stage["status"]=="not_applied"
                assert stage["observed_fact"] is None


def test_manifest_integrity_and_original_preservation():
    assert preserved_original()["all_preserved"]
    p=HERE/"results/milestone_001"
    for name,entry in json.loads((p/"artifact_manifest.json").read_text()).items():
        assert digest(p/name)==entry["sha256"]
