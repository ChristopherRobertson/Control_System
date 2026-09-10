"""Declarative registration against the frozen measurement host API."""
from control_app.measurement_host import API_VERSION, ModuleDescriptor


def create_tabs(context):
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), title="Single-Pump Scan Bursts"),
        make_handle(context.for_mode("dual"), title="Dual-Detector Single-Pump Scan Bursts"),
    )


DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="single_pump_scan_burst",
    display_order=600,
    create_tabs=create_tabs,
)
