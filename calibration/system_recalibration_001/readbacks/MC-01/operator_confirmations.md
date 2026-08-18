# MC-01 operator confirmations

## Gate 1 item 1 - optical emission inhibits

- Confirmation UTC: `2026-08-17T19:09:22.4973017Z`
- Operator: Christopher Robertson
- Observation: "The interlock provides this control as well as a manual
  shutter on the laser that has been closed, both prevent the laser from
  firing."
- Recorded state: installed interlock inhibits laser firing; manual MIRcat
  shutter is closed; optical emission remains unauthorized.
- Decision: `PASS_ITEM_1_CONTINUE_TO_ITEM_2`

## Gate 1 item 2a - physical armed indicator availability

- Observation UTC: `2026-08-17T19:10:42.6874477Z`
- Operator: Christopher Robertson
- Observation: no armed-status indicator is present on the installed system;
  armed state must be obtained from the manufacturer GUI or SDK.
- Disposition: `NOT_SHOWN_ON_PHYSICAL_SYSTEM`.
- Boundary decision: the SDK `isArmed` alternative was not used because MC-01
  prohibits SDK connection. Continue through manufacturer-GUI ownership.

## Gate 1 item 2b - manufacturer GUI initially closed

- Observation UTC: `2026-08-17T19:11:52.4566677Z`
- Operator: Christopher Robertson
- Observation: MIRcat manufacturer GUI is closed.
- Disposition: `CONFIRMED_GUI_CLOSED`; competing SDK/control clients remain to
  be confirmed before opening the manufacturer GUI.

## Gate 1 item 2c - competing clients closed

- Confirmation UTC: `2026-08-17T19:12:20.8805315Z`
- Operator: Christopher Robertson
- Observation: no non-GUI MIRcat clients are open.
- Codex confirmation: no SDK client or MIRcat device connection was opened by
  Codex during MC-01.
- Decision: `EXCLUSIVE_GUI_OWNERSHIP_AVAILABLE`.

## Gate 1 item 2d - manufacturer GUI opened

- Observation UTC: `2026-08-17T19:15:47.5767323Z`
- Operator: Christopher Robertson
- Observation: MIRcat manufacturer GUI is open.
- Disposition: `GUI_OPEN`; connection success and exact initial status remain
  unobserved and are not inferred.

## Gate 1 item 2e - initial GUI status screenshots

- Evidence received UTC: `2026-08-17T19:17:17.9522588Z`
- Operator: Christopher Robertson
- GUI header: `Connected to MIRcat S/N 10524`.
- Status observations: Interlocks green; Key Switch Status green; Connected
  green; Emission indicator dark; System Fault indicator dark; action controls
  read `ARM LASER` and `TURN EMISSION ON`.
- Bounded interpretation: the GUI is connected under manufacturer-GUI
  ownership and presents emission as off. Armed state is not claimed solely
  from indicator color; the `ARM LASER` action label is retained as evidence
  that arming has not been commanded in MC-01.
- Initial Tune display: `1850.00 cm-1`; this is outside the CH-00-retained
  1885-1980 cm^-1 region and is not accepted as the MC-01 point.
- Initial settings: Process Trigger Mode `Use Internal Step Mode`; Pulse Mode
  `Use External Trigger Mode`; QCL1; Pulsed; 2000000 Hz; 150 ns; 1000 mA;
  19.00 C; duty cycle 30%; `Disable Channel` unchecked; parameter logging
  enabled. These are observed initial settings, not accepted MC-01 settings.
- Decision: `PASS_CONNECTION_EMISSION_OFF`; external process-trigger mode and
  an already retained point/configuration must be selected only at later gates.

## Gate 1 item 3 - GUI and firmware provenance

- Evidence received UTC: `2026-08-17T19:18:36.0408156Z`
- Manufacturer GUI/software version: `1.9.0.4`.
- Controller firmware version: `3.1.0`.
- Model: `MIRcat-QT-Z-2100`; serial: `10524`.
- Manufacture date: `2024.02.06`; displayed hours of operation: `189`.
- Motion model type: `6`; motion firmware version: `N/A`; motion hardware
  version: `N/A`.
- Ownership: manufacturer GUI connected exclusively; no SDK client used.
- QCL1 capability limits shown on the About page are retained as GUI metadata,
  not classified as campaign-measured performance.
- Decision: `PASS_GUI_FIRMWARE_PROVENANCE`.

## Gate 1 item 4 - initial configuration export

- Operator confirmation: native initial export completed as
  `mircat_initial_configuration.mcfg` at the requested MC-01 raw path.
- Evidence inspection UTC: `2026-08-17T19:34:57.4841889Z`.
- Native size: `4293` bytes; format is an opaque manufacturer `.mcfg` binary.
- Disposition: `PRESERVED_PRECHANGE_BASELINE`. The file is a restoration and
  provenance reference; no hash or checksum match is an operational gate.

## Gate 1 item 5 - Favorites inventory

- Evidence received UTC: `2026-08-17T19:36:00.3161934Z`.
- Visible Favorites: `Default` and `PowerOffCfg` only.
- No Favorite corresponding to `CHCFG-POINT-RAREPUMP-v1` exists.
- Decision: `NO_RETAINED_FAVORITE_AVAILABLE`; neither visible Favorite was
  recalled, edited, erased, regenerated, or overwritten.
- Requirement-brief context: HRP regions near 1905 and 1934 cm^-1 and MbCO A1
  near 1943-1945 cm^-1 are planning/claim anchors, but CH-00 explicitly leaves
  numeric accepted settings pending dependencies. The displayed 1850 cm^-1
  alignment value is explicitly not a biological setting.

## Gate 1 item 6a - T660-1 channel D exclusion

- Confirmation UTC: `2026-08-17T19:36:58.3735057Z`.
- Operator: Christopher Robertson.
- Observation: "CH D will ALWAYS be disconnected unless I tell you otherwise."
- Recorded state: T660-1 channel D is disconnected and excluded for MC-01.
- Standing-condition rule: retain this state without repetitive confirmation
  unless the operator explicitly reports a change. A reported change requires
  safe-idle re-verification before further transition or testing.

## Gate 1 item 6b - MIRcat DB9 pin 5 exclusion

- Confirmation UTC: `2026-08-17T19:37:40.1721028Z`.
- Operator: Christopher Robertson.
- Observation: MIRcat DB9 pin 5 is always disconnected unless the operator
  explicitly reports otherwise.
- Recorded state: pin 5 is disconnected and excluded for MC-01.
- Standing-condition rule: retain this state without repetitive confirmation;
  a reported change requires safe-idle review and is outside current scope.

## Gate 1 item 6c - default-wiring semantic directive

- Operator directive: `default wiring restored` means T660-1 channel D is
  disconnected, MIRcat DB9 pin 5 is disconnected, and MIRcat DB9 pins 6 and 8
  are unused.
- Standing-condition rule: do not ask about these items again unless the
  operator explicitly dictates that something changed.
- Repository authority: `docs/default_wiring_state.md`.

## Gate 1 item 7 - initial Scan page

- Evidence received UTC: `2026-08-17T19:51:14.3897481Z`.
- Initial Scan Mode: `Sweep Mode`.
- Initial displayed sweep: start 2049.0 cm^-1, stop 1650.0 cm^-1, speed
  40.0 cm^-1/s, one scan, both-directions unchecked, infinite unchecked.
- Disposition: `OUTSIDE_MC01_SCOPE_NOT_STARTED`. This is continuous-sweep
  configuration evidence only and is not the CH-00-retained point/process
  topology.

## Gate 1 item 8 - available Scan modes

- Evidence received UTC: `2026-08-17T19:54:23.8171782Z`.
- Available modes: `Sweep Mode`, `Step and Measure Mode`, and
  `Multi-Spectral Mode`.
- Selection decision: `Step and Measure Mode` is the only available mode that
  matches CH-00 `TOPO-POINT-01` discrete point/process behavior.
- Exclusions: `Sweep Mode` is the separate continuous topology;
  `Multi-Spectral Mode` is outside MC-01 and must not be exercised.

## Gate 1 item 9 - Step and Measure initial state

- Evidence received UTC: `2026-08-17T19:55:28.9115361Z`.
- Selected mode: `Step and Measure Mode`.
- Inherited values: start 2049.0 cm^-1, stop 1650.0 cm^-1, step size
  10.0 cm^-1, one scan, infinite unchecked.
- `Keep Laser On Between Steps` is checked.
- Disposition: `SUPERSEDED_UNSAFE_FOR_MC01`; no scan was started. The keep-on
  option must be cleared before any point/process test configuration is built.

## Operator interaction convention

- Directive UTC: `2026-08-17T19:57:45.8107402Z`.
- Operator is the graduate student who designed the system.
- Routine GUI configuration instructions are issued as ordered batches with a
  compact verification-evidence list rather than one click per exchange.
- Safety-critical stops remain at configuration acceptance, inhibited control,
  bounded active electrical repeats, and restoration/readback boundaries.

## GUI persistence behavior

- Operator correction UTC: `2026-08-17T19:59:39.0928411Z`.
- MIRcat Laser Settings changes must be committed with `Save Settings` before
  Export Configuration or the export does not include the updated values.
- MC-01 candidate workflow therefore saves the reviewed non-emitting settings
  before exporting. Saving settings does not authorize arming, emission, scan
  start, or a manual step.

## Gate 1 item 10 - candidate configuration evidence

- Evidence received UTC: `2026-08-17T20:04:16.8067039Z`.
- Laser Settings: `Use External Step Mode`; `Use External Trigger Mode`;
  parameter logging enabled; emission presented off.
- Step and Measure: 1905.0 to 1934.0 cm^-1; step 29.0 cm^-1; one scan;
  infinite off; `Keep Laser On Between Steps` cleared.
- Native export: `mircat_mc01_candidate_configuration.mcfg`, 4293 bytes;
  GUI message `MIRcat configuration exported successfully.`
- Wavelength Trigger Start/Stop changed from initial 2050.00/2050.00 to
  1905.00/1934.00. Classification as automatic coupling or intentional
  operator change remains `USER_INPUT_REQUIRED`; Wavelength Trigger Pulse Mode
  is not selected, so these fields are not used to trigger MC-01.
- Decision: `CANDIDATE_CONFIG_RECORDED_PENDING_TRANSITION_GATE`.

## Inhibited control - mandatory non-emitting boundary result

- Evidence received UTC: `2026-08-17T20:11:33.0767420Z`.
- Operator correction: clicking `Start Scan` with the interlock off throws the
  error shown in the first screenshot.
- Exact Start Scan error: `Please ARM the laser prior to trying this operation.`
- Exact ARM error with interlock off: `Please make sure Interlock is in place
  and keyswitch is on and retry this operation.`
- Expected: with interlock inhibit active, emission off, T660-1 CHC disabled,
  and laser unarmed, no point/process scan begins and no point transition occurs.
- Observed: GUI rejected Start Scan before tuning/scan start; ARM was also
  rejected because the interlock was off. No process-trigger pulse was issued,
  no scan began, and no emission occurred.
- Decision: `PASS_INHIBITED_CONTROL_AND_BLOCK_ACTIVE_REPEATS`.
- Blocker: three qualified repeats, one-command/one-process behavior, state
  transitions, and post-Sweep-Active delay require a started Step and Measure
  process. The GUI requires arming first; the manufacturer manual describes
  Step and Measure operation as turning on/firing. Removing the inhibit and
  arming is outside the non-emitting authorization. MC-01 therefore stops at a
  genuine documented blocker rather than emitting.

## Restoration - import behavior and runtime-setting limitation

- Evidence received UTC: `2026-08-17T20:20:19.4926679Z`.
- Exact import message: `MIRcat configuration imported successfully. MIRcat
  Control Panel will now exit, and the laser will power down.`
- The MIRcat was powered on again after the successful import so the restored
  state could be inspected; it remained unarmed and non-emitting.
- Export/import restoration confirmed Wavelength Trigger Start/Stop returned
  to `2049.18 cm^-1`. The earlier 1905/1934 values were intentionally changed
  to verify this exact restoration behavior.
- `Use External Step Mode` remained selected after import. Inference from the
  observed export/import behavior: Process Trigger Mode is not serialized in
  the `.mcfg` file and must be set explicitly through the manufacturer GUI (or
  SDK in a separately eligible/authorized workflow) for each use.
- Restoration is not complete until Process Trigger Mode is manually returned
  to the initial `Use Internal Step Mode` and saved.

## Continuation authorization

- Recorded UTC: `2026-08-17T20:32:17.9445320Z`.
- Authorization ID: `MC01-AUTH-002`.
- Operator authorizes the controlled emission and MIRcat SDK controls necessary
  to complete MC-01. The authorization persists across task/session boundaries
  until MC-01 completion, a new blocker, or explicit revocation.
- Scope remains MC-01 only. No later phase, sample, CO, biological work,
  T660-1 channel D, or MIRcat DB9 pin 5, 6, or 8 is authorized.

## Active-repeat and final-restoration confirmations

- The operator confirmed three accepted scans each waited for one process
  signal, transitioned exactly once to 1934 cm^-1, and were stopped explicitly.
- After Stop Scan, the GUI emission state was off, QCL and current wavenumber
  were N/A, no fault appeared, and the laser remained armed until disarmed.
- The manual shutter remained closed throughout. T660-2 sent no external
  laser-trigger pulse; the HF2LI captured DIO only. No optical pulse or
  delivered beam occurred.
- The operator disarmed the laser and closed the GUI. The preserved initial
  configuration imported successfully and powered the MIRcat down.
- The interlock was then disabled/inhibiting. Default wiring was restored under
  the standing definition: T660-1 CHD disconnected, DB9 pin 5 disconnected,
  and DB9 pins 6 and 8 unused/unwired.
