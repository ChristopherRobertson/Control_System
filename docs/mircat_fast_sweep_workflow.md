# MIRcat Fast Sweep Workflow

This document covers the rewired fast spectral sweep. It is a UI/control,
timing, and acquisition workflow artifact, so it belongs in this repository
rather than in the RSI article folder.

## Purpose

Use this workflow when a full-band polystyrene sweep is needed quickly. It
does not step through individual wavenumbers. Instead, it runs one continuous
MIRcat sweep while the HF2LI uses the MIRcat pulse marker as the reference.

The workflow assumes this physical wiring:

- `MIRcat TRIG OUT -> HF2LI DIO0` for phase-coherent EXT REF
- `MIRcat TRIG OUT -> HF2LI DIO1` for the LabOne Plotter trigger/marker
- `T660-2 CHB` disconnected from `MIRcat TRIG IN`

Use a splitter or equivalent routing if the MIRcat `TRIG OUT` must feed both
HF2LI inputs. This keeps the lock-in reference phase-coherent with the MIRcat
pulses, while the DIO1 marker defines the actual emission interval for the
sweep axis. The first small segment can contain the expected HF2LI lock transient
because the reference appears with emission; trim it using the DIO1 marker if it
is visible in the exported trace.

## Why This Replaces Step-Scan

A full-band step-scan at roughly 400 setpoints takes too long because each point
requires tune/readback/acquire overhead. The fast sweep completes the optical
sweep in about 10 seconds for `2076 -> 1640 cm^-1` at `43.6 cm^-1/s`.

Use the fast sweep when the hardware marker is available. Use a step-scan only
when static per-wavenumber readback matters more than speed.

## Run Command

Run from native Windows Python in the project directory:

```powershell
py tests\hardware_checks\check_mircat_fast_sweep.py --operator "Chris" --confirm-real-hardware --confirm-laser-safety --confirm-mircat-trig-out-to-hf2li-dio0-and-dio1
```

Optional overrides:

```powershell
py tests\hardware_checks\check_mircat_fast_sweep.py --operator "Chris" --confirm-real-hardware --confirm-laser-safety --confirm-mircat-trig-out-to-hf2li-dio0-and-dio1 --start-cm1 2076 --stop-cm1 1640 --scan-rate-cm1-s 43.6
```

## LabOne Plotter Setup

Before the run, open LabOne and configure the Plotter:

- Add `Demodulators/1/Sample/R`
- Add `Demodulators/4/Sample/R`
- Set Plotter trigger to `DIO1` rising
- Leave demodulator transfer triggers continuous; the preset keeps
  `/demods/0/trigger = 0` and `/demods/3/trigger = 0`

The workflow does not replicate the Plotter in the UI. It configures HF2LI and
writes a continuous API record, but the article-grade time-to-wavenumber axis
should use the MIRcat `TRIG OUT` marker captured/exported from LabOne.

## Workflow Sequence

1. Apply HF2LI preset `standard_spectral_validation`.
2. Confirm the physical fast-sweep wiring.
3. Initialize MIRcat, clear errors, confirm interlock/key state, arm, and wait for TECs.
4. Set MIRcat pulse settings to `2 MHz`, `150 ns`, `1000 mA`, internal mode.
5. Tune MIRcat to the sweep start with emission off.
6. Start HF2LI polling, wait the pre-sweep record interval, open MIRcat emission, and start the sweep.
7. Save HF2LI raw/summary CSV, MIRcat readbacks, and manifest.
8. Stop MIRcat scan, close emission, and disarm/deinitialize.

## Run Artifacts

Expected run folder:

```text
runs/YYYYMMDD_HHMMSS_polystyrene_fast_sweep/
```

Expected files include:

- `command_log.txt`
- `fast_sweep_request.json`
- `hf2li_fast_sweep_settings_snapshot.json`
- `hf2li_fast_sweep_preset_readback.json`
- `fast_sweep_startup_readback.json`
- `hf2li_raw_fast_sweep.csv`
- `hf2li_summary_fast_sweep.csv`
- `fast_sweep_acquisition_metadata.json`
- `fast_sweep_cleanup_summary.json`
- `fast_sweep_summary.json`
- `run_manifest.json`

If a required confirmation is omitted or hardware fails, the run writes
`BLOCKED.md`.
