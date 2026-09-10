"""Automatic version-one host registration; no construction-time hardware I/O."""
from control_app.measurement_host import API_VERSION, ModuleDescriptor


def create_tabs(context):
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), "Repeated Rapid-Scan Phase Delay"),
        make_handle(context.for_mode("dual"), "Dual-Detector Repeated Rapid-Scan Phase Delay"),
    )


DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="repeated_rapid_scan",
    display_order=500,
    create_tabs=create_tabs,
)
