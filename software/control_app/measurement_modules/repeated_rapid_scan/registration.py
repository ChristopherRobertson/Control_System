"""Automatic version-one host registration; no construction-time hardware I/O."""
from control_app.measurement_host import API_VERSION, ModuleDescriptor
from control_app.measurement_host.naming import tab_title


def create_tabs(context):
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), tab_title("repeated_rapid_scan", "single")),
        make_handle(context.for_mode("dual"), tab_title("repeated_rapid_scan", "dual")),
    )


DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="repeated_rapid_scan",
    display_order=600,
    create_tabs=create_tabs,
)
