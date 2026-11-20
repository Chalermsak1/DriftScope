"""Audit staged files, reachable history and refs against user-supplied markers."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def git(repo, *args, required=True):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if required and result.returncode: raise RuntimeError(result.stderr.decode(errors='replace'))
    return result.stdout


def audit(repo, markers, working_tree=False):
    repo = Path(repo).resolve()
    patterns = [m.encode().lower() for m in markers]
    if not patterns or any(not p for p in patterns): raise ValueError('Nonempty excluded markers required')
    failures = []; scanned = 0
    def check(label, data):
        nonlocal scanned
        scanned += 1
        if any(p in data.lower() for p in patterns): failures.append(label)
    if working_tree:
        paths = git(repo, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')
    else:
        paths = git(repo, 'ls-files', '-z', '--cached').split(b'\0')
    for raw in paths:
        if not raw: continue
        name = raw.decode(); check('file_path:'+name, raw)
        content = (repo/name).read_bytes() if working_tree else git(repo, 'show', ':'+name)
        check('file_content:'+name, content)
    check('branch_and_tag_refs', git(repo, 'for-each-ref', '--format=%(refname)'))
    check('commit_authorship_and_messages', git(repo, 'log', '--all', '--format=fuller', required=False))
    objects = git(repo, 'rev-list', '--objects', '--all', required=False).splitlines()
    for line in objects:
        check('historical_object_path', line)
        object_id = line.split(b' ', 1)[0].decode()
        if git(repo, 'cat-file', '-t', object_id).strip() == b'blob':
            check('historical_blob:'+object_id, git(repo, 'cat-file', 'blob', object_id))
    return {'passed': not failures, 'checks_performed': scanned,
            'file_count': len([p for p in paths if p]), 'working_tree_including_untracked': working_tree,
            'marker_sha256': [hashlib.sha256(p).hexdigest() for p in patterns],
            'failure_locations': failures, 'scope': 'Files selected by Git ignore/index rules, their paths, all reachable Git blob history, commit metadata, and published refs; local reflogs/private ignored files are not uploaded.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--excluded-marker', action='append', required=True)
    p.add_argument('--working-tree', action='store_true')
    p.add_argument('--output', type=Path)
    a = p.parse_args(); result = audit(a.repository, a.excluded_marker, a.working_tree)
    text = json.dumps(result, indent=2, sort_keys=True)+'\n'
    if a.output: a.output.write_text(text)
    print(text)
    if not result['passed']: raise SystemExit(1)


if __name__ == '__main__': main()
