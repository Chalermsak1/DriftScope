import importlib.util
from pathlib import Path
import subprocess


def test_audit_checks_staged_content_history_and_refs(tmp_path):
    path = Path(__file__).resolve().parents[4]/'scripts/publication_audit.py'
    spec = importlib.util.spec_from_file_location('publication_audit', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    def git(*args): subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    git('init', '-q'); git('config', 'user.name', 'Unit Test'); git('config', 'user.email', 'unit@example.invalid')
    f = tmp_path/'module.txt'; f.write_text('allowed scientific implementation')
    git('add', 'module.txt'); git('commit', '-qm', 'Scientific fixture')
    assert module.audit(tmp_path, ['unwanted_marker'])['passed']
    f.write_text('Unwanted_Marker'); git('add', 'module.txt')
    assert not module.audit(tmp_path, ['unwanted_marker'])['passed']
    git('commit', '-qm', 'Fixture containing excluded marker'); f.write_text('clean'); git('add', 'module.txt'); git('commit', '-qm', 'Clean current file')
    assert not module.audit(tmp_path, ['unwanted_marker'])['passed']
