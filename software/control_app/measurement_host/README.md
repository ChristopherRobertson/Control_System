# Measurement module API, version 1

This document freezes the Python integration boundary for independent measurement
packages. Repository architecture and launch instructions remain in the existing
[repository README](../../../README.md). No scientific engine is implemented by
the host. The established Phase Scan lives in `measurement_modules/phase_scan/`;
its former import paths remain compatibility aliases.

## Package ownership and registration

A feature owns `software/control_app/measurement_modules/<experiment_id>/`, its
tests, and its operating procedure. It does not edit the main window, state
machine, package `__init__.py`, registry or sibling features. Its package may
share pure helpers between modes, but never mutable settings, runners, review,
baselines, cancellation, subscriptions or timing tables. The desktop host owns
application-lifetime SDK connections and lends operation-scoped device leases;
modules must not share leases or bypass exclusive instrument ownership.

Each package exports exactly one frozen `ModuleDescriptor` named `DESCRIPTOR`
from `registration.py`:

```python
from control_app.measurement_host import API_VERSION, ModuleDescriptor
from control_app.measurement_host.naming import tab_title

def create_tabs(context):
    # Defer Qt/widget imports until the host constructs the pair on the UI thread.
    from .widgets import make_handle
    return (
        make_handle(context.for_mode("single"), title=tab_title("steady_state_slow_scan", "single")),
        make_handle(context.for_mode("dual"), title=tab_title("steady_state_slow_scan", "dual")),
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

`naming.py` defines the visible order and labels independently of stable module
and native record IDs. `EXPERIMENT_ORDER` lists the six methods in the following
order; `tab_title(experiment_id, mode)` uses the Single label or its `DD ` variant.
The top-level mode selector defaults to **Single**; **Dual** shows the `DD `
pages. The matching **Phase Scan** or **DD Phase Scan** follows these six methods,
then MIRcat, T660-1, Nd:YAG, OPO Iris and Plotter. The application retains all
**19 tab instances** and shows **12 per mode**. A mode change only changes
visibility: settings, active operations, ownership, emergency-stop routing and
close checks remain attached to every instance, including hidden pages.

| Stable ID | Single | Dual |
| --- | --- | --- |
| `steady_state_slow_scan` | Slow Scan | DD Slow Scan |
| `fixed_wavenumber_kinetics` | Fixed Wavenumber | DD Fixed Wavenumber |
| `nanosecond_stroboscopy` | Nanosecond Stroboscopy | DD Nanosecond Stroboscopy |
| `microsecond_stroboscopy` | Microsecond Stroboscopy | DD Microsecond Stroboscopy |
| `single_pump_scan_burst` | Single Scan Phase Delay | DD Single Scan Phase Delay |
| `repeated_rapid_scan` | Rapid Scan Phase Delay | DD Rapid Scan Phase Delay |

Compatibility fixtures remain in `software/tests/test_measurement_host_contract.py`;
the installed-module smoke test checks the actual six production pairs.

## Scoped context and operation snapshots

Only the application constructs `ContextFactory`. Its keyword arguments are
`configuration_provider`, `real_device_factories`, `simulated_device_factories`,
`promoted_bundle_loader`, `save_root_provider`, `preference_backend`, `ownership`,
`lifecycle`, and optional `instance_save_root_provider`. The application supplies
`instance_save_root_provider(instance_id: str) -> str | Path` to resolve each
page's destination independently. Modules receive an experiment context and immediately create
their two detector contexts with `.for_mode("single" | "dual")`. A detector
context cannot select another detector mode. It offers:

| API | Behavior |
| --- | --- |
| `.instance_id`, `.experiment_id`, `.mode` | Stable scope identities |
| `.configuration() -> dict` | Detached configuration copy |
| `.promoted_bundle(bundle_id) -> PromotedBundle` | Detached result of the injected promotion-validating loader |
| `.save_root() -> Path` | This detector instance's current root for the next operation |
| `.preferences` | Scoped `value`, `setValue`, `contains`, `remove`, `sync` subset |
| `.new_plan(settings: Mapping) -> PlanSnapshot` | New UUID and recursively immutable settings |
| `.begin_operation(...) -> OperationSnapshot` | Freeze inputs and optionally acquire hardware before dispatch |
| `.devices.available(hardware=False) -> tuple[str, ...]` | Factory names, no discovery or SDK imports |
| `.devices.create(name, operation, **kwargs)` | Operation-scoped service lease in the desktop, fresh service otherwise; frozen configuration and owned scope |
| `.hardware_scope(operation)` | Bind the operation's token around backend access |
| `.ownership` | Instance-bound acquire/assert/scope/release/snapshot subset |
| `.lifecycle` | Instance-bound before-start, state, error and instrument-event hooks |

Preferences always use `measurements/<experiment_id>/<mode>/v1/<relative_key>`.
Absolute paths, traversal segments, empty keys and backslashes are rejected;
the namespace cannot be reassigned. The module never receives a global mutable
QSettings/session object. The Phase Scan adapter imports supported preference keys into its scoped
namespace without changing source values.

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

In the desktop application, each measurement page defaults to
`<research_root>/experiments/runs/YYYY-MM-DD/<exact current tab title>/`, using the local
calendar date. Titles are preserved exactly, including spaces and the `DD ` prefix.
The instance provider resolves either that default or the custom destination
chosen for that page and detector mode. Choosing a custom destination does not
retarget another page. `begin_operation` freezes this `save_root` and produces
`output_path = <save_root>/<run_uuid>/`; for example, the default Dual Slow Scan
destination is `<research_root>/experiments/runs/YYYY-MM-DD/DD Slow Scan/<run_uuid>/`.

Begin does not create folders. The native saver creates them and preserves
partial, rejected, diagnostic and restoration records. Later settings, baseline
selections, date rollover, mode switches or save-location changes cannot retarget
an active operation. Phase Scan uses its native run-directory
names and formats under the matching Phase Scan or DD Phase Scan page root.
Native input files and their paths are not moved or renamed by output selection.
Nd:YAG is a device-page label and never a folder name; that page and standalone
device output default to the plain dated root
`<research_root>/experiments/runs/YYYY-MM-DD/`.

For compatibility, an embedding that supplies only the original zero-argument
`save_root_provider` retains the version 1 output layout
`<save_root>/measurements/<experiment_id>/<mode>/<run_uuid>/`. The desktop uses
the instance provider described above. Stable experiment IDs, preference
namespaces and native record schemas are independent of these display names
and destination defaults.

Device factories implement
`factory(*, configuration: Mapping[str, Any], **kwargs) -> service`.
`devices.create` supplies a new mutable copy of **the operation's frozen
configuration**, never re-reads a configuration file, and prevents a caller from
overriding it. Real and simulated factory maps are separate; missing simulations
raise an error rather than falling back to hardware. A factory constructor may
prepare service state; actual discovery, connection and commands require the
owning hardware scope:

The desktop starts `ApplicationDeviceSession` once in a background worker. Independent
connections are initialized and read concurrently (at most six workers), with one
ordered task per device. Every worker explicitly binds the same exclusive startup
ownership token; all workers finish before readiness or owner release. HF2LI
supported-choice enumeration still runs once at each application startup. Per-device
and total elapsed seconds are returned for diagnostics and shown in startup status.
Its
cached views are read-only and never perform I/O on tab activation. Acquisitions
and explicit device commands keep live readbacks. An operation's `close` releases
its use of a transport; it must still stop acquisition, inhibit outputs and
perform its existing cleanup. The application runs the safe-state procedure and
physically disconnects the pooled services on shutdown. It retains the process
lock between operations, so another process cannot open the same instruments.
Standalone factories and injected simulation services retain their previous
lifecycle. The application cache never replaces safety or acquisition readbacks.

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

New pages use `CompactMeasurementPanel(settings_widget, adapter, context,
parent=None, *, advanced_widget=None)` from `presentation.py`, implementing
`CompactScientificAdapter`. Essential scientific inputs occupy the left column;
concise derived-setting rows and the primary plot occupy the right. Independently
overridable calculated settings stay displayed in the framed Advanced overrides
group, with each field independently set to Automatic or an explicit value.
The panel has no review object, acknowledgement state or procedural checkbox.
`ScientificAdapter` and `GuidedMeasurementPanel` provide compatibility
APIs for existing integrations; new measurement pages do not use their review flow.

Adapters retain `read_settings`, `apply_settings`, `make_plan`, `validate_plan`,
`selected_records`, `hardware_required`, `run_preliminary`, `run_measurement`,
`request_abort`, `save_plan`, `load_plan`, `load_run`, `export_run` and `new_run`
signatures. `summarize_plan(plan)` returns ordered `(label, value)` pairs, with
short values rather than explanatory paragraphs. Required
`validate_preliminary(preliminary_or_None, plan) -> Sequence[str]` checks actual
scientific data compatibility. Return `()` for `None` when a method does not need
a separate preliminary; hide or repurpose its preliminary button. A harmless
settings refresh retains acquired data and rechecks compatibility automatically.
Optional `validate_operation(kind, plan, preliminary) -> Sequence[str]` validates
numeric, device and data prerequisites for a particular action. Neither callback
may introduce manual approval, temperature-provenance or promotion prerequisites
for raw acquisition. Calibrated claims still use applicable promoted bundles.

`begin("preliminary" | "measurement")` validates and dispatches the standard
scientific action. Additional blank and device-check actions use
`begin_operation(kind, callback, *, invalidates_preliminary=False,
requires_valid_plan=True)`; the callback receives `(StartSnapshot, OperationWorker)`.
Only custom actions may set `requires_valid_plan=False`, allowing a device check
before acquisition inputs can produce a valid plan. Such an action still freezes
current settings, invokes operation-specific validation and acquires declared
hardware ownership. Its scientific snapshot plan may be `None`. Completion emits
`operation_finished(kind, WorkerOutcome)` so the feature can retain its result and
call `refresh_readiness()` or `refresh_plan()`.

If `read_settings()` itself requires valid scientific inputs, a feature may
provide pure `read_operation_settings(kind)` to supply unvalidated intent and
mode for custom actions with `requires_valid_plan=False`. The host freezes that
data using the same snapshot path. Standard acquisition never uses this hook.

Use the panel's named extension points instead of replacing its layout:

| Purpose | API |
| --- | --- |
| Essential inputs and extra actions | `settings_layout` / `control_layout`, `settings_extras_layout`, `add_settings_action(text, callback)` |
| Always-visible independent overrides | `set_advanced_widget(widget)`, `advanced_layout`, `advanced_content` / `advanced_group` |
| Blank actions | `blank_actions_layout`, `add_blank_action(text, callback)` |
| Standard actions and plan files | `action_layout`, `file_layout` |
| Derived values and primary results | `summary_form`, `summary_values`, `set_summary_rows(rows)`, `result_layout`, `add_result_widget(widget)` |
| Native load and export | `run_file_layout` |

The standard controls are `save_plan_button`, `load_plan_button`,
`preliminary_button`, `start_button`, `abort_button`, `new_run_button`,
`load_run_button`, `export_button`, `validation`, `status` and `progress`.
Features may give actions scientific labels and hide redundant actions.
`busy_changed`, `result_ready`, `preliminary_ready`, `run_loaded`, `outcome_ready`,
`operation_finished` and `new_run_requested` notify the owning feature only.
`command_running`, `close_blockers` and `request_abort` preserve the shared
lifecycle, worker cleanup and native preservation boundaries.

`LinkedSliceControl` and toolbar plot helpers are independent reusable parts.
Scientific units support ns, us, ms and longer periods. The module chooses a
suitable plot; a steady-state spectrum does not need a kinetic surface.

Adapter `hardware_required(kind, settings)` and `selected_records()` are pure.
The panel creates the canonical operation before dispatching a worker and wraps
hardware calls in `.hardware_scope`. Its `StartSnapshot` contains that operation
plus detached scientific plan/preliminary data. Scientific adapters still own
planning, data compatibility, normalization, fit models, schemas and verified
cleanup/preservation. The executable compact adapter fixture and ownership,
cancellation and file-operation examples are in
`software/tests/test_compact_measurement_panel.py`.
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

## Read-only HF2 acquisition health

`HF2LIService.read_acquisition_health(*, reference_pll=0, input_indices=(0, 1))`
is an additive public device query using the connected service's existing
ownership checks. Indices are zero-based; no connection, configuration, stream,
subscription or synchronization changes occur. The JSON-compatible result uses
`schema_version: "hf2li-acquisition-health/1"` and a host `timestamp_utc`.

`reference_locked` is the selected PLL's lock when its enable state is true;
disabled, missing or unreadable enable state yields `None`. `clock_locked`
combines internal clock-generation PLL and digital clock-manager indicators,
whose documented polarity is inverted: zero means locked. Either known unlock
gives false, both known locks give true, otherwise the result is `None`.
`clock_lock_basis` names that scope. `external_clock_selected` reports the
configured source; `external_reference_locked` remains `None` because these
nodes do not independently establish physical external-reference lock.

`overload` covers only ADC clipping on the selected signal inputs: true if any
clips, false if all are known clear, otherwise `None`. `inputs` is keyed by
zero-based index strings and retains each `input_index`, `adc_clipped` and
`overload`. `reference` and `clock` retain component states. Successful binary
integer reads are retained in `nodes` by full path as `{type: "int", value: ...}`;
individual missing, malformed or failed reads are retained in `read_errors` by
path. Connection preconditions and ownership failures raise; SDK node read
failures become unknowns. Require explicit `is True` for a required lock and
`is False` for clear overload; do not treat unknown as permission to acquire.

These sequential reads cannot establish uninterrupted health over an
acquisition or detector/upstream electronics linearity. Meanings follow the
[HF2 node reference](https://docs.zhinst.com/hf2_user_manual/nodedoc.html).

## Compatibility checks

With the repository's UI test environment, run:

```powershell
python -m pytest software/tests/test_measurement_host_contract.py software/tests/test_measurement_host_contract_interchange.py software/tests/test_measurement_host_presentation.py
```

The contract fixtures install all six temporary package pairs simultaneously,
isolate optional failures, reject malformed factories and duplicate tabs, forbid
construction-time ownership, verify preference/plan/output/baseline/cancellation
separation, and exercise explicit device checks and standalone data exchange.
Ownership/process and existing Phase Scan suites provide the backend and native-format
regression checks. They use simulated instruments; passing them does not claim
live hardware commissioning.
