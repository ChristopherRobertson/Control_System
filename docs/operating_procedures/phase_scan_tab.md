# Phase Scan tab

The **Phase Scan** tab develops and runs finite room-temperature MbCO single-scan
phase-delay acquisitions. Planning controls and **Save Plan** do not access
hardware. **Capture Background**, **Capture Test Scan (pump OFF)**,
**Capture Inhibited Diagnostic**, **Start Scan**, and **Abort Scan** use the
connected acquisition workflow and its readiness checks. Output remains labeled
`EXPLORATORY_PROOF_OF_CONCEPT` and not for publication; software readiness does
not promote scientific evidence.

## Wiring and scheduling

Use the [default wiring](../../instrument/default_wiring_state.md). T660-1 A
supplies HF2LI DIO0, B supplies MIRcat TRIG IN, and C supplies T660-2 TRIG IN.
T660-2 runs the preloaded event frames: A FIRE, B Q-switch, C MIRcat Process
Trigger. Both D outputs and HF2LI DIO1 are unwired. T660-2 CLOCK OUT distributes
the separate 10 MHz reference to T660-1 and HF2LI.

Sample feeds HF2LI Signal 1 In (+)/PicoScope CHA and reference feeds Signal 2
In (+)/PicoScope CHB through separate adapter/tee branches. Both receivers stay
connected. MIRcat DB9 pin 2 Sweep Active feeds HF2LI DIO21 and PicoScope EXT;
DIO17 records the synchronized electrical pump event. Chemical time zero still
requires the measured electrical-to-optical correction and uncertainty.

The complete timing table is prepared before execution. One unpumped baseline
precedes the nominal phase series; repetitions repeat that phase series, not
the baseline. Per-frame channel OFF states suppress pump outputs in baseline
and inactive padding frames. Train count zero selects no additional pulses
and does not disable an enabled channel. Physical padding frames and logical scan counts
are recorded separately. Host polling does not set the frame or pulse times.

## Controls and derived values

- **T660-1 Trigger Rate** is fixed at 2 MHz for this implementation. MIRcat
  internal acceptance settings and the external trigger train are separate;
  the former does not establish the optical opportunity rate.
- **Start/Stop Wavenumber** and **Scan Speed** define nominal duration. Live
  acquisition needs calibrated trajectory bounds and observed timing.
- **Phase Delay** sets the nominal phase increment. **Before Pump** and
  **After Pump** define the reconstruction window. The calibrated trajectory
  determines the signed hardware phase range; it is not limited to `0..T`.
- **Frame Period** is fixed at 0.3 s, from a 600000 predivider of the 2 MHz
  event-input stream. This is a workflow-specific bound, not a general
  experiment cadence or proof of sample recovery.
- **Repetitions** repeats the complete phase series while retaining native
  identities. The preview budgets frame timing; initialization, returning,
  tuning, settling, and final-output completion can extend elapsed time.

A phase increment is not temporal resolution. Numeric pulse/duty limits and a
valid preview do not establish installed source, detector, or sample suitability.
**Save Plan** exports the versioned settings, counts, sequence, and planning
status. Changing settings invalidates the configured background when the
acquisition contract requires it.

## Acquisition and records

Live acquisition requires promoted timing qualification, verified T660 frame
capacity and LabOne resident-history capacity, exclusive device ownership,
MIRcat readiness, matching background/settings, and successful readbacks.
A missing prerequisite fails preflight before a finite sequence starts.

Detector records use bounded Sweep-Active-triggered LabOne histories plus a
separate small synchronized pump-event record. A consolidated native acquisition
retains the full records, frame table, requested/read-back settings, and partial
results on failure. PicoScope pulse diagnostics establish signal fidelity and
trigger/receiver behavior; they are not a mandatory missing-pulse retry recorder.

Ordinary one-pass reconstruction uses the calibrated trajectory, observed scan
and pump timestamps, and detector/reference/background normalization. It does
not perform automatic missing-pulse retries, coverage merging, or etalon removal.
Unsupported regions stay empty. Rejected and diagnostic records remain available.

**Latest Scan**, **Show Background**, and **Completed 3D Map** display the
corresponding retained products. Diagnostic coordinates and electrical pump sync
remain explicitly provisional where their physical calibration is unavailable.
The plot does not turn requested wavenumbers or small phase steps into calibrated
axes or resolution.

**Abort Scan** requests interruptible shutdown, closes emission, stops the frame
and probe timing, preserves partial native data, and reports restoration. Other
device controls respect exclusive ownership. Completion waits for final scheduled
outputs as well as frame-engine status and reconciles scan/pump/frame counts.

Scientific methods and claims remain in [EXPERIMENTS.md](../../EXPERIMENTS.md)
and the applicable campaign plans.
