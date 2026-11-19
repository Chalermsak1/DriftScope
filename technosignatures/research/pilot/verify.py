"""Repeat the milestone and verify all stable JSON and every numeric array."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

from .observations import HERE,digest
from .run import run,preserved_original


def main():
    reference=HERE/"results/milestone_001"
    repeated=HERE/"results/reproduction"
    run(repeated)
    checks={}
    for path in sorted(reference.glob("*.json")):
        if path.name in ["profile.json","artifact_manifest.json"]:continue
        a=json.loads(path.read_text());b=json.loads((repeated/path.name).read_text())
        if path.name=="access_summary.json":
            a.pop("metadata_and_export_elapsed_s",None);b.pop("metadata_and_export_elapsed_s",None)
        checks[path.name]=(a==b)
    for path in sorted(reference.glob("*.npz")):
        with np.load(path,allow_pickle=False) as a,np.load(repeated/path.name,allow_pickle=False) as b:
            checks[path.name]=a.files==b.files and all(np.array_equal(a[k],b[k]) for k in a.files)
    test_path=HERE/"evidence/tests.xml"
    if not test_path.exists():raise FileNotFoundError("Run pytest with the documented XML path before verification")
    suites=list(ET.parse(test_path).getroot().iter("testsuite"))
    tests={k:sum(int(s.get(k,0)) for s in suites) for k in ["tests","failures","errors","skipped"]}
    tests_passed=tests["tests"]>0 and tests["failures"]==tests["errors"]==tests["skipped"]==0
    original=preserved_original()
    result={
        "all_checks_passed":all(checks.values()) and tests_passed and original["all_preserved"],
        "tests":tests,"repeat_comparisons":checks,"repeat_check_count":len(checks),
        "comparison_scope":"All stable scientific JSON and exact equality of all NPZ arrays in same installed environment; runtime, transfer timing, image bytes and manifest bytes are not required identical.",
        "preservation":original,
        "source_code_sha256":{p.name:digest(p) for p in sorted(HERE.glob("*.py"))},
        "test_code_sha256":{p.name:digest(p) for p in sorted((HERE/"tests").glob("test_*.py"))},
        "representative_cohort_gate_passed":False,
        "event_grouping_cadence_filtering_and_llm_validation_complete":False,
    }
    (HERE/"evidence/verification.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!='repeat_comparisons'},indent=2))
    raise SystemExit(0 if result["all_checks_passed"] else 1)


if __name__=="__main__":main()
