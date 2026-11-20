# Execution record notes

The local sequential orchestration wrapper initially used `pilot_execution.log` for both its outer progress stream and its full-pilot subprocess stream. Opening the subprocess destination truncated the outer console log, and later progress messages could overwrite some console bytes. The retained file is explicitly named `pilot_execution_mixed_stream.log`; it is not an authoritative scientific result ledger.

This affected console logging only. Source files, original observations, immutable input arrays, atomic per-trial checkpoints, JSONL signal/metric ledgers and final scientific JSON were separate files. A fresh full execution reproduced all scientific comparisons and all 1,152 trial checkpoints exactly, as recorded in `repeat_verification.json`. The public CLI/reproduction commands do not use the colliding wrapper. Later orchestration uses a distinct outer log name.
