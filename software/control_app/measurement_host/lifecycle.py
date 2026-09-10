"""Application lifecycle fan-out; scientific state remains inside each handle."""
from __future__ import annotations

from pathlib import Path
from threading import RLock


class MeasurementLifecycle:
    """Failure-isolated lifecycle routing for every installed measurement pair.

    Cancellation follows the coordinator's actual hardware owner. Busy offline
    workers still block app close, but never receive a hardware emergency abort.
    Observations and callback errors remain available to the shell for display.
    No callback is interpreted as proof of physical safe idle.
    """

    def __init__(self, ownership, *, before_start=None):
        self.ownership = ownership
        self._before_start = before_start or (lambda instance_id: None)
        self._handles = {}
        self._lock = RLock()
        self.states = {}
        self.errors = []
        self.instrument_events = []
        self.instrument_dispatcher = None

    @property
    def handles(self):
        with self._lock:
            return tuple(self._handles.values())

    def register(self, handle):
        with self._lock:
            if handle.instance_id in self._handles:
                raise ValueError(f"Duplicate measurement handle: {handle.instance_id}")
            self._handles[handle.instance_id] = handle

    def before_start(self, instance_id):
        return self._before_start(instance_id)

    def notify_state(self, instance_id, busy, state=""):
        with self._lock:
            self.states[instance_id] = {"busy": bool(busy), "state": str(state)}

    def report_error(self, instance_id, message):
        with self._lock:
            self.errors.append(f"{instance_id}: {message}")

    def close_blockers(self):
        blockers = []
        for handle in self.handles:
            try:
                specific = list(handle.close_blockers())
                blockers.extend(f"{handle.title}: {item}" for item in specific)
                if handle.command_running() and not specific:
                    blockers.append(f"{handle.title} is still running; wait for cleanup and saving.")
            except Exception as exc:
                message = f"{handle.title}: cannot verify close readiness: {exc}"
                blockers.append(message)
                self.report_error(handle.instance_id, message)
        return blockers

    def output_location_changed(self, path: Path):
        errors = []
        for handle in self.handles:
            try:
                handle.output_location_changed(Path(path))
            except Exception as exc:
                message = f"output-location notification failed: {exc}"
                self.report_error(handle.instance_id, message)
                errors.append(f"{handle.instance_id}: {message}")
        return errors

    def publish_instrument_state(self, change):
        """Queue via the shell's Qt bridge when attached; pure hosts deliver locally."""
        from .interchange import validate_instrument_state_change
        change = validate_instrument_state_change(change)
        if self.instrument_dispatcher is not None:
            self.instrument_dispatcher(change)
            return []
        return self.deliver_instrument_state(change)

    def deliver_instrument_state(self, change):
        """Deliver only to named recipients; never reach into a widget's settings."""
        from .interchange import validate_instrument_state_change
        change = validate_instrument_state_change(change)
        with self._lock:
            self.instrument_events.append(change)
        errors = []
        recipients = change.recipients
        known = {handle.instance_id for handle in self.handles}
        for recipient in recipients:
            if recipient not in known:
                message = f"Instrument change recipient is not installed: {recipient}"
                self.report_error(recipient, message)
                errors.append(message)
        for handle in self.handles:
            if handle.instance_id not in recipients:
                continue
            try:
                handle.instrument_state_changed(change)
            except Exception as exc:
                message = f"instrument-state notification failed: {exc}"
                self.report_error(handle.instance_id, message)
                errors.append(f"{handle.instance_id}: {message}")
        return errors

    instrument_state_changed = publish_instrument_state

    def request_emergency_stop(self, reason):
        """Request only the current local hardware handle, plus owner callbacks."""
        errors = []
        snapshot = self.ownership.snapshot()
        owner = snapshot.get("owner") or {}
        instance_id = owner.get("instance_id")
        # A remote owner is not this process's widget even if its ID is equal.
        import os
        # A free/fault record retains historical owner identity for provenance.
        # That identity must never abort later offline work in the same tab.
        local_owner = snapshot.get("state") == "owned" and owner.get("pid") == os.getpid()
        for handle in self.handles:
            if local_owner and handle.instance_id == instance_id:
                try:
                    handle.request_abort(str(reason))
                except Exception as exc:
                    message = f"abort callback failed: {exc}"
                    errors.append(f"{handle.instance_id}: {message}")
                    self.report_error(handle.instance_id, message)
        try:
            errors.extend(self.ownership.request_emergency_stop(str(reason)) or [])
        except Exception as exc:
            errors.append(f"Hardware cancellation callback failed: {exc}")
        return errors
