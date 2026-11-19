"""Integration tests require actual original-archive scientific excerpts."""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from research.pilot.observations import HERE,load_release,inspect_cadence,digest
from research.pilot.archive_excerpts import run as extract


@pytest.fixture(scope="module")
def release():return load_release()[0]


@pytest.mark.parametrize("scan",range(6))
def test_every_raw_archive_scientific_sample_matches_release(release,scan):
    path=HERE/f"data/archive_excerpts/scan_{scan}.npz"
    assert path.exists(),"Complete archive extraction before claiming source validation"
    _,powers,freq,_=inspect_cadence("mlc1",release["mlc1"])
    with np.load(path,allow_pickle=False) as data:
        np.testing.assert_array_equal(data["power_ascending"],powers[scan])
        np.testing.assert_array_equal(data["frequency_hz"],freq)
        np.testing.assert_array_equal(data["time_s"],np.arange(16)*float(release["mlc1"]["all_header"][scan]["tsamp"]))
    record=json.loads((HERE/"evidence/archive_excerpts.json").read_text())["records"][scan]
    source=record["header"]
    assert abs(source['src_raj']*15-float(release['mlc1']['all_header'][scan]['src_raj'].degree))*3600<1
    assert abs(source['src_dej']-float(release['mlc1']['all_header'][scan]['src_dej'].degree))*3600<1


def test_original_source_validation_scope_and_budgets():
    path=HERE/"evidence/archive_excerpts.json"
    assert path.exists(),"Online source extraction evidence required"
    result=json.loads(path.read_text())
    assert result["all_six_scientific_excerpts_bitwise_match"]
    assert result["all_stored_time_samples_acquired_for_selected_frequency_slice"]
    assert not result["full_original_bandwidth_acquired"]
    assert not result["representative_cohort_gate_passed"]
    assert len(result["records"])==6
    for record in result["records"]:
        assert record["range_bytes_accessed"]<=record["range_byte_budget"]
        assert all(record["header_checks"].values())
        assert not record["whole_original_file_checksum_verified"]
        assert digest(HERE/f"data/archive_excerpts/scan_{record['scan_index']}.npz")==record["excerpt_npz_sha256"]


def test_source_extraction_reproduces_with_http_disabled(monkeypatch):
    def no_network(*args,**kwargs):raise AssertionError("Offline extraction attempted HTTP")
    monkeypatch.setattr("research.pilot.range_access.HTTPRangeSource.__call__",no_network)
    result=extract(offline=True)
    assert result["all_six_scientific_excerpts_bitwise_match"]
    assert result["new_network_bytes"]==0
