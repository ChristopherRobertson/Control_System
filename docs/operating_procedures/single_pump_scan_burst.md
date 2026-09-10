# Single-pump scan bursts

This package implements `single_pump_scan_burst` for the version-1 measurement
host. Its two top-level tabs are **Single-Pump Scan Bursts**
(`single_pump_scan_burst:single`) and **Dual-Detector Single-Pump Scan Bursts**
(`single_pump_scan_burst:dual`). Each owns its settings, selected records,
blank/baseline, review, cancellation and result. The existing Phase Scan tabs
retain their own implementation.

The condition profiles are `77K-HRP-G-S` / `ARC-77-HRP-SPB` and
`77K-Mb-G-S` / `ARC-77-MB-SPB`. They require separate accepted cryogenic sample,
preparation, state, matrix, cell, position, thermal-history and temperature
identities. Nominal 77 K is descriptive; it is not an illuminated-sample
temperature measurement. The scientific requirements are
[EXPERIMENTS.md](../../EXPERIMENTS.md) §§8.5, 11–18. That document does not supply
operating settings.

## Installation and readiness

Install the `software/control_app/measurement_modules/single_pump_scan_burst/`
directory alongside the integrated measurement host and restart the normal app.
Discovery imports its `registration.py`; no central registry edits, sibling
experiment package or additional dependencies are required. The isolated task
branch starts from host commit `7152d66`, which includes the integrated current
single/dual Phase Scan implementation and fixes. This commit reference records
provenance; matching it is not an operational gate.

The task also incorporates the foundation owner's backward-compatible
PicoScope factory change (`8f62300`, cherry-picked as `7141327`). It accepts a
detached per-operation `capture_settings` mapping through the existing owned
device factory, without changing global configuration. The foundation owner
supplied this change and its compatibility tests; the experiment package does
not introduce another hardware factory or shared abstraction.
The owner's standalone discovery-aware shell smoke-test fix (`acb098a`,
cherry-picked as `1326b1b`) verifies the seven preserved legacy tabs plus
accepted optional module tabs, without contacting devices.

Construction and planning contact no instruments. Optional UI dependencies are
the existing PySide6 and Matplotlib app dependencies. Real device discovery and
acquisition are explicit operations under the host's exclusive ownership.
Simulation never falls back to a real device.

The maintained promoted-bundle registry was empty during development. Missing
commissioning evidence remains visible in the planner and prevents unsupported
connected biological work. It does not prevent editing or saving plans,
simulation, loading records or analysis. **EXAMPLE ONLY** settings are opt-in
simulation data and cannot be used as a commissioned biological recipe.

Select operating values from applicable promoted instrument bundles, connected
readbacks and justified condition records. Preserve requested, quantized selected
and actual read-back values. Required qualifications include spectral trajectory
and direction, marker semantics, both HF2LI detector paths and filters where
applicable, aggregate stream throughput, optical arrival/IRF and clock transfer,
the tee/receiver topology, low-dose pump characterization, and the actual
sample-temperature envelope. A sample spectral-selection record can be loaded
through the host's versioned standalone interchange; it is not an instrument
calibration and does not require the producing Slow Scan package.

The installed device roles remain:

| Device/channel | Role |
| --- | --- |
| HF2LI demodulator 0, Signal 1 | Primary sample spectral stream |
| HF2LI demodulator 3, Signal 2 | Simultaneous reference in dual mode |
| HF2LI demodulator 2 | Native timing/DIO stream |
| T660-1 A/B/C | HF2 reference / MIRcat pulse trigger / T660-2 frame input |
| T660-2 A/B/C | Pump FIRE / Q-switch / MIRcat Process Trigger |
| DIO21 / DIO20 / DIO22 | Observed Sweep Active / direction / wavelength markers |
| PicoScope | Qualified pulse/timing/IRF diagnostics; never the spectral recorder |

Neither T660 channel D nor HF2LI DIO1 is presumed wired. The default PicoScope
A/B routing observes sample/reference MIR detectors; it does **not** provide
an independent visible-pump monitor. An explicitly qualified optical diagnostic
configuration must preserve the selected HF2LI spectral topology. An electrical
pump synchronization event is never substituted for optical arrival.

No sample thermometer, temperature controller, motorized position stage,
thermal-reset mechanism, shutter or refill controller is presumed installed.
The host can supply an installed temperature adapter; otherwise the operator
must supply identified, time-bounded measured temperature evidence. Stale
temperature evidence stops progression. Any physical loading, beam-blocking,
cell positioning, cooling or refilling action must follow the installed
instrument procedures and be recorded explicitly. No measurement in this
development task operated hardware.

## Routine workflow

1. Select the tab and top-bar Save Location. Set the condition and load the
   accepted sample selection, promoted operating evidence and applicable dark,
   pump-blocked, off-band, matrix/cell and cryostat controls. Identify the sample
   temperature measurement and permitted heating/exposure envelope.
2. Edit the early scan train, logarithmic or explicit information-based later
   burst times, scan counts, observation limit and final-state scans. Keep
   useful spectra fast; slow chemical recovery alone does not justify slow
   individual scans. Review the finite frame/channel schedule, hardware
   quantization, storage/memory budget and wall-time estimate. Unknown
   preparation/control/tuning/upload/restoration overheads are labeled as
   unknown; physical actions add time.
3. In single mode, acquire or load a complete compatible sequential matched
   blank/control record with pump outputs disabled. Preserve sequence position,
   trajectory, settings and state compatibility. In dual mode, install the
   matched-buffer reference for simultaneous recording; no routine full
   separate blank sequence is added.
4. Load the sample and acquire unpumped preliminary spectra. Inspect stationary
   spectra, native support, detector quality, state and temperature. The review
   checkbox and a separate **Start** action authorize the measurement workflow.
   Changes to settings, selection, calibration or relevant instrument state
   invalidate prior review with a specific mismatch. Fixing compatibility does
   not silently reapprove the measurement.
5. Start freezes the plan, records and output root. The worker configures,
   uploads acknowledged timing frames, checks tuning/settling, retains the
   pump intent durably, and enables one finite first block. Exactly one
   independent optical pump observation is required. Later blocks contain
   disabled FIRE and Q-switch outputs.
6. During long waits the UI shows elapsed/remaining time, next burst, counts,
   temperature and exposure. The host may prepare a future block, but its
   requested elapsed time is not an observed edge. Native observations establish
   actual times; upload, settling and missed intervals remain real gaps.
7. Retain the final-state spectrum and restoration records, then inspect the
   native and derived views. **New run** clears only this tab's blank, review
   and results, preserving entered settings, other tabs and saved files.

Save/Load Plan uses a versioned experiment/mode envelope. Loaded timing tables
are recompiled from scientific settings and capability records. Native loading
rejects incompatible experiment, mode and condition identities. Preferences
stay under `measurements/single_pump_scan_burst/<mode>/v1/`; no shared QSettings
group is changed.

## Timing and non-repeatable state

Every declared block contains one hardware frame per scan and an all-OFF
terminal frame. Train count zero means no *additional* pulses; an enabled
channel still emits its first pulse. Only the first frame of the first block
has FIRE/Q-switch enabled. An uninterrupted early train that exceeds capacity
is rejected rather than silently split. Later bursts are explicit finite blocks
and never rearm a pump. The compiler accounts for frame capacity, predivider,
timing quantum, edge widths/delays, guard intervals, scan duration, pulse duty,
stream rates and the longest observation.

Upload uses the documented T660 pending-field optimization and per-frame
acknowledgments with progress/cancellation. Python waits do not define pump,
probe or scan edges. Electrical synchronization, observed scan onset and the
independent optical epoch are separate records. Native integer ticks are kept
intact; pointwise elapsed time can subtract the epoch before floating-point
conversion, preserving short differences after long device uptime.

Cancellation covers preparation, programming, acquisition, waits and analysis.
Normal stopping is reported as **Acquisition stopped**. Cleanup and preservation
failures take precedence over that normal message. Ownership lasts through
safe restoration and required preservation; a worker exiting does not prove
the instruments are safe. A normal Stop targets this tab only; the host-wide
emergency lifecycle remains separate.

An interrupted/power-failed observation must never automatically fire another
pump. Resume needs retained optical epoch, clock continuity and independently
established unchanged instrument/sample state. Ambiguous clock loss, a torn
pump-intent history, missing identity or an unverified sample state leaves an
incomplete result and requires an explicitly new experiment/state. An approved
continuation is linked to its earlier evidence and starts only unpumped
remaining blocks. Manual resets or fresh-position extensions require
equivalent-state evidence and a separately identified observation; no repeated
phase offsets are interleaved into the main one-pump record.

The explicit continuation action loads the interrupted run and a separate named
continuity/state-evidence record, shows the retained epoch for review and
requires a new Start action. It creates a linked output directory while keeping
the earlier observation intact. Band fractions retain the original first
observed bleach across that link. A new biological pump also checks both
detector-mode histories beneath the selected root and rejects a previously
used accepted-state identity, including a pump intent with unresolved arrival.
Changing storage destinations does not establish a new sample state; retain
the source observation and use a separately qualified state after any reset.

## Native data and equations

Runs live under the root frozen at Start:
`measurements/single_pump_scan_burst/<mode>/<unique-run-id>/`. Metadata, an
fsynced append-only event journal, exclusive NPZ native chunks, immutable
records/checkpoints and a final manifest preserve partial, rejected, diagnostic
and restoration evidence. Convenience current/final pointers do not erase
earlier checkpoints/finalizations. Native array dtypes and values are retained
without pickle. Existing chunk names cannot be overwritten. Storage failures
are reported, not converted into successful runs. IDs, paths, byte sizes,
versions and UTC/source records establish provenance; no checksum matching is
required. Journals and chunks can be streamed without retaining the observation
in RAM across long waits.

Each spectral sample is an observation at its measured wavenumber and time,
not an instantaneous spectrum. Wavelength reconstruction uses identified
controller markers within valid sweep support. Missing markers, scans, timing,
reference, clipping or lock loss are flagged; gaps are never silently filled.

For dual mode, `Q=S/R`, with reference matched in measured time, wavenumber and
scan support. `Q0` is the compatible unpumped sample/reference baseline:

```
Delta A = -log10(Q/Q0)
```

Absolute absorbance additionally requires an applicable measured balance
factor `B`: `T=Q/B`, `A=-log10(T)`. In its absence the ratio is labeled
reference-normalized signal, not absolute transmission or absorbance. `Q0`
is never substituted for `B`.

Single mode uses its corresponding sequential blank position:
`T_i=S_i/blank_i`, `A_i=-log10(T_i)` and
`Delta A_i=-log10(T_i/T0)`. Coordinates and scan direction must match measured
support. It assumes compatible source/detector behavior between sequential
sample and blank observations, which remains an uncertainty limitation.

Where noise inputs are supplied, ratio uncertainty retains detector covariance:

```
Var(S/R) = Var(S)/R^2 + S^2 Var(R)/R^4 - 2 S Cov(S,R)/R^3
Var(Delta A) = [Var(Q)/Q^2 + Var(Q0)/Q0^2] / ln(10)^2
```

The second equation assumes separate baseline and pumped records are
independent. Single-mode blank uncertainty is propagated. Unknown uncertainties
remain unknown; they are not set to zero. Unsupported or nonpositive values
cannot enter logarithms.

Plots provide early linear time separately from strictly positive logarithmic
time, sparse scan-burst timing, native trajectory/direction, spectral/time
slices and temperature/probe-duty history. Point selection and held arrows
select actual coordinates; view/reset/image controls live in the plot toolbar.
Any bounded display reduction is labeled and does not alter native files.

Band summaries report observed residual fractions relative to the first
observed negative band signal, with their support and finite observation
window. They do not assume that the first scan captures total photolysis or
that the final scan represents full recovery. Prospective plateau tests require
supported observations in each declared band. An unrecovered population stays
right-censored. These are apparent recovery observables, not automatically
geminate fractions, lifetimes or evidence of bulk-solvent return. Mechanistic
fits require the accepted IRF, sensitivity/identifiability and independent
escape evidence specified in EXPERIMENTS.md.

## Verification and remaining commissioning

Hardware-free tests are in
`software/tests/measurement_modules/single_pump_scan_burst/`. Run them together
with the frozen host compatibility suites:

```powershell
python -m pytest software/tests/measurement_modules/single_pump_scan_burst -q
python -m pytest software/tests/test_measurement_host_contract.py software/tests/test_measurement_host_contract_interchange.py software/tests/test_measurement_host_presentation.py -q
```

Tests cover deterministic compilation and limits, known-truth multiscale
pointwise recovery, sparse/missing support, bad reference/clipping/unlock,
covariance, normalization without an absolute balance, native dtype/value
retention, torn journals, storage failures, one-pump continuation/refusal,
cancellation and cleanup precedence, and independent tab sessions through
the host. Simulated device verification is not hardware commissioning.

Final development verification on the isolated task checkout: **88 module
tests passed**; module plus shell smoke checks passed **92 tests**. The complete
`software/tests` suite with `hardware_checks` excluded passed **854 tests**,
with **9 skips**, **24 passing subtests** and two existing Phase Scan diagnostic
plot-legend warnings. Both new tabs were also rendered offscreen, and a complete
simulated dual run was inspected in the positive-time logarithmic view. No
native device was contacted. `git diff --check` passed.

Before connected use, qualify the installed optical pump monitor and recorder
bridge; illuminated-sample temperature measurement/freshness and heating;
trajectory and scan-trigger behavior; detector lock, filters, rates and receiver
loading; state/control compatibility; safe restoration; and long-duration
clock/storage performance. Named calibration IDs alone are insufficient.
Accepted evidence must be applicable to this architecture, mode, configuration
and condition. Creating this package or saving a plan does not promote a bundle,
authorize hardware or mark a campaign phase complete.
