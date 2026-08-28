# MC-01 — MIRcat GUI process-trigger qualification: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Retained execution campaign | `system_recalibration_001` |
| Phase ID | `MC-01` |
| Phase run ID | `system_recalibration_001_MC-01_001` |
| Domain | Calibration/control qualification |
| Scientific disposition | `PASS — COMPLETE` |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Operator | Christopher Robertson |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; review remains pending. |
| Document version | `0.1.0` |
| Execution interval | Exact UTC bounds are retained in the action ledger and acquisition records; not restated as an inferred single interval. |
| Draft date | 2026-08-27 |
| Governing records | `plan.md`; `run_record.md`; `phase_manifest.json`; `action_ledger.csv`; `final_report.md` |
| Qualified software | MIRcat GUI `1.9.0.4`; firmware `3.1.0`; SDK API `2.4.1` |

## Executive synopsis

MC-01 qualified a single MIRcat External Step point/process sequence and the
runtime prerequisites needed to control it. The manufacturer GUI was used to
configure a one-transition 1905-to-1934 cm^-1 Step and Measure process, while a
T660-1 CHC 10 ms active-low command supplied the external process event. The
manual shutter stayed closed and no external laser-trigger pulse was supplied,
so GUI emission indicators represented an enabled gate/process state, not
evidence of optical pulses.

An inhibited control and three accepted bounded repeats passed. Each valid repeat
contained exactly one started-engine command, counter transition 0 to 1, and one
GUI point transition, followed by explicit Stop Scan. A raw HF2LI DIO diagnostic
correlated events but did not establish a persistent ready level or a universal
host delay. SDK set/readback control of Process Trigger Mode passed under
exclusive ownership, with mandatory runtime prerequisites retained.

## 1. Purpose — WHY

PT-01 established the electrical route, but did not show how the MIRcat process
state responded to an external command or how GUI/SDK ownership, configuration
persistence, terminal stopping, and faults behaved. MC-01 addressed those
control-system questions before any automated optical acquisition could rely on
the sequence.

The scope was one CH-00-retained point/process transition. It excluded spectral-
accuracy, power, detector, sample, and optical-performance claims. The manual
shutter and absent external pulse trigger enforced a nonemitting boundary.

## 2. Procedure performed — HOW

### 2.1 Entry state and retained configuration

The MIRcat was identified as model `MIRcat-QT-Z-2100`, serial `10524`. The
qualified state used QCL1, Pulsed, 2 MHz, 150 ns, 1000 mA, 19 C; External Step
process mode; External Trigger pulse mode; and a one-scan Step and Measure from
1905 to 1934 cm^-1 in one 29 cm^-1 transition. Infinite and Keep Laser On Between
Steps were off. T660-1 CHC was the only permitted process-command output.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | Physical inhibits, closed shutter, ownership conditions, GUI/firmware identity, initial configuration export, Favorites, exclusions, and initial Scan state were recorded. | Freeze provenance and safety before changing a GUI setting. | `operator_confirmations.md`; `action_ledger.csv`; configuration exports | Entry gate completed. |
| 2 | Candidate QCL, timing, process, pulse, and Step and Measure settings were entered and saved in the GUI. | Create the single bounded configuration under test. | GUI screenshots/exports; `conditions.csv`; operator records | The retained 1905-to-1934 cm^-1 configuration was established. |
| 3 | With interlock inhibiting and MIRcat unarmed, Start Scan and arm behavior were observed. | Negative control: an unsafe/unready state must refuse operation without a process pulse. | `MC01-CONTROL-001`; `expected_observed.csv` | Start Scan requested arming; arm requested interlock/keyswitch; no scan or command occurred. |
| 4 | Under the released active gate, the process was started and one T660-1 CHC negative 10 ms, 50 ohm command was issued with the timing engine running. | Test one-command/one-transition behavior. | `MC01-REPEAT-001-RETRY1`; T660 status; GUI observations | Counter changed 0 to 1 and GUI advanced once to 1934 cm^-1. |
| 5 | The terminal point was explicitly stopped and the sequence was repeated twice under the same bounded conditions. | Test repeatability and terminal-state behavior. | `MC01-REPEAT-002`; `MC01-REPEAT-003`; operator confirmations | All three accepted repeats produced one transition and required explicit Stop Scan. |
| 6 | Raw HF2LI DIO was captured during a diagnostic process event. | Determine whether DB9 status outputs supplied usable correlation or a persistent ready state. | `MC01-DIO-DIAGNOSTIC-002`; raw CSV; diagnostic analysis | DIO21 gave two single-sample assertions; DIO22 remained low. No persistent ready level was established. |
| 7 | Configuration export/import behavior was tested. | Determine which state could be restored from `.mcfg`. | Native exports; `operator_confirmations.md`; `final_report.md` | Serialized settings restored, but Process Trigger Mode did not and must be set/read back each run. |
| 8 | Under exclusive SDK ownership, Process Trigger Mode was set/read External and restored/read Internal without arm, tune, scan, or emission commands. | Establish bounded SDK automation eligibility and restoration behavior. | `sdk_control_qualification.json`; `sdk_automation_decision.md` | SDK qualification passed. |
| 9 | Initial configuration was restored; MIRcat and T660s were returned to their final states and ownership was released. | End without persistent control or output changes. | `restoration_confirmation.json`; final safe-idle records | MIRcat powered down, shutter closed, interlock inhibiting, default wiring restored, and T660 safe idle passed. |

### 2.3 Controls, exclusions, and analysis

The inhibited control tested refusal before the accepted repeats. For each
repeat, command-count and GUI-state evidence were compared with the expected
one-command/one-transition outcome. The DIO diagnostic retained 14,596 samples
over 4.056576 s. The two DIO21 assertions were separated by 0.724319086 s, with
a conservative two-edge discretization bound of 0.000555886 s; this was treated
as descriptive correlation only because device/host observations did not share a
qualified common clock.

### 2.4 Deviations, rejected attempts, and restoration

An engine-stopped `TRIG:EXEC` attempt produced no count increment or MIRcat
transition and was correctly rejected as an invalid command setup. Two failed
HF2 export attempts remain partial/rejected evidence. They were not substituted
for the three accepted repeats. A terminal process required explicit Stop Scan.
No fault remained after restoration.

## 3. Results — WHAT

| Test | Population/result | Outcome |
| --- | --- | --- |
| Inhibited control | 1 control; no scan, process pulse, or transition | PASS |
| Bounded active repeats | 3 accepted repeats; each one command and one 1905-to-1934 cm^-1 transition | PASS |
| Terminal behavior | Explicit Stop Scan required; no terminal fault | PASS |
| Raw DIO diagnostic | 14,596 samples over 4.056576 s; DIO21 event assertions; DIO22 no edges | BOUNDED/PASS for correlation only |
| SDK Process Trigger Mode | External set/read; Internal restore/read | PASS |
| Configuration persistence | Serialized settings restored; Process Trigger Mode not serialized | BOUNDED |

The accepted categorical results and restoration criteria passed. The recorded
scientific disposition is complete. This retrospective writeup is not yet
reviewer-accepted.

## 4. Implications, caveats, and claims

MC-01 supports one-command/one-process control for the exact retained GUI,
firmware, SDK, configuration, and state sequence. SDK automation is eligible only
when the GUI is closed, ownership is exclusive, Process Trigger Mode is set and
read back every run, the MIRcat waiting/tuned state is confirmed before each
command, T660-1 CHC is staged exactly as qualified, and terminal Stop Scan is
verified.

The phase does not support a fixed host delay, a sustained DIO21 ready-state
interpretation, optical emission, spectral accuracy, power, detector response,
or general behavior across other GUI/firmware versions or scan configurations.
The GUI's green indicators cannot be cited as proof of emitted optical pulses.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Chronological operator/control actions | `action_ledger.csv`; `operator_confirmations.md` | Use timestamps and stable acquisition IDs; summarize repetitive commands. |
| Expected/observed outcomes | `expected_observed.csv`; `measurements.csv` | Account for the control and all three accepted repeats. |
| DIO interpretation | Raw diagnostic CSV/status; `dio_diagnostic_analysis.md`; `uncertainty_ambiguity.md` | Do not promote the observed interval to a universal delay. |
| SDK eligibility | `sdk_control_qualification.json`; `sdk_automation_decision.md` | Preserve every mandatory runtime prerequisite. |
| Rejected/partial evidence | `exclusions.csv`; phase indexes | Retain the engine-stopped and export failures. |
| Restoration | `restoration_confirmation.json`; final readbacks | Confirm MIRcat ownership release and T660 safe idle. |

Minimal computational reproduction reads the indexed control/repeat status files,
checks counter and GUI-transition outcomes, and reanalyzes the raw DIO diagnostic
without modifying eligibility. Hardware repetition is not authorized by this
document.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Reconcile action ledger, repeats, and exclusions. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Review state-based automation boundary. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
