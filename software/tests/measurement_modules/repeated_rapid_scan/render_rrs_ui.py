"""Render the real 1100 × 780 shell with injected data and no device I/O.

Run with PYTHONPATH=software and QT_QPA_PLATFORM=offscreen. Images and native
preview records go to tmp/rrs-overhaul unless an output directory is supplied.
"""
from dataclasses import replace
from pathlib import Path
import sys
from time import monotonic, sleep
from uuid import uuid4

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from control_app.measurement_host.ownership import HardwareCoordinator
from control_app.measurement_modules.repeated_rapid_scan.registration import DESCRIPTOR
from control_app.measurement_modules.repeated_rapid_scan.settings import example_settings
from control_app.measurement_modules.repeated_rapid_scan.simulation import SimulationAcquirer
from control_app.paths import set_save_location
from control_app.ui.contracts import blocked_handler
from control_app.ui.main_window import ControlSystemMainWindow


def render(folder):
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
        app.setFont(QFont("Segoe UI", 9))
    set_save_location(folder / "native")
    handler = blocked_handler("Rendering with injected test devices")
    handler.coordinator = HardwareCoordinator(folder / f"render-{uuid4()}.lock")
    window = ControlSystemMainWindow(handler, module_discovery=(DESCRIPTOR,))
    window.phase_scan_widget._capability_check_attempted = True
    window.dual_detector_phase_scan_widget._capability_check_attempted = True
    window.resize(1100, 780)
    window.show()

    def snapshot(panel, name):
        window.tabs.setCurrentWidget(panel)
        for _ in range(3):
            app.processEvents()
        window.workspace_scroll.verticalScrollBar().setValue(0)
        window.grab().save(str(folder / name))

    for panel, name in ((window.phase_scan_widget, "phase-scan-single-shell.png"),
                        (window.dual_detector_phase_scan_widget, "phase-scan-dual-shell.png")):
        snapshot(panel, name)
    for mode in ("single", "dual"):
        panel = next(window.tabs.widget(i) for i in range(window.tabs.count())
                     if window.tabs.widget(i).objectName() == f"repeated_rapid_scan:{mode}")
        snapshot(panel, f"rrs-{mode}-empty.png")
        settings = replace(example_settings(mode), phase_offsets_s=(0.,),
                           directions=("forward",), controls=("probe_only",), pre_scans=3, post_scans=24)
        panel.adapter.acquirer_factory = SimulationAcquirer
        panel.adapter.apply_settings(settings.to_dict())
        panel.refresh_plan()
        panel.begin("measurement")
        deadline = monotonic() + 45
        while panel.command_running():
            app.processEvents()
            sleep(.005)
            if monotonic() > deadline:
                panel.request_abort("Preview timeout")
                raise RuntimeError("Preview timed out")
        if panel.result is None:
            raise RuntimeError(panel.status.text())
        panel.set_status("Preview with injected test data")
        snapshot(panel, f"rrs-{mode}-result.png")
        panel.plots.view.setCurrentIndex(1)
        snapshot(panel, f"rrs-{mode}-kinetics.png")
        assert window.workspace_scroll.verticalScrollBar().maximum() == 0
        print(f"{mode}: {window.width()}x{window.height()}, plots {panel.plots.width()}x{panel.plots.height()}")
    window.hide()
    window.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    render(sys.argv[1] if len(sys.argv) > 1 else "tmp/rrs-overhaul")
