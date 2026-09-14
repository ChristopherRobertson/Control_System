"""Make the source-layout package importable without an editable install."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


SOFTWARE_ROOT = Path(__file__).resolve().parents[1]
if str(SOFTWARE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOFTWARE_ROOT))


@pytest.fixture(autouse=True)
def complete_pending_qt_deletions():
    """Finish deleteLater cleanup without requiring a running QApplication loop.

    processEvents does not deliver deferred deletes by itself. A shell left
    queued for deletion otherwise keeps its timers alive in subsequent tests.
    """
    yield
    qt_core = sys.modules.get("PySide6.QtCore")
    if qt_core is not None and qt_core.QCoreApplication.instance() is not None:
        qt_core.QCoreApplication.sendPostedEvents(None, qt_core.QEvent.Type.DeferredDelete)
