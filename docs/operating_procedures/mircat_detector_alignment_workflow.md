# MIRcat Detector Alignment Workflow

This document covers the UI-controlled detector-alignment workflow. It is a UI,
timing, and hardware-operation artifact retained for instrument setup. Its
outputs are operational records unless an approved campaign phase explicitly
imports them.

## Purpose

Use the MIRcat tab to initialize the MIRcat, configure the probe laser for a
continuous internal alignment pulse train, and configure the HF2LI for detector
monitoring in LabOne Plotter. The default alignment mode does not require
T660-2. The run continues until the operator presses `Emission Off` in the UI.

## Detector wiring

Use the [default detector split connections](../../instrument/default_wiring_state.md).
Each signal passes through its own female-to-female BNC adapter ->
male-to-two-female BNC tee: detector 1 (sample) feeds HF2LI Signal 1 In (+) and
PicoScope CHA; detector 2 (reference) feeds HF2LI Signal 2 In (+) and PicoScope
CHB. Both PicoScope channels therefore show detector waveforms, not T660
trigger waveforms, with this wiring. Leave both
receivers connected while monitoring in LabOne, even if the PicoScope is not
recording. The Arduino MUX remains bypassed; changing a branch or receiver
termination changes the installed load and must be recorded and reviewed.

## UI Defaults

- Wavenumber: `1850.0 cm^-1`
- QCL: `1`
- Pulse mode: internal by default; external trigger only when `Use T660 Timing` is checked
- Pulse repetition rate: `2_000_000 Hz`
- Pulse width: `150 ns`
- Current: `1000.0 mA`
- Use T660 Timing: unchecked by default
- HF2LI preset: `detector_alignment_internal`
- T660 recipe: `instrument/recipes/mircat_detector_alignment_2mhz.yaml` only when `Use T660 Timing` is checked
- LabOne live display: use the LabOne Plotter tab directly

## Ordered Start Sequence

The `Start Alignment` button runs `mircat.start_detector_alignment` and returns
after the hardware is started, leaving the UI responsive. It is intended to be
self-contained, but it also preserves a working manual MIRcat session: if the
manual `Initialize`/`Arm`/`Direct Tune` buttons were used first, Start Alignment
adopts that initialized session instead of closing it.

1. Initialize MIRcat if it is not already initialized, clear system error, and
   confirm interlock/key state.
2. Stop any MIRcat scan and cancel manual tune if active.
3. Apply MIRcat QCL pulse settings at `1850.0 cm^-1`, `2 MHz`, `150 ns`, and
   `1000 mA`, then save the requested settings and MIRcat readbacks.
4. Configure MIRcat internal pulse timing unless `Use T660 Timing` is checked.
5. Arm MIRcat once and poll `IsLaserArmed` until the SDK readback confirms the
   armed state.
6. Wait for TEC readiness, re-confirm the armed state, tune, and wait for tuned
   state.
7. Reassert and read back MIRcat pulse mode after tuning.
8. Apply HF2LI preset `detector_alignment_internal` and export the settings snapshot.
   This keeps demodulators `0` and `3` in continuous data-transfer mode
   (`/demods/{0,3}/trigger = 0`) and sets HF2LI oscillator 0 to `2 MHz`.
9. Open MIRcat emission after explicit UI safety approval. In internal mode,
   MIRcat should fire immediately after the gate opens.
10. If `Use T660 Timing` is checked, apply
   `instrument/recipes/mircat_detector_alignment_2mhz.yaml` to start continuous T660-2
   timing:
   - CHA -> HF2LI DIO0 external reference
   - CHB -> MIRcat TRIG IN
   - CHC -> HF2LI DIO1 optional Plotter UI trigger route

## HF2LI And LabOne Plotter

The default preset `detector_alignment_internal` configures detector input
monitoring for the LabOne Plotter without T660-2. It does not create a LabOne
DAQ module and the UI does not replicate the LabOne plotter.

- PLL disabled for default internal alignment mode
- HF2LI oscillator 0: `2_000_000.0 Hz`
- Demodulators: `0` for Signal Input 1, `3` for Signal Input 2
- Time constant: `0.001 s`
- Sample rate: `2000.0 Sa/s`
- Continuous demodulator transfer: `/demods/0/trigger = 0` and
  `/demods/3/trigger = 0`

Open LabOne at `http://127.0.0.1:8006`, select the HF2LI, open Plotter, and add:

- `Demodulators/1/Sample/R`
- `Demodulators/4/Sample/R`

The detector traces are then rendered by LabOne using the shared LabOne Data
Server session. For flat live alignment traces, leave demodulator triggering
continuous. If a triggered display is needed, configure the Plotter trigger in
the LabOne UI to use DIO1 rising; do not set the demodulator trigger nodes to
DIO1, because that gates the sample stream and can produce shared dips in both
channels.

## Emission On But No MIRcat Firing

If `Emission Gate` reads ON but the MIRcat is not firing:

1. Press `Emission Off` in the UI before touching cables.
2. Confirm T660-2 CHB is physically connected to MIRcat `TRIG IN`.
3. Confirm the T660 alignment readback shows T660-2 channel `B` enabled.
4. Confirm `alignment_start_summary.json` includes external-trigger readback
   both before and after tune, plus `mircat_alignment_arm_readback.json` with
   `confirmed_armed: true` before tuning.
5. Scope or visually check T660-2 CHB at the MIRcat end if readbacks are correct
   but firing is still absent.

The gate being ON is not sufficient in external-trigger mode. The MIRcat only
fires when the emission gate is open and valid TTL rising edges reach `TRIG IN`.

## Stop Sequence

For UI-started alignment runs, pressing `Emission Off` runs the alignment stop
path:

1. Apply `instrument/recipes/safe_idle.yaml`.
2. Close MIRcat emission.
3. Disarm and deinitialize MIRcat.
4. Close the HF2LI LabOne session.
5. Update the run manifest in the UI alignment run directory.

`Stop Alignment`, `Disarm`, and `Deinitialize` also use the same stop path when
a UI alignment run is active.

## Run Artifacts

UI alignment starts write a timestamped operational directory:

```text
evidence/experiments/runs/YYYYMMDD_HHMMSS_mircat_detector_alignment_ui/
```

Expected artifacts include:

- `alignment_request.json`
- `safe_idle_before_alignment_readback.json` only when `Use T660 Timing` is checked
- `mircat_alignment_laser_parameters.json`
- `mircat_alignment_arm_readback.json`
- `hf2li_detector_alignment_settings_snapshot.json`
- `hf2li_detector_alignment_preset_readback.json`
- `mircat_detector_alignment_2mhz_readback.json` only when `Use T660 Timing` is checked
- `mircat_alignment_state_readback.json`
- `alignment_start_summary.json`
- `safe_idle_after_alignment_readback.json`
- `alignment_stop_summary.json`
- `run_manifest.json`

The terminal hardware check
`software/tests/hardware_checks/check_mircat_detector_alignment.py` uses the same workflow
but holds until Enter or `--duration-s`, then runs the same stop sequence.
