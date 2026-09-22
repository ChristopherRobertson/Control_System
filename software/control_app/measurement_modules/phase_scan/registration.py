"""Registration of the established Phase Scan pair without changing its behavior."""
from __future__ import annotations

from control_app.measurement_host.contracts import TabHandle, ModuleDescriptor
from control_app.measurement_host.naming import tab_title


class LegacyPhasePreferences:
    """Read-through migration of exactly two old keys into a scoped namespace.

    Old values are retained for provenance/older software. All new writes use
    the instance's measurements/phase_scan/<mode>/v1 namespace. Widgets never
    receive the application-wide settings object.
    """

    def __init__(self, scoped, legacy_backend, *, dual=False):
        key = "dual_detector_phase_scan" if dual else "regular_phase_scan"
        self._mapping = {key: "settings", key + "_hf2_choices": "hf2_choices"}
        self._scoped = scoped
        self._legacy_backend = legacy_backend

    def value(self, key, default=None):
        target = self._mapping[key]
        sentinel = "__measurement_host_missing_preference__"
        value = self._scoped.value(target, sentinel)
        if value == sentinel:
            if self._legacy_backend is not None:
                value = self._legacy_backend.value(key, sentinel)
            if value != sentinel:
                self._scoped.setValue(target, value)
        return default if value == sentinel else value

    def setValue(self, key, value):  # noqa: N802 - QSettings compatibility
        self._scoped.setValue(self._mapping[key], value)


def create_phase_scan_tabs(context, *, single_runner=None, dual_runner=None,
                           legacy_preferences=None, before_start=None):
    from .widgets import PhaseScanWidget

    handles = []
    for mode, title, runner in (
        ("single", tab_title("phase_scan", "single"), single_runner),
        ("dual", tab_title("phase_scan", "dual"), dual_runner),
    ):
        scoped = context.for_mode(mode)
        widget = PhaseScanWidget(
            runner=runner, dual_detector=mode == "dual",
            before_start=(lambda r=runner, instance_id=scoped.instance_id: before_start(
                hardware=bool(getattr(r, "hardware_access", False)), instance_id=instance_id))
                         if before_start is not None else None,
            save_root_provider=scoped.save_root,
            preferences=LegacyPhasePreferences(scoped.preferences, legacy_preferences,
                                               dual=mode == "dual"),
        )
        handles.append(TabHandle(
            instance_id=scoped.instance_id, title=title, widget=widget,
            command_running=widget.command_running, close_blockers=widget.close_blockers,
            request_abort=widget.request_abort, output_location_changed=widget.output_location_changed,
            instrument_state_changed=widget.instrument_state_changed,
            state_changed=widget.busy_changed,
        ))
    return tuple(handles)


DESCRIPTOR = ModuleDescriptor(
    api_version=1, experiment_id="phase_scan", display_order=700,
    create_tabs=create_phase_scan_tabs,
)
