"""Make the source-layout package importable without an editable install."""

from __future__ import annotations

from pathlib import Path
import sys


SOFTWARE_ROOT = Path(__file__).resolve().parents[1]
if str(SOFTWARE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOFTWARE_ROOT))
