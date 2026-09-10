"""Frozen host API v1 registration; widget and device imports are deferred."""
from control_app.measurement_host import API_VERSION, ModuleDescriptor


def create_tabs(context):
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), title="Fixed-Wavenumber Kinetics"),
        make_handle(context.for_mode("dual"), title="Dual-Detector Fixed-Wavenumber Kinetics"),
    )


DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="fixed_wavenumber_kinetics",
    display_order=200,
    create_tabs=create_tabs,
)
