"""Declarative registration against the frozen measurement host API."""
from control_app.measurement_host import API_VERSION, ModuleDescriptor
from control_app.measurement_host.naming import tab_title


def create_tabs(context):
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), title=tab_title("single_pump_scan_burst", "single")),
        make_handle(context.for_mode("dual"), title=tab_title("single_pump_scan_burst", "dual")),
    )


DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="single_pump_scan_burst",
    display_order=500,
    create_tabs=create_tabs,
)
