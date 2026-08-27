"""Run the shared focused electrical-sweep implementation for PT-01 Step 8."""

from __future__ import annotations

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "T1-01" / "acquire_step.py"
SPEC = importlib.util.spec_from_file_location("retained_t1_acquire_step", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load retained acquisition implementation: {SOURCE}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

# Reuse the retained acquisition mechanics without modifying completed T1-01.
MODULE.HERE = HERE
MODULE.STEPS = {"8": "setup_1_fire_to_process_trigger"}
MODULE.POLARITIES = {"8": ("negative", "negative")}

if __name__ == "__main__":
    raise SystemExit(MODULE.main())
