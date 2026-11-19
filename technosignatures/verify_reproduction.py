"""Rerun the complete pipeline and compare every numerical/scientific artifact."""
import json
from pathlib import Path

import numpy as np
import pipeline as p


def main():
    reference = p.ROOT / "results" / "run_001"
    repeated = p.ROOT / "results" / "reproduction"
    if not (reference / "results.json").exists():
        raise FileNotFoundError("Run pipeline.py before reproduction verification")
    p.run(output=repeated)
    checks = {}
    for name in ["before.npz", "after.npz", "search_before.npz", "search_after.npz"]:
        with np.load(reference / name) as first, np.load(repeated / name) as second:
            checks[name] = set(first.files) == set(second.files) and all(np.array_equal(first[k], second[k]) for k in first.files)
    checks["injected_signal.npy"] = np.array_equal(np.load(reference / "injected_signal.npy"), np.load(repeated / "injected_signal.npy"))
    for name in ["results.json", "config.json", "candidates_before.csv", "candidates_after.csv"]:
        checks[name] = (reference / name).read_bytes() == (repeated / name).read_bytes()
    summary = {
        "all_checks_passed": all(checks.values()),
        "comparison": "bitwise array equality and byte-for-byte results/config/candidate equality in the same installed environment",
        "checks": checks,
        "excluded": "Figures and environment descriptions are not required to be byte-identical across platforms",
    }
    p.write_json(p.ROOT / "results" / "reproducibility.json", summary)
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
