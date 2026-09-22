"""Injected per-module and per-detector services, with immutable operation inputs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from .contracts import MODES, ContractError, validate_experiment_id, validate_instance_id


def freeze_data(value: Any) -> Any:
    """Detach JSON-like scientific selections and make every container immutable.

    Mutable runner/SDK objects are deliberately unsupported as operation inputs.
    Native schemas stay in the experiment; selected values must be explicit data.
    """
    if is_dataclass(value) and not isinstance(value, type):
        value = {name: getattr(value, name) for name in value.__dataclass_fields__}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("Snapshot mapping keys must be strings")
        return MappingProxyType({key: freeze_data(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_data(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"Operation inputs must be explicit data, not {type(value).__name__}")


def thaw_data(value: Any) -> Any:
    """Return a fresh mutable JSON-compatible copy for a native serializer."""
    if isinstance(value, Mapping):
        return {key: thaw_data(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_data(item) for item in value]
    return deepcopy(value)


@dataclass(frozen=True)
class PlanSnapshot:
    plan_id: str
    instance_id: str
    settings: Mapping[str, Any]

    def __post_init__(self):
        UUID(self.plan_id)
        validate_instance_id(self.instance_id)
        if not isinstance(self.settings, Mapping):
            raise ContractError("Plan settings must be a mapping")
        object.__setattr__(self, "settings", freeze_data(self.settings))


@dataclass(frozen=True)
class OperationSnapshot:
    """Frozen before device work; later tab edits cannot retarget the operation."""

    api_version: int
    instance_id: str
    plan_id: str
    run_id: str
    started_utc: str
    hardware: bool
    settings: Mapping[str, Any]
    configuration: Mapping[str, Any]
    calibration_records: tuple[Any, ...]
    sample_records: tuple[Any, ...]
    save_root: Path
    output_path: Path
    ownership: Any | None

    def __post_init__(self):
        if type(self.api_version) is not int or self.api_version != 1:
            raise ContractError("Unsupported operation API version")
        validate_instance_id(self.instance_id)
        UUID(self.plan_id)
        UUID(self.run_id)
        if self.plan_id == self.run_id:
            raise ContractError("Plan and run identities must be distinct")
        for name in ("settings", "configuration"):
            if not isinstance(getattr(self, name), Mapping):
                raise ContractError(f"Operation {name} must be a mapping")
            object.__setattr__(self, name, freeze_data(getattr(self, name)))
        for name in ("calibration_records", "sample_records"):
            object.__setattr__(self, name, tuple(freeze_data(item) for item in getattr(self, name)))
        if self.hardware != (self.ownership is not None):
            raise ContractError("Hardware operations require an ownership token; simulations cannot own hardware")
        if self.ownership is not None and self.ownership.instance_id != self.instance_id:
            raise ContractError("Operation ownership must belong to this instance")
        object.__setattr__(self, "save_root", Path(self.save_root))
        object.__setattr__(self, "output_path", Path(self.output_path))

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        result["ownership"] = asdict(self.ownership) if is_dataclass(self.ownership) else self.ownership
        result["save_root"] = str(self.save_root)
        result["output_path"] = str(self.output_path)
        return thaw_data(result)


class ScopedPreferences:
    """QSettings-compatible subset; no underlying backend or global keys exposed."""

    __slots__ = ("__backend", "__namespace")

    def __init__(self, backend: Any, experiment_id: str, mode: str):
        validate_experiment_id(experiment_id)
        if mode not in MODES:
            raise ContractError(f"Unsupported detector mode {mode!r}")
        self.__backend = backend
        self.__namespace = f"measurements/{experiment_id}/{mode}/v1/"

    @property
    def namespace(self) -> str:
        return self.__namespace

    def _key(self, key: str) -> str:
        if (not isinstance(key, str) or not key or "\\" in key or key.startswith("/")
                or any(part in ("", ".", "..") for part in key.split("/"))):
            raise ContractError(f"Preference key must be a nonempty relative key: {key!r}")
        return self.namespace + key

    def value(self, key: str, default: Any = None, **kwargs: Any) -> Any:
        path = self._key(key)
        if hasattr(self.__backend, "value"):
            value = self.__backend.value(path, default, **kwargs)
        else:
            value = self.__backend.get(path, default)
            if "type" in kwargs and value is not None:
                value = kwargs["type"](value)
        return deepcopy(value)

    def setValue(self, key: str, value: Any) -> None:
        path = self._key(key)
        if hasattr(self.__backend, "setValue"):
            self.__backend.setValue(path, deepcopy(value))
        else:
            self.__backend[path] = deepcopy(value)

    def contains(self, key: str) -> bool:
        path = self._key(key)
        return self.__backend.contains(path) if hasattr(self.__backend, "contains") else path in self.__backend

    def remove(self, key: str) -> None:
        path = self._key(key)
        if hasattr(self.__backend, "remove"):
            self.__backend.remove(path)
        else:
            for candidate in tuple(self.__backend):
                if candidate == path or candidate.startswith(path + "/"):
                    del self.__backend[candidate]

    def sync(self) -> None:
        if hasattr(self.__backend, "sync"):
            self.__backend.sync()


class ScopedOwnership:
    """Restrict token operations to the receiving tab's identity."""

    def __init__(self, coordinator: Any, instance_id: str, active: Callable[[], bool]):
        self.__coordinator = coordinator
        self.__instance_id = instance_id
        self.__active = active

    @property
    def instance_id(self) -> str:
        return self.__instance_id

    def acquire(self, operation_id: str | None = None, *, purpose: str = "", cancel=None, recovery=False):
        if not self.__active():
            raise RuntimeError("Hardware ownership is unavailable during module construction")
        return self.__coordinator.acquire(
            self.instance_id, operation_id=operation_id, purpose=purpose, cancel=cancel, recovery=recovery
        )

    def assert_owner(self, token: Any) -> None:
        if getattr(token, "instance_id", None) != self.instance_id:
            raise RuntimeError(f"Ownership token belongs to another tab, not {self.instance_id}")
        self.__coordinator.assert_owner(token)

    def release(self, token: Any, *, safe_verified: bool, preservation_verified: bool = True, detail: str = ""):
        self.assert_owner(token)
        return self.__coordinator.release(
            token, safe_verified=safe_verified, preservation_verified=preservation_verified, detail=detail
        )

    def park(self, token, *, cleanup, detail="Prepared measurement session; awaiting sample"):
        self.assert_owner(token)
        return self.__coordinator.park(token, cleanup=cleanup, detail=detail)

    def close_parked_session(self):
        return self.__coordinator.close_parked_session(instance_id=self.instance_id)

    def has_parked_session(self):
        return self.__coordinator.has_parked_session(instance_id=self.instance_id)

    def snapshot(self):
        return deepcopy(self.__coordinator.snapshot())

    @contextmanager
    def scope(self, token: Any):
        self.assert_owner(token)
        with self.__coordinator.scope(token):
            yield token


class _ScopedLifecycle:
    def __init__(self, hooks: Any, instance_id: str):
        self.__hooks = hooks
        self.instance_id = instance_id

    def _call(self, method: str, *args):
        callback = getattr(self.__hooks, method, None)
        return callback(*args) if callable(callback) else None

    def before_start(self) -> str | None:
        return self._call("before_start", self.instance_id)

    def notify_state(self, busy: bool, state: str = "") -> None:
        self._call("notify_state", self.instance_id, busy, state)

    def report_error(self, message: str) -> None:
        self._call("report_error", self.instance_id, message)

    def publish_instrument_state(self, change: Any) -> None:
        from .interchange import validate_instrument_state_change
        validate_instrument_state_change(change)
        if change.producer_instance_id != self.instance_id:
            raise ContractError("Instrument-state producer must identify the sending tab")
        self._call("publish_instrument_state", change)


class _ScopedDevices:
    def __init__(self, context: "MeasurementContext", real: Mapping[str, Callable], simulated: Mapping[str, Callable]):
        self.__context, self.__real, self.__simulated = context, dict(real), dict(simulated)

    def available(self, *, hardware: bool = False) -> tuple[str, ...]:
        return tuple(sorted(self.__real if hardware else self.__simulated))

    def create(self, name: str, operation: OperationSnapshot, **kwargs: Any):
        self.__context._validate_operation(operation)
        if "configuration" in kwargs:
            raise ContractError("Device configuration comes from the frozen operation")
        factories = self.__real if operation.hardware else self.__simulated
        try:
            factory = factories[name]
        except KeyError as exc:
            raise KeyError(f"No {'real' if operation.hardware else 'simulated'} factory named {name!r}") from exc
        if operation.hardware:
            with self.__context.hardware_scope(operation):
                return factory(configuration=thaw_data(operation.configuration), **kwargs)
        return factory(configuration=thaw_data(operation.configuration), **kwargs)


class ContextFactory:
    """Application-only service injection. Modules receive MeasurementContext."""

    def __init__(
        self, *, configuration_provider: Callable[[], Mapping[str, Any]] | None = None,
        real_device_factories: Mapping[str, Callable] | None = None,
        simulated_device_factories: Mapping[str, Callable] | None = None,
        promoted_bundle_loader: Callable[[str], Any] | None = None,
        save_root_provider: Callable[[], str | Path] | None = None,
        instance_save_root_provider: Callable[[str], str | Path] | None = None,
        preference_backend: Any = None, ownership: Any = None, lifecycle: Any = None,
    ):
        from control_app.paths import get_save_location
        from control_app.promoted_bundles import load_promoted_bundle
        if ownership is None:
            from .ownership import default_coordinator
            ownership = default_coordinator()
        self.__services = dict(
            configuration_provider=configuration_provider or (lambda: {}),
            real_device_factories=dict(real_device_factories or {}),
            simulated_device_factories=dict(simulated_device_factories or {}),
            promoted_bundle_loader=promoted_bundle_loader or load_promoted_bundle,
            save_root_provider=save_root_provider or get_save_location,
            instance_save_root_provider=instance_save_root_provider,
            preference_backend={} if preference_backend is None else preference_backend,
            ownership=ownership, lifecycle=lifecycle,
        )

    def for_experiment(self, experiment_id: str, *, constructing: bool = False) -> "MeasurementContext":
        return MeasurementContext(experiment_id, self.__services, active=[not constructing])


class MeasurementContext:
    """Module context. Call for_mode exactly once for each independently owned tab."""

    def __init__(self, experiment_id: str, services: dict[str, Any], *, mode: str | None = None, active: list[bool]):
        self.__experiment_id = validate_experiment_id(experiment_id)
        if mode is not None and mode not in MODES:
            raise ContractError(f"Unsupported detector mode {mode!r}")
        self.__mode = mode
        self.__instance_id = f"{experiment_id}:{mode}" if mode else None
        self.__services, self.__active = services, active
        if mode is not None:
            self.preferences = ScopedPreferences(services["preference_backend"], experiment_id, mode)
            self.ownership = ScopedOwnership(services["ownership"], self.instance_id, lambda: self.__active[0])
            self.lifecycle = _ScopedLifecycle(services["lifecycle"], self.instance_id)
            self.devices = _ScopedDevices(self, services["real_device_factories"], services["simulated_device_factories"])

    @property
    def experiment_id(self) -> str:
        return self.__experiment_id

    @property
    def mode(self) -> str | None:
        return self.__mode

    @property
    def instance_id(self) -> str | None:
        return self.__instance_id

    def for_mode(self, mode: str) -> "MeasurementContext":
        if self.mode is not None:
            raise ContractError("A detector-scoped context cannot access another mode")
        return MeasurementContext(self.experiment_id, self.__services, mode=mode, active=self.__active)

    def _activate(self) -> None:
        self.__active[0] = True

    def _require_mode(self) -> None:
        if self.mode is None:
            raise ContractError("Select context.for_mode('single' or 'dual') before accessing tab services")

    def configuration(self) -> dict[str, Any]:
        return deepcopy(dict(self.__services["configuration_provider"]()))

    def promoted_bundle(self, bundle_id: str) -> Any:
        return deepcopy(self.__services["promoted_bundle_loader"](bundle_id))

    def save_root(self) -> Path:
        provider = self.__services.get("instance_save_root_provider")
        if provider is not None:
            self._require_mode()
            return Path(provider(self.instance_id)).expanduser().resolve()
        return Path(self.__services["save_root_provider"]()).expanduser().resolve()

    def new_plan(self, settings: Mapping[str, Any]) -> PlanSnapshot:
        self._require_mode()
        return PlanSnapshot(str(uuid4()), self.instance_id, freeze_data(settings))

    def begin_operation(
        self, settings: Mapping[str, Any] | None = None, *, plan: PlanSnapshot | None = None,
        calibration_records=(), sample_records=(), hardware: bool = False, purpose: str = "", cancel=None,
    ) -> OperationSnapshot:
        """Snapshot all inputs and acquire ownership, before the caller starts a worker.

        No directories or instruments are touched. The native saver creates the
        frozen output_path when needed, including after cancellation or failure.
        Hardware callers must retain ownership until cleanup AND preservation are
        verified, then call ownership.release with the actual outcomes. A saved
        blank may instead park a prepared, emission-off session; the same tab's
        next operation resumes its existing SDK ownership token.
        """
        self._require_mode()
        if hardware:
            blocker = self.lifecycle.before_start()
            if blocker:
                raise RuntimeError(str(blocker))
        if plan is not None:
            if plan.instance_id != self.instance_id:
                raise ContractError("A plan cannot cross experiment or detector instances")
            UUID(plan.plan_id)
            if settings is not None:
                raise ContractError("Pass settings or a frozen plan, not both")
        else:
            plan = self.new_plan(settings or {})
        # Complete fallible data validation before acquiring hardware ownership.
        frozen_settings = freeze_data(plan.settings)
        configuration = freeze_data(self.configuration())
        calibration = tuple(freeze_data(value) for value in calibration_records)
        samples = tuple(freeze_data(value) for value in sample_records)
        root = self.save_root()
        run_id = str(uuid4())
        if self.__services.get("instance_save_root_provider") is not None:
            output = root / run_id
        else:
            output = root / "measurements" / self.experiment_id / self.mode / run_id
        started = datetime.now(timezone.utc).isoformat()
        token = self.ownership.acquire(run_id, purpose=purpose, cancel=cancel) if hardware else None
        return OperationSnapshot(1, self.instance_id, plan.plan_id, run_id, started, hardware,
                                 frozen_settings, configuration, calibration, samples, root, output, token)

    def _validate_operation(self, operation: OperationSnapshot) -> None:
        self._require_mode()
        if operation.instance_id != self.instance_id:
            raise ContractError("An operation cannot cross experiment or detector instances")

    @contextmanager
    def hardware_scope(self, operation: OperationSnapshot):
        self._validate_operation(operation)
        if not operation.hardware or operation.ownership is None:
            raise ContractError("Real device access requires a hardware operation")
        with self.ownership.scope(operation.ownership):
            yield operation
