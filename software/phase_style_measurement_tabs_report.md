# Phase Scan layout correction and stepped measurements

The Fixed Wavenumber Kinetics, Microsecond Stroboscopy, Nanosecond Stroboscopy, and Rapid Scan Phase Delay pages now use separate Nd:YAG Settings, MIRcat Settings, and HF2LI Settings sections in both single and dual detector modes. Phase Scan was inspected as the reference and was not edited by this task. Existing unrelated working-tree changes were preserved.

## Controls and layout

Nd:YAG Settings contains Repetition Rate, FIRE - Q-SWITCH Delay, and Wavelength. MIRcat Settings contains Start, Stop, Step Size, Repetition Rate, Pulse Width, and Current for fixed kinetics and both stroboscopy experiments. Rapid Scan Phase Delay retains Scan Speed because its acquisition uses continuous sweeps.

HF2LI Settings contains independent filter order, time constant, and sample rate controls for each applicable detector. Experiment-specific observation, delay, repetition, recovery, and aperture inputs remain in the experiment section. There is no T660 settings section in these measurement pages: their existing timing compilers derive timer programs from the experiment inputs.

Settings and plan file buttons scroll in the left pane. Acquisition actions remain outside that scroll pane. The right side retains derived settings, native run loading/export, and scientific plots. The eight pages are checked in the actual application shell at 1100 × 780 with Segoe UI 9.

## Stepped acquisition

Start is the first measurement wavenumber, Stop is the final measurement wavenumber, and Step Size is the positive spacing in cm⁻¹. Start 1940, Stop 1946, Step Size 2 produces measurements at 1940, 1942, 1944, and 1946. Descending ranges work in the same way. A single position uses equal Start and Stop values.

The generated positions feed the existing experiment planners and acquisition loops. Each position receives the configured kinetics or stroboscopy procedure. No continuous scan-speed setting is exposed on these three experiments. Decimal grid generation avoids floating-point endpoint loss. Zero/negative values and a Stop that does not fall on the selected grid are reported as validation errors.

Existing saved custom position lists remain intact until the range is edited; irregular lists display Loaded custom grid as Step Size. Saved plans retain generated positions and optional laser requests. Historical plans without the new optional laser_settings dictionary remain readable. Immutable operation snapshots are normalized before serialization.

## Device behavior

Optional laser requests are validated and passed through the existing owned acquisition paths. Current and pulse-width requests use existing instrument setters, limits, readback verification, and restoration. FIRE-to-Q-SWITCH requests feed the experiment timing planners. Requested repetition rates constrain cadence; observation and recovery can require slower events. The existing automatic selections remain available.

Pump wavelength is retained as requested run metadata. These procedures do not have an automatic OPO wavelength actuator; the wavelength control tooltip explains that the instrument must be set separately. This is not a claim that an entered wavelength has been physically verified.

## Verification

Checks cover exact section/control inventories, the inclusive range example, descending ranges, invalid endpoints, plan round trips, independent detector overrides, no device I/O while editing, connected preparation, operation ownership, native records, and restoration. Installed-adapter tests use injected in-memory instrument transports; no physical hardware was operated. Additional tests exercise new microsecond current/timing requests and nanosecond current/width requests, including restoration of the original laser settings.

The initial combined regression run passed 746 tests and exposed nine failures. The failures identified outdated label/scroll expectations, a hidden dual-page test setup, and the new dictionary's immutable-snapshot serialization issue; these were corrected. Final verification results are recorded below after rerunning the suite.

Final verification: the broad four-module/host regression completed with 756 passed and one layout-test failure from the test version collected before its last correction. The corrected layout test passed in both detector modes, and the complete focused UI/layout suite then passed all 78 tests. That correction makes the scrolling assertion include the spin box frame, rather than Qt's smaller focus rectangle. No acquisition failures remained. `git diff --check` passed for the four affected measurement modules.

## Explicit laser defaults (September 18 update)

All measurement pages with the shared laser sections now start with the Phase Scan MIRcat values: external repetition rate 2,000,000 Hz, external TTL pulse width 150 ns, and current 1,000 mA. Rapid Scan Phase Delay also starts at 10,000 cm⁻¹/s. Existing explicit saved selections and measurement position lists remain supported. Nd:YAG defaults are 10 Hz (also the UI maximum), 250 µs FIRE-to-Q-SWITCH delay, and read-only 540 nm wavelength.

Microsecond Stroboscopy uses direct numeric inputs for MIRcat repetition rate and pulse width; their Auto/Override dropdowns were removed. These values remain explicit during connected capability resolution, plan reload, and preference reload. HF2LI automatic choices remain independent. Restoring automatic settings resets the laser inputs to the specified defaults.

The Fixed Wavenumber installed adapter now retains the requested current when building its pulse command, checks installed current limits and readback, and restores the original current on cleanup. This also keeps preliminary-record compatibility consistent with the requested plan. Rapid Scan normalizes current and pump-delay requests before serialization and treats their native fields as derived values on reload.

Verification for the explicit MIRcat defaults: 129 focused UI, persistence, and installed-adapter tests passed; both default-shell layout tests also passed. A separate offline check verified all eight affected pages and the two direct Microsecond MIRcat numeric controls. No physical hardware was operated.

## HF2LI automatic startup update

Every active measurement page starts with independent Automatic HF2LI filter order, time constant, and sample rate selections. Overrides are non-editable dropdowns populated from accepted HF2LI capability values. Time-constant choices follow an explicitly selected filter order; unsupported historical requests remain visible but are not offered as new selectable values.

Application startup now forces one shared HF2LI capability enumeration, with the existing owned configuration/restoration procedure, then publishes detached choices to all twelve single/dual measurement pages. Tab switches and edits do not perform device reads. HF2LI choices are published independently of MIRcat/timer readiness. Per-tab Check device, Check connected device, and Read connected settings buttons were removed; the existing Instruments menu remains available for retrying startup failures or reconnecting instruments.

Automatic planning uses each experiment's inputs. Existing Phase Scan, Slow Scan, and Microsecond selection policies are retained. Fixed Wavenumber selects supported response/sampling values from its observation intervals; Rapid Scan uses the scan period; Nanosecond uses the sparse cycle and sampled pulse-area support. These are documented engineering defaults, not assertions of calibrated time or spectral resolution. Explicit overrides remain independent and are validated against the accepted settings.

## External trigger / internal optical correction

The Fixed Wavenumber, Microsecond, Nanosecond, and Rapid Scan MIRcat-section rate and width controls describe T660 external triggering. Internal MIRcat parameters are selected by the backend as a provisional 2,100,000 Hz / 142 ns pair, with separate vendor-limit checks and readback verification. Internal duty is 29.82%; an external 150 ns TTL width must not be used in that calculation. The internal rate must exceed the actual external cadence. No minimum headroom has been characterized by this change.

Microsecond now edits timing.probe_width_ns; Rapid Scan edits probe_pulse_width_s, displayed in nanoseconds. Prior explicit internal-width overrides are preserved as historical settings rather than silently treated as external requests. Fixed Wavenumber writes the requested external width to its T660 probe recipe; Nanosecond uses its probe command width. Sparse Nanosecond event cadence remains constrained by the experiment's cycle and recovery requirements.

Phase Scan already separates the external 2 MHz / 150 ns default and internal 2.1 MHz / 142 ns pair. Slow Scan uses internally triggered pulsed operation (or CW); its trigger mode has not been changed by this correction. No physical hardware was operated during these code changes.

Verification after external/internal separation: all 159 UI/planner/startup checks passed. Rapid Scan acquisition passed 69 tests, including internal-pair readback matching. The combined Fixed Wavenumber/Microsecond/Nanosecond transport run passed 139 tests initially; its three outdated test expectations were corrected and the affected cases passed targeted reruns (seven cases, with one final assertion correction rerun separately). Instrument tests cover command application, independent trigger settings, connected limits, readback refusal, preservation, and restoration using in-memory transports.

## Descending endpoint convention

Procedure range entry now requires Start wavenumber greater than Stop wavenumber, with that wording in the validation error. Step-based ranges descend using a positive Step Size. Rapid Scan's visible Start maps to the upper spectral bound and Stop to the lower bound; its internal lower/upper storage and bidirectional reconstruction are unchanged. Phase Scan and the MIRcat scan workflow reject equal or ascending endpoints. Slow Scan uses Stop consistently and places Current below Pulse Width and above Number of Scans.

Descending-range verification: the combined suite passed 224 checks with one skipped test and one outdated error-message assertion. After updating that assertion, the targeted suite passed 43 checks with one skip, including two added equal/reversed endpoint cases and the Slow Scan control-order assertion.


## Shared limits, summaries and continuous kinetics (September 19 update)

All active procedure pages use MIRcat current 250–1000 mA, pulse width 21–1005 ns and wavenumber 1639–2077 cm⁻¹ inclusive. Shared UI constraints and planner validation enforce these requests; narrower connected-device limits and duty/period checks still apply. External pulse controls remain separate from the backend internal 2.1 MHz / 142 ns policy. Manual MIRcat command validation also applies the current/width limits.

Derived summaries now use Phase Scan vocabulary consistently: sequence/acquisition window, relevant delay/cadence details, MIRcat, Nd:YAG where used, selected HF2LI, nominal effective resolution, preflight capacity and estimated completion. Slow Scan omits Nd:YAG. Fixed Wavenumber no longer counts its pre-pump interval twice. Nanosecond measurement estimates exclude separately requested blank/preliminary actions while preserving the campaign estimate in provenance. Fixed estimates include finite terminal completion, between-trial shot spacing and available overhead allowances. Unknown overhead is labeled as a lower bound. Expired estimates no longer display zero remaining while work continues. These remain engineering estimates, not measured startup/transfer benchmarks.

Fixed Wavenumber exposes Pre-Pump Acquisition, Post-Pump Acquisition, Pump Shots, Shot Delay and Trials, with a shared s/ms/µs/ns unit selector that preserves physical values. Shot Delay is editable only for multiple shots and cannot be shorter than 0.1 s or the selected Nd:YAG repetition-rate ceiling. Trials apply per wavenumber. The existing serialized events_per_position field represents trials; pump_shots explicitly represents shots within each continuous trial.

The backend starts the probe reference and MIRcat before subscribing to native recording. A finite T660 table schedules pre-first-shot time, FIRE/Q-switch pairs and post-last-shot capture; detected markers annotate and validate retained data instead of triggering recording. FIRE/Q-switch commands can occupy adjacent hardware frames. No extra host-recorded baseline is added. Recording stops before terminal verification and any between-trial idle time. Cancellation remains checked during terminal verification. Failed or interrupted recordings retain obtained native chunks and restoration evidence.

Each wavenumber has an equal-weight mean across trials on common observed time bins. Gaps are not interpolated; individual native traces, contribution counts, standard errors and quality flags remain retained. Nonstationary positive baselines can define a descriptive local relative signal and remain flagged; neither the mean nor its standard error establishes sample reset or independent biological replication. The default plot and CSV export show the trial mean. Single-shot recovery models are not applied to multi-shot trains.

Timing limits remain explicit: the continuous T660 program requires pre-pump time at least as long as FIRE-to-Q-switch (250 µs by default). Entering ns units does not establish nanosecond detector resolution. Automatic HF2LI selections use the shortest pre/post/shot-spacing interval and startup-supported values; each setting remains independently overridable. The summary reports the sampling interval and nominal filter response, and planning warns when a requested window has fewer than three samples. No physical instrument was operated for these changes.

Regression verification: 484 tests passed and one test was skipped across Fixed Wavenumber, Slow Scan, Microsecond, Nanosecond, Rapid Scan, Phase Scan and shared layouts. All 73 follow-up checks passed, covering the final mean CSV export, blank endpoint display, installed adapters and terminal-wait estimate. Layouts were rendered in the full shell at 1100×780 in both detector modes; scrolling stays within settings. Additional multi-shot tests verify command offsets, native pre/post support, finite shot counts, trial averaging, unit round trips, accepted-value HF2LI selection and limit endpoints.


## Fixed Wavenumber startup readiness correction

The timing demodulator now receives an automatic rate compatible with the active detector streams. Previously its idle readback (potentially 1.842 MHz) could exceed the shared 700 kSa/s acquisition budget and invalidate every acquisition action after startup, even though sample/reference automatic rates had already been reduced. Selection uses startup-supported rates when available, otherwise the existing binary-divider policy, with installed readback verification retained. Explicit detector overrides remain unchanged.

Disabled acquisition actions now show their validation reason next to the actions and in button tooltips instead of only inside the settings scroll. Empty or invalid wavenumber ranges still require correction; startup does not invent measurement positions. Regression: 100 tests passed, including single/dual high-idle-rate cases, accepted-rate selection and actual panel enablement after range entry. No physical hardware was operated.
