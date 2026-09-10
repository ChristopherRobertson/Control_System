Build the shared experiment host for independent, parallel-developed measurement tabs

Work in the Control_System repository and implement the one-time shared foundation needed to add the remaining EXPERIMENTS.md methods without having each task edit the same application files. This task owns integration and common interfaces; it does not implement new scientific experiment engines.

The existing Single Scan Phase-Delay Reconstruction and its dual-detector version work well and are the behavioral reference. Preserve their current tabs, controls, timing, saved-data compatibility and measurements. Read applicable AGENTS.md instructions, EXPERIMENTS.md, software/control_app/ui/main_window.py, ui/app.py, ui/contracts.py, workflows/state_machine.py, the regular_phase_scan* and dual_detector_phase_scan* modules, phase_scan_widget.py, phase_scan_surface.py, existing device services and both operating procedures.

The starting checkout contains important working changes that may not be committed. Inventory and preserve them. Establish a reproducible development baseline containing the current working Phase Scan code and fixes before the six feature tasks branch. Do not base new work on an older HEAD that lacks those files. Do not reset, discard or silently omit unrelated changes. Perform this foundation work in an isolated checkout when appropriate and integrate/checkpoint its completed interface before the experiment tasks start from it.

Deliver actual integration code, tests and a stable developer contract. Do not stop at a registry proposal. Use a small measurement host, not a resurrection of Experiment Builder, Configured Workflow, a generic user-authored workflow language or another scheduling framework.

Own these shared areas in this task:
- software/control_app/measurement_host/ for the host API, registry, ownership, shared presentation and narrow data-exchange helpers;
- software/control_app/measurement_modules/__init__.py and any package-level discovery infrastructure;
- main_window.py, ui/app.py, state_machine.py and necessary backward-compatible shared-service/lifecycle changes;
- host-specific and existing regression tests, global dependency updates only when justified, and the existing canonical architecture/operating documentation.
Do not create the six feature packages; their tasks will own those paths independently.

Freeze a small registration contract with these semantics before feature development:
- Discover repository modules under software/control_app/measurement_modules/<experiment_id>/registration.py. Each module supplies a descriptor with api_version, immutable experiment_id, display order and create_tabs(context). No feature must edit a central registry or package-level import list.
- Each descriptor creates exactly two handles, instance_id "<experiment_id>:single" and "<experiment_id>:dual", with unique top-level tab titles. A handle supplies the QWidget, command_running(), close_blockers(), request_abort(reason), output_location_changed(path), and instrument_state_changed(change), plus a busy/state notification suitable for the existing Qt lifecycle.
- Define the concrete dataclasses/protocols, callable signatures, version checks and compatibility fixtures in the host. Imports, registration and widget construction perform no hardware I/O. Discovery is deterministic and lazy where appropriate; one absent SDK or broken optional module must not prevent working tabs from opening. Report duplicate IDs, invalid factories and incompatible APIs clearly.
- Provide an injected, scoped context containing configuration access, real/simulated device factories, promoted-instrument-bundle access, a save-root provider, namespaced preferences, instrument ownership and application lifecycle hooks. It must not expose an unscoped mutable preference/session singleton.
- Enforce measurements/<experiment_id>/<mode>/v1/ preference namespaces, unique plan/run identity and isolated output paths. Freeze settings, selected calibration/sample records, save destination and ownership at operation start. A later tab change or save-location edit must not retarget an active run.
- Publish the exact interface through module documentation and executable compatibility examples/tests. Keep repository-wide architecture in the existing canonical README rather than creating a competing repository contract.

Implement one authoritative hardware coordinator for the whole coupled spectrometer:
- Acquire exclusive ownership atomically before any actual discovery, connection/configuration, alignment, acquisition or restoration. Protect against competing tabs and separate app/task processes on Windows, not only two threads. Use an appropriate OS-level lock plus owner identity/fault provenance; an in-memory busy flag is insufficient.
- Token identity prevents a delayed callback from one operation releasing another operation's ownership. Persistent alignment/emission sessions retain ownership beyond their initiating command. Do not make two experiments share live SDK sessions, subscriptions, timing tables or mutable settings.
- Retain ownership through safe shutdown/restoration and required data preservation. If restoration is unverified, leave an actionable fault state rather than advertising free, ready hardware. A crashed process or expired lock is not proof of physical safe idle. Provide the existing explicit recovery path without automatically firing or repeating an experiment.
- Integrate legacy manual MIRcat, T660, Nd:YAG and iris controls, both existing Phase Scan runners, and automatic capability checks. Enforcement is in backend entry points as well as UI state. Analysis, plan editing, loading data and simulations remain independent of hardware ownership.
- Normal Stop/Abort targets only its owning handle. App close queries every registered handle for blockers, and emergency stop requests cancellation of every registered live hardware operation without cancelling unrelated offline analysis or simulation. Owner cleanup/emergency operations must still be permitted while ordinary commands are blocked. Inspect current hardcoded emergency_stop and shutdown routing; ensure both existing detector modes and all future tabs have a verified lifecycle. Preserve every partial/native/restoration record.
- Keep intentional cancellation distinct from runtime failure. A failed status callback must not prevent safety cleanup or native saving, while a real cleanup/save failure must remain visible. Do not claim safe shutdown merely because a worker exited.

Adapt the existing Phase Scan tabs into this host without changing their experiment logic or data meaning. Preserve their visible names, established preference values through a deliberate compatibility adapter, per-mode baselines/review, automatic discovery behavior when ownership is available, and existing saved plans/runs. Add generic lifecycle wiring so future registrations need no main-window/state-machine edits. Preserve device-tab order and make all tabs accessible when many experiments are installed.

Extract or expose reusable presentation components with explicit injected scientific adapters: nonblocking workers, concise settings/summary layout, validation and status, Save/Load Plan, native-run loading, guided preliminary/review/start workflow, toolbar-only plot controls, linked numeric slice controls with held-arrow updates, New run, data export and run progress. Do not turn PhaseScanWidget's dual_detector branch into a growing switch on every experiment. Measurement-specific planners, normalization, readiness, fit models and data schemas remain in the owning module. Time display units/precision must support nanoseconds, microseconds and long recovery as appropriate; a steady-state spectrum need not show a 3-D kinetic surface.

Provide narrow versioned interchange for accepted sample spectral selections and instrument-state notifications so an experiment can consume selected windows/uncertainties and condition identity as data without importing another feature package. Preserve producer/source identity and distinguish sample-derived records from promoted instrument calibration. Consumers can validate standalone records with host helpers; installing or running the Slow Scan package must not be a software prerequisite. Any invalidation event names its device/configuration changes and recipients; it must not silently mutate another tab's settings.

The six independent feature packages and planned tab pairs are:
- steady_state_slow_scan: Slow Scan / Dual-Detector Slow Scan
- fixed_wavenumber_kinetics: Fixed-Wavenumber Kinetics / Dual-Detector Fixed-Wavenumber Kinetics
- nanosecond_stroboscopy: Nanosecond Stroboscopy / Dual-Detector Nanosecond Stroboscopy
- microsecond_stroboscopy: Microsecond Stroboscopy / Dual-Detector Microsecond Stroboscopy
- repeated_rapid_scan: Repeated Rapid-Scan Phase Delay / Dual-Detector Repeated Rapid-Scan Phase Delay
- single_pump_scan_burst: Single-Pump Scan Bursts / Dual-Detector Single-Pump Scan Bursts.
Use these stable IDs in compatibility examples. No production feature may import a sibling feature. Single and dual implementations may share pure code within their own package but never mutable runner/review/baseline state.

Verify with simulated instruments and synthetic dummy modules:
- zero hardware access on import, discovery and construction; explicit device checks acquire ownership;
- both legacy Phase Scan modes preserve current behavior and saved-data compatibility;
- independently installed packages register two unique tabs without editing central files, and missing/broken optional modules are isolated;
- settings, plans, baselines, save roots and cancellation remain separate between modules and modes;
- competing worker starts, manual commands, separate processes, persistent alignment, capability discovery and late completion callbacks cannot cross-talk;
- normal completion, preparation abort, acquisition abort, application close, emergency stop, data-save failure, callback failure and restoration failure have truthful, complete outcomes;
- held-arrow plots, typed coordinates, toolbar behavior, scientific-unit displays, layout and New run retain the working interaction quality.
Exercise the complete current software suite and targeted ownership/process tests without contacting hardware. Do not add hash-matching operational gates or promote a calibration/campaign phase.

Finish by reporting the frozen API and file ownership, the baseline to use for all six worktrees, the test results, any explicit live commissioning limitations, and concise launch/integration instructions. All six experiment tasks should then need only their own package, tests and operating procedure. The final acceptance check is that independently developed packages can be installed together without integration edits or a change to the working Phase Scan experiment.
