"""Exclusive coupled-instrument ownership, including process crash provenance.

The byte lock is held until physical cleanup AND required preservation have been
verified. Its disappearance is never evidence of safe idle: the durable record
must also say ``free``. Recovery is an explicit operation, never a retry policy.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from threading import RLock
from uuid import uuid4


class OwnershipError(RuntimeError):
    """The coupled instrument is owned or requires verified recovery."""


@dataclass(frozen=True)
class OwnershipToken:
    token_id: str
    instance_id: str
    operation_id: str
    pid: int
    acquired_utc: str


def _utc():
    return datetime.now(UTC).isoformat()


_bound_owner = ContextVar("measurement_hardware_owner", default=None)


class HardwareCoordinator:
    """A process-wide coordinator backed by a nonblocking OS file lock.

    Pass an isolated ``lock_path`` in tests. All production checkouts use the
    same machine path, so separate app/task processes and accounts compete.
    No constructor, import or snapshot opens a device.
    """
    def __init__(self, lock_path=None):
        base = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) if os.name == "nt" else Path("/var/tmp")
        self.lock_path = Path(lock_path) if lock_path else base / "ControlSystem" / "coupled_spectrometer.lock"
        self.record_path = self.lock_path.with_suffix(".owner.json")
        self.journal_path = self.lock_path.with_suffix(".history.jsonl")
        self._mutex = RLock()
        self._file = None
        self._token = None
        self._cancel = None
        self._fault = False

    def _read(self):
        try:
            value = json.loads(self.record_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("state") not in {"free", "owned", "fault"}:
                raise ValueError("invalid owner record")
            return value
        except FileNotFoundError:
            return {"state": "free", "owner": None, "detail": "No prior ownership record"}
        except (ValueError, OSError) as exc:
            return {"state": "fault", "owner": None, "detail": f"Owner provenance unreadable; explicit recovery required: {exc}"}

    def _write(self, state, detail, **fields):
        record = {"schema_version": 1, "state": state, "owner": asdict(self._token) if self._token else None,
                  "updated_utc": _utc(), "detail": detail, **fields}
        # Retain every transition. Journal failure itself prohibits advertising
        # free hardware; write the authoritative record only after the journal.
        with self.journal_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary = self.record_path.with_name(self.record_path.name + "." + uuid4().hex + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.record_path)

    def _lock_os(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.lock_path.open("a+b")
        try:
            if stream.seek(0, 2) == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            record = self._read()
            raise OwnershipError(f"Coupled spectrometer is owned by {record.get('owner')}; finish its stop, restoration and saving first") from exc
        self._file = stream

    def _unlock_os(self):
        stream, self._file = self._file, None
        if stream is None:
            return
        try:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()

    def acquire(self, instance_id, operation_id=None, purpose="", cancel=None, recovery=False):
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise ValueError("Ownership requires a stable instance_id")
        with self._mutex:
            if self._token is not None and not (recovery and self._fault):
                raise OwnershipError(f"Coupled spectrometer is owned by {self._token.instance_id}: {self._token.operation_id}")
            if self._file is None:
                self._lock_os()
            previous = self._read()
            if previous["state"] != "free" and not recovery:
                self._unlock_os()
                raise OwnershipError(f"Explicit Safe Shutdown recovery required; previous {previous['state']} owner: {previous.get('owner')}. {previous.get('detail', '')}")
            token = OwnershipToken(uuid4().hex, instance_id, operation_id or uuid4().hex, os.getpid(), _utc())
            self._token, self._cancel, self._fault = token, cancel, False
            try:
                self._write("owned", purpose, recovery=bool(recovery), previous=previous if previous["state"] != "free" else None)
            except BaseException:
                self._fault = True
                # Keep the lock even if provenance storage fails.
                raise
            return token

    def assert_owner(self, token):
        with self._mutex:
            if token is None or token != self._token or token.pid != os.getpid() or self._file is None:
                raise OwnershipError("Missing or stale hardware ownership token")

    @contextmanager
    def scope(self, token):
        self.assert_owner(token)
        bound = _bound_owner.set((self, token))
        try:
            yield token
        finally:
            _bound_owner.reset(bound)

    def release(self, token, *, safe_verified, preservation_verified=True, detail=""):
        with self._mutex:
            self.assert_owner(token)
            if not (safe_verified and preservation_verified):
                self._fault = True
                # This operation has reached its reported cleanup/preservation
                # boundary. A later offline worker must never inherit its
                # cancellation callback merely because the fault retains a lock.
                self._cancel = None
                self._write("fault", detail or "Safe shutdown/restoration or required data preservation is unverified; run explicit recovery",
                            safe_verified=bool(safe_verified), preservation_verified=bool(preservation_verified))
                return
            try:
                self._write("free", detail or "Safe shutdown/restoration and required preservation verified",
                            safe_verified=True, preservation_verified=True)
            except BaseException:
                self._fault = True
                raise
            self._token, self._cancel, self._fault = None, None, False
            self._unlock_os()

    def snapshot(self):
        with self._mutex:
            record = self._read()
            if self._token is not None:
                record.update(state="fault" if self._fault else "owned", owner=asdict(self._token))
            # A surviving owned record is deliberately never inferred free by PID.
            return record

    def request_emergency_stop(self, reason):
        with self._mutex:
            callback = self._cancel
        if callback is None:
            return []
        try:
            callback(reason)
            return []
        except BaseException as exc:
            return [f"Owner emergency cancellation failed: {type(exc).__name__}: {exc}"]


_default = None
_default_lock = RLock()


def default_coordinator():
    global _default
    with _default_lock:
        if _default is None:
            _default = HardwareCoordinator()
        return _default


def require_hardware_owner(service=None):
    """Bind a real transport once, then reject reused sessions after release.

    Acquirer helper threads may use their owning session without inheriting
    contextvars; identity remains pinned to that session, never a current tab.
    """
    owner = getattr(service, "_measurement_owner", None) if service is not None else None
    owner = owner or _bound_owner.get()
    if owner is None:
        raise OwnershipError("Acquire coupled spectrometer ownership before real device discovery, connection or control")
    coordinator, token = owner
    coordinator.assert_owner(token)
    if service is not None:
        service._measurement_owner = owner
    return token


def check_bound_hardware_owner(service):
    """Validate already-bound sessions; injected test transports stay independent."""
    if getattr(service, "_measurement_owner", None) is not None:
        require_hardware_owner(service)


def adopt_recovery_session(service):
    """Explicit recovery may inhibit a prior session using the recovery token.

    Normal operations cannot inherit SDK sessions. This is limited to the
    guarded recovery scope for the same instrument and current process.
    """
    if service is None or getattr(service, "_measurement_owner", None) is None:
        return
    current = _bound_owner.get()
    if current is None:
        raise OwnershipError("Recovery session adoption requires a scoped recovery owner")
    coordinator, token = current
    coordinator.assert_owner(token)
    previous_coordinator, previous_token = service._measurement_owner
    if token == previous_token:
        return
    if (token.instance_id != "manual:recovery" or not coordinator.snapshot().get("recovery") or
            previous_token.pid != os.getpid() or
            previous_coordinator.lock_path.resolve() != coordinator.lock_path.resolve()):
        raise OwnershipError("Only explicit recovery may adopt a prior session for this instrument")
    service._measurement_owner = current
