"""Lazy v1 host registration; discovery performs no device or widget work."""
from control_app.measurement_host import API_VERSION, ModuleDescriptor


def create_tabs(context):
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), title="Microsecond Stroboscopy"),
        make_handle(context.for_mode("dual"), title="Dual-Detector Microsecond Stroboscopy"),
    )


DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="microsecond_stroboscopy",
    display_order=140,
    create_tabs=create_tabs,
)
