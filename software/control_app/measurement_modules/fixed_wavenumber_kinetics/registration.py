"""Frozen host API v1 registration; widget and device imports are deferred."""
from control_app.measurement_host import API_VERSION, ModuleDescriptor
from control_app.measurement_host.naming import tab_title


def create_tabs(context):
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), title=tab_title("fixed_wavenumber_kinetics", "single")),
        make_handle(context.for_mode("dual"), title=tab_title("fixed_wavenumber_kinetics", "dual")),
    )


DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="fixed_wavenumber_kinetics",
    display_order=200,
    create_tabs=create_tabs,
)
