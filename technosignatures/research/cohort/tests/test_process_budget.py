from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys

from research.cohort.transport import FileTransferBudget


def test_shared_budget_reservations_are_atomic_across_processes(tmp_path):
    path = tmp_path/'ledger.json'; budget = FileTransferBudget.create(path, 10, 10)
    code = 'import sys; from research.cohort.transport import FileTransferBudget; FileTransferBudget(sys.argv[1]).reserve("source",5)'
    def one(_): return subprocess.run([sys.executable, '-c', code, str(path)], capture_output=True).returncode
    with ThreadPoolExecutor(max_workers=3) as pool: results = list(pool.map(one, range(3)))
    assert sorted(results) == [0, 0, 1] and budget.reserved == 10
    budget.cancel()
    try: budget.reserve('other', 1)
    except ValueError: pass
    else: raise AssertionError('Cancelled acquisition accepted a new reservation')
