"""Hidden optional pages cannot enlarge the established Phase Scan workspace."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget

from control_app.measurement_host import ModuleDescriptor, TabHandle
from control_app.ui.main_window import ControlSystemMainWindow


class OversizedPage(QWidget):
    state_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        policy = QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        policy.setHorizontalStretch(2)
        policy.setVerticalStretch(3)
        self.setSizePolicy(policy)

    def minimumSizeHint(self):
        return QSize(1700, 1900)

    def sizeHint(self):
        return QSize(1800, 2000)


def oversized_pair(context):
    handles = []
    for mode in ("single", "dual"):
        scoped = context.for_mode(mode)
        page = OversizedPage()
        handles.append(TabHandle(scoped.instance_id, f"Oversized {mode}", page,
                                 lambda: False, lambda: (), lambda reason: None,
                                 lambda path: None, lambda change: None, page.state_changed))
    return handles


def settle(app):
    # LayoutRequest and subsequent scroll-area geometry updates use queued events.
    for _ in range(8):
        app.processEvents()


@pytest.mark.parametrize("legacy_index", (0, 1), ids=("single_phase_scan", "dual_phase_scan"))
def test_hidden_optional_pages_preserve_legacy_geometry_and_selected_native_size(legacy_index):
    app = QApplication.instance() or QApplication([])
    descriptor = ModuleDescriptor(1, "oversized_measurement", 1, oversized_pair)
    legacy = ControlSystemMainWindow(module_discovery=())
    integrated = ControlSystemMainWindow(module_discovery=(descriptor,))
    try:
        for window in (legacy, integrated):
            window.resize(1100, 780)
            window.tabs.setCurrentIndex(legacy_index)
            window.show()
        settle(app)
        baseline_hint = legacy.tabs.minimumSizeHint()
        baseline_phase = legacy.tabs.widget(legacy_index).size()
        phase_page = integrated.tabs.widget(legacy_index)
        legacy_policies = [QSizePolicy(legacy.tabs.widget(i).sizePolicy()) for i in range(legacy.tabs.count())]
        assert integrated.tabs.minimumSizeHint() == baseline_hint
        assert phase_page.size() == baseline_phase
        optional = [handle.widget for handle in integrated.measurement_lifecycle.handles[2:]]
        expected = QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        expected.setHorizontalStretch(2)
        expected.setVerticalStretch(3)
        for page in optional:
            assert page.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
            assert page.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Ignored
            integrated.tabs.setCurrentWidget(page)
            settle(app)
            assert page.sizePolicy() == expected
            assert integrated.tabs.minimumSizeHint().height() >= page.minimumSizeHint().height()
            assert integrated.tabs.minimumSizeHint().width() >= page.minimumSizeHint().width()
            assert integrated.workspace_scroll.verticalScrollBar().maximum() > 0
            assert integrated.workspace_scroll.horizontalScrollBar().maximum() > 0
            integrated.tabs.setCurrentWidget(phase_page)
            settle(app)
            assert integrated.tabs.minimumSizeHint() == baseline_hint
            assert phase_page.size() == baseline_phase
            assert page.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
            assert page.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Ignored
        # Existing tabs retain their policies regardless of feature navigation.
        integrated_legacy = [integrated.phase_scan_widget, integrated.dual_detector_phase_scan_widget,
                             integrated.mircat_widget, integrated.t660_widget, integrated.ndyag_widget,
                             integrated.iris_widget, integrated.scan_plotter_widget]
        assert [widget.sizePolicy() for widget in integrated_legacy] == legacy_policies
    finally:
        legacy.deleteLater()
        integrated.deleteLater()
        settle(app)
