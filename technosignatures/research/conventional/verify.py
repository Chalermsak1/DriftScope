"""Repeat all development experiments and require scientific JSON/hash equality."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from research.pilot.run import preserved_original
from .run import HERE, ROOT, run, write


def verify(reference, release_path, tests_path, output):
    reference = Path(reference)
    suites = list(ET.parse(tests_path).getroot().iter('testsuite'))
    tests = {k: sum(int(s.get(k, 0)) for s in suites) for k in ['tests', 'failures', 'errors', 'skipped']}
    if tests['tests'] < 1 or any(tests[k] for k in ['failures', 'errors', 'skipped']):
        raise AssertionError('A passing complete test record is required before final verification')
    reference_source = json.loads((reference/'source_manifest.json').read_text())
    for relative, entry in reference_source.items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() != entry['sha256']:
            raise AssertionError(f'Source changed after the reference run: {relative}; rerun the experiment')
    with tempfile.TemporaryDirectory(prefix='driftscope-conventional-repeat-') as temporary:
        repeat = Path(temporary)/'repeat'
        run(repeat, Path(release_path), reference/'execution_config.json')
        checks = {}
        for path in sorted(reference.glob('*.json')):
            if path.name == 'runtime.json': continue
            checks[path.name] = json.loads(path.read_text()) == json.loads((repeat/path.name).read_text())
    result = {'all_checks_passed': all(checks.values()), 'tests': tests, 'repeat_comparisons': checks,
              'repeat_check_count': len(checks), 'preservation': preserved_original(),
              'comparison_scope': 'All stable scientific JSON, including exact score/power-array SHA-256 values, in the same installed environment. Runtime, PNG bytes, and fresh network availability are outside this guarantee.',
              'source_hashes_verified_before_repeat': True, 'representative_cohort_gate_passed': False,
              'locked_test_accessed': False, 'llm_introduced': False}
    write(Path(output), result)
    if not result['all_checks_passed']: raise AssertionError('Numerical development repeat differs; see comparison ledger')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, default=HERE/'results/development_v2')
    p.add_argument('--release-path', type=Path, required=True)
    p.add_argument('--tests', type=Path, default=HERE/'evidence/tests_final.xml')
    p.add_argument('--output', type=Path, default=HERE/'evidence/verification.json')
    args = p.parse_args()
    result = verify(args.reference, args.release_path, args.tests, args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
