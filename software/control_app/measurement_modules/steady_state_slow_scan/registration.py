"""Lazy discovery of the two independently owned steady-state spectra tabs."""

from control_app.measurement_host import API_VERSION, ModuleDescriptor


def create_tabs(context):
    from .widgets import make_handle

    return (
        make_handle(context.for_mode("single"), title="Slow Scan"),
        make_handle(context.for_mode("dual"), title="Dual-Detector Slow Scan"),
    )


DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="steady_state_slow_scan",
    display_order=100,
    create_tabs=create_tabs,
)
