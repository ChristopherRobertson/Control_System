"""Lazy v1 host registration; discovery performs no device or widget work."""
from control_app.measurement_host import API_VERSION, ModuleDescriptor
from control_app.measurement_host.naming import tab_title


def create_tabs(context):
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), title=tab_title("microsecond_stroboscopy", "single")),
        make_handle(context.for_mode("dual"), title=tab_title("microsecond_stroboscopy", "dual")),
    )


DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="microsecond_stroboscopy",
    display_order=400,
    create_tabs=create_tabs,
)
