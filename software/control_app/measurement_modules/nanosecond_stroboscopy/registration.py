"""Frozen host-v1 registration; constructing tabs performs no device access."""
from control_app.measurement_host import API_VERSION, ModuleDescriptor
from control_app.measurement_host.naming import tab_title


def create_tabs(context):
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), title=tab_title("nanosecond_stroboscopy", "single")),
        make_handle(context.for_mode("dual"), title=tab_title("nanosecond_stroboscopy", "dual")),
    )


DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="nanosecond_stroboscopy",
    display_order=300,
    create_tabs=create_tabs,
)
