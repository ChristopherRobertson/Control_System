# Measurement module API, version 1

This document freezes the Python integration boundary for independent measurement
packages. Repository architecture and launch instructions remain in the existing
[repository README](../../../README.md). No scientific engine is implemented by
the host. The established Phase Scan is adapted in `legacy_phase_scan.py`; its
scientific meaning, native formats and single/dual state remain in its existing
workflows and widgets.

## Package ownership and registration

A feature owns `software/control_app/measurement_modules/<experiment_id>/`, its
tests, and its operating procedure. It does not edit the main window, state
machine, package `__init__.py`, registry or sibling features. Its package may
share pure helpers between modes, but never mutable settings, runners, review,
baselines, cancellation, SDK sessions, subscriptions or timing tables.

Each package exports exactly one frozen `ModuleDescriptor` named `DESCRIPTOR`
from `registration.py`:

```python
from control_app.measurement_host import API_VERSION, ModuleDescriptor

def create_tabs(context):
    # Defer Qt/widget imports until the host constructs the pair on the UI thread.
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), title="Slow Scan"),
        make_handle(context.for_mode("dual"), title="Dual-Detector Slow Scan"),
    )

DESCRIPTOR = ModuleDescriptor(
    api_version=API_VERSION,
    experiment_id="steady_state_slow_scan",
    display_order=100,
    create_tabs=create_tabs,
)
```

`api_version` is exactly integer `1`. `experiment_id` is immutable lowercase
snake_case, identical to its directory. `display_order` is an integer; ties sort
by ID. `create_tabs(context: MeasurementContext) -> Sequence[TabHandle]` returns
exactly two distinct widgets. The host orders single before dual and reserves
existing titles and instance IDs. Duplicate IDs/titles, incompatible versions,
missing SDKs, import failures and construction errors are reported per package;
working packages remain available. Python function signatures are validated
before activation. Discovery imports only registration modules; use lazy
imports for optional dependencies. Install by adding the package directory and
restart the application; no registry edits are needed.

Registration imports and widget construction must perform zero hardware I/O,
including enumeration, capability checks and connection. Context-based hardware
ownership is disabled while the factory runs. Schedule an explicit capability
operation after activation if needed; it must acquire ownership like acquisition.
Backend guards also require ownership at real device boundaries. Arbitrary
third-party Python is not sandboxed: this is an enforced service boundary and a
module compatibility requirement, not a security isolation mechanism.

The frozen `TabHandle` fields are:

| Field | Required value/signature |
| --- | --- |
| `instance_id` | `<experiment_id>:single` or `<experiment_id>:dual` |
| `title` | Nonempty top-level title unique across installed tabs |
| `widget` | A distinct `PySide6.QtWidgets.QWidget` |
| `command_running` | `() -> bool`, including outstanding cleanup/saving |
| `close_blockers` | `() -> Sequence[str]`, concise actionable reasons |
| `request_abort` | `(reason: str) -> None`, cancel this instance only |
| `output_location_changed` | `(path: pathlib.Path) -> None`, update the next operation |
| `instrument_state_changed` | `(change: InstrumentStateChange) -> None`, review named changes |
| `state_changed` | Qt signal with `.connect(callback)`; normally `Signal(bool)` |

All lifecycle callbacks run promptly on the UI thread. Emit state changes using
Qt signals so worker-to-UI delivery is queued safely. `command_running=False`
does not establish physical safety. Return close blockers until worker cleanup,
native/partial saving and any persistent session have actually finished. An
abort request preserves the distinction between intentional cancellation and
runtime failure. Callback exceptions must not bypass cleanup or data saving.

The reserved compatibility pairs are exercised as real temporary registration
packages in `software/tests/test_measurement_host_contract.py`:

| Stable ID | Single | Dual |
| --- | --- | --- |
| `steady_state_slow_scan` | Slow Scan | Dual-Detector Slow Scan |
| `fixed_wavenumber_kinetics` | Fixed-Wavenumber Kinetics | Dual-Detector Fixed-Wavenumber Kinetics |
| `nanosecond_stroboscopy` | Nanosecond Stroboscopy | Dual-Detector Nanosecond Stroboscopy |
| `microsecond_stroboscopy` | Microsecond Stroboscopy | Dual-Detector Microsecond Stroboscopy |
| `repeated_rapid_scan` | Repeated Rapid-Scan Phase Delay | Dual-Detector Repeated Rapid-Scan Phase Delay |
| `single_pump_scan_burst` | Single-Pump Scan Bursts | Dual-Detector Single-Pump Scan Bursts |

These fixtures are synthetic widgets, not production feature directories.

## Scoped context and operation snapshots

Only the application constructs `ContextFactory`. Its keyword arguments are
`configuration_provider`, `real_device_factories`, `simulated_device_factories`,
`promoted_bundle_loader`, `save_root_provider`, `preference_backend`, `ownership`,
and `lifecycle`. Modules receive an experiment context and immediately create
their two detector contexts with `.for_mode("single" | "dual")`. A detector
context cannot select another detector mode. It offers:

| API | Behavior |
| --- | --- |
| `.instance_id`, `.experiment_id`, `.mode` | Stable scope identities |
| `.configuration() -> dict` | Detached configuration copy |
| `.promoted_bundle(bundle_id) -> PromotedBundle` | Detached result of the injected promotion-validating loader |
| `.save_root() -> Path` | Current root for the next operation |
| `.preferences` | Scoped `value`, `setValue`, `contains`, `remove`, `sync` subset |
| `.new_plan(settings: Mapping) -> PlanSnapshot` | New UUID and recursively immutable settings |
| `.begin_operation(...) -> OperationSnapshot` | Freeze inputs and optionally acquire hardware before dispatch |
| `.devices.available(hardware=False) -> tuple[str, ...]` | Factory names, no discovery or SDK imports |
| `.devices.create(name, operation, **kwargs)` | Fresh service from frozen configuration; owned scope for real constructors |
| `.hardware_scope(operation)` | Bind the operation's token around backend access |
| `.ownership` | Instance-bound acquire/assert/scope/release/snapshot subset |
| `.lifecycle` | Instance-bound before-start, state, error and instrument-event hooks |

Preferences always use `measurements/<experiment_id>/<mode>/v1/<relative_key>`.
Absolute paths, traversal segments, empty keys and backslashes are rejected;
the namespace cannot be reassigned. The module never receives a global mutable
QSettings/session object. The legacy adapter privately migrates only its known
Phase Scan keys and retains old values for older software.

The exact operation signature is:

```python
begin_operation(
    settings: Mapping | None = None,
    *, plan: PlanSnapshot | None = None,
    calibration_records=(), sample_records=(),
    hardware: bool = False, purpose: str = "", cancel=None,
) -> OperationSnapshot
```

Pass either settings or a frozen plan. A plan belongs to one instance; loading a
native scientific plan is the feature's job, followed by creating a host plan
identity. Reusing a reviewed host plan keeps its plan UUID while every operation
gets a fresh, distinct run UUID. `cancel(reason: str)` signals this worker's
cancellation object and is registered with the hardware coordinator.

The snapshot fields are `api_version`, `instance_id`, `plan_id`, `run_id`,
`started_utc`, `hardware`, `settings`, `configuration`, `calibration_records`,
`sample_records`, `save_root`, `output_path`, and `ownership`. Container values
are recursively detached and immutable; native serializers can use `.to_dict()`.
Record data accepts mappings, dataclasses, lists/tuples, paths and scalar values;
mutable SDK/runner objects are rejected. Scientific arrays should be represented
by explicit selected values or native-file references, not live analysis objects.

New modules save under the frozen path
`<save_root>/measurements/<experiment_id>/<mode>/<run_uuid>/`. Begin does not
create folders. The native saver creates them and preserves partial, rejected,
diagnostic and restoration records. Later settings, baseline selections or global
save-location changes cannot retarget an active operation. Legacy Phase Scan
retains its established native output directories and formats.

Device factories implement
`factory(*, configuration: Mapping[str, Any], **kwargs) -> fresh_service`.
`devices.create` supplies a new mutable copy of **the operation's frozen
configuration**, never re-reads a configuration file, and prevents a caller from
overriding it. Real and simulated factory maps are separate; missing simulations
raise an error rather than falling back to hardware. A factory constructor may
prepare service state; actual discovery, connection and commands require the
owning hardware scope:

```python
cancel_event = threading.Event()
operation = context.begin_operation(
    plan=reviewed_plan,
    calibration_records=selected_calibrations,
    sample_records=selected_samples,
    hardware=True,
    purpose="explicit detector capability check",
    cancel=lambda reason: cancel_event.set(),
)
# Ownership and immutable inputs exist BEFORE starting a worker.
with context.hardware_scope(operation):
    detector = context.devices.create("hf2li", operation)
    # Feature adapter performs guarded discovery and verified cleanup here.
```

The scientific adapter must retain ownership through all cleanup, restoration
and required native preservation, then call:

```python
context.ownership.release(
    operation.ownership,
    safe_verified=actual_restoration_verified,
    preservation_verified=actual_required_records_saved,
    detail=actual_outcome_description,
)
```

These values are explicit outcomes, not assumptions based on a worker exiting.
An unverified outcome leaves an actionable coordinator fault. A stale callback
cannot release another operation's token. Persistent alignment/emission keeps
its token until safe closure. Only explicit recovery may acquire with
`context.ownership.acquire(..., recovery=True)` after a fault; recovery does not
repeat acquisition. Ordinary simulation/offline work uses `hardware=False`,
does not take the lock and bypasses hardware start blockers.

Scoped lifecycle methods are `.before_start() -> str | None`,
`.notify_state(busy: bool, state: str = "")`, `.report_error(message: str)` and
`.publish_instrument_state(change)`. Host app close consults every handle.
Normal Stop belongs to the active owning widget; emergency cancellation targets
the coordinator's live hardware owner and its registered cancellation callback,
without cancelling unrelated offline/simulated workers.

## Shared presentation with scientific adapters

`presentation.py` defines the exact `ScientificAdapter` protocol and optional
`GuidedMeasurementPanel(settings_widget, adapter, context)`. The panel supplies
nonblocking workers, settings/summary/validation, Save/Load Plan, native loading,
preliminary/review/start, New run, data export, progress and cancellation.
`LinkedSliceControl` and toolbar plot helpers are independent reusable parts.
Scientific units support ns, us, ms and longer periods. The module chooses a
suitable plot; a steady-state spectrum does not need a kinetic surface.

Adapter `hardware_required(kind, settings)` and `selected_records()` are pure.
The panel creates the canonical operation before dispatching a worker and wraps
hardware calls in `.hardware_scope`. Its `StartSnapshot` contains that operation
plus detached scientific plan/preliminary data. Scientific adapters still own
planning, readiness, normalization, fit models, schemas, review and verified
cleanup/preservation. Implement these using the executable
`DummyScientificAdapter` in `software/tests/test_measurement_host_presentation.py`.
Do not extend PhaseScanWidget's `dual_detector` branch for new experiments.

## Narrow standalone interchange

`interchange.py` is independent of all six feature packages. Version `1` records
can be serialized as JSON; `sample_selection_from_dict` and
`load_sample_selection` validate standalone data without loading Slow Scan.

`SampleSpectralSelection` contains stable selection/sample IDs, a producer
instance, `SourceRecord(producer_run_id, native_path, created_utc,
software_version)`, condition identity plus explicit condition data, selected
`SpectralWindow(lower_cm1, upper_cm1, center_cm1, uncertainty_cm1, label)` values,
named acceptance and UTC acceptance time. It requires disposition `accepted`,
finite bounded windows and nonnegative uncertainties. Missing uncertainty is
explicit (`None`) and accompanied by `uncertainty_description`. Producers retain
the source record; consumers choose and validate the record without importing
its producer. Saving an accepted selection never overwrites a prior record.

`PromotedCalibrationReference(bundle_id, calibration_id)` is a distinct type;
constructing it does not establish promotion or readiness. The injected bundle
loader validates actual promotion. Sample validation rejects calibration
records, and sample acceptance never promotes instrument calibration.

`InstrumentStateChange(producer_instance_id, recipients, changes, reason, ...)`
contains schema version, event identity, UTC timestamp and explicit recipients
such as `("phase_scan:single", "nanosecond_stroboscopy:dual")`. Each
`DeviceConfigurationChange(device_id, configuration_key, previous_value,
new_value)` names its actual device/configuration change. Wildcards, empty
recipients and unspecified changes are rejected. The scoped publisher must name
its own producer instance. The host reports absent recipients and isolates
callback errors. Recipients may invalidate their own readiness/review visibly;
events must never silently replace another tab's settings. No digest matching is
an operational gate in these APIs.

## Compatibility checks

With the repository's UI test environment, run:

```powershell
python -m pytest software/tests/test_measurement_host_contract.py software/tests/test_measurement_host_contract_interchange.py software/tests/test_measurement_host_presentation.py
```

The contract fixtures install all six temporary package pairs simultaneously,
isolate optional failures, reject malformed factories and duplicate tabs, forbid
construction-time ownership, verify preference/plan/output/baseline/cancellation
separation, and exercise explicit device checks and standalone data exchange.
Ownership/process and existing Phase Scan suites provide the backend and legacy
regression checks. They use simulated instruments; passing them does not claim
live hardware commissioning.
