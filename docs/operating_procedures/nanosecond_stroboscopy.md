# Nanosecond stroboscopy

The **Nanosecond Stroboscopy** and **Dual-Detector Nanosecond Stroboscopy** tabs
use the common compact measurement panel. Normal operations use installed device
factories. There is no execution-mode selector, review checkbox, temperature
branch, or promoted-evidence gate for raw measurement.

## Inputs and operation

The essential inputs are wavenumbers (cm⁻¹), programmed delays (ns), averages,
and cycle interval (s). The framed HF2LI override form is always visible: filter
order, time constant, and sample rate. Dual mode provides independent sample and
reference choices. Each field starts at Auto and follows connected readbacks;
setting one override does not freeze the others. Sequencing and electrical timing
details are computed automatically. Historical overrides remain recorded as
metadata when an older plan is loaded. Optional sample,
protein, temperature, and preparation annotations do not change the procedure.

Acquisition uses the single installed laser, QCL 1. Historical QCL selection in a
saved plan cannot redirect it. MIRcat repetition rate and optical pulse width are
preserved from the device; their product (with width in seconds) must be at most
0.30 and satisfy the device's own limits. The sparse external probe cadence and
electrical trigger width are separate settings, not substitutes for this check.

In single mode, acquire or load a complete blank, then acquire the unpumped
sample. In dual mode, acquire the unpumped sample and simultaneous reference Q₀.
Start becomes available when the required data are compatible. No separate
review action is required. Matching data are reused until acquisition settings
or observed device settings change. New Run clears this tab's data while
preserving entered settings and saved files.

Stop requests cancellation of this tab only. Instrument ownership spans all
hardware calls, restoration, and required native preservation. Interlock,
clipping, acquisition-count, invalid-reference, and storage errors remain real
errors. Hardware cleanup failures take precedence over normal stopped status.

## Installed measurement kernel

At each fixed wavenumber, T660 frames place one sparse probe at each programmed
pump-to-probe interval. The entire delay series finishes before retuning. The
probe clock uses a finite remote-gated burst; one execute command emits the
selected frame count even if host retrieval is delayed. Inherited edge
references are configured and checked against the compiled electrical recipe.
Measured detector pulse count and cadence must support the event assignment.
HF2LI remains the spectral recorder. Its sample and reference demodulators use
verified internal 0-Hz operation, retaining the DC lowpass response to the pulse.
The baseline-subtracted complex response is integrated over its full aperture;
the magnitude of that integral supplies a detector response area (V·s). Stable
linear transfer factors cancel between compatible pumped and unpumped records.
Each stream uses its own measured timestamps, with the integer epoch subtracted
before conversion to seconds. Gaps, duplicate timestamps, incomplete apertures,
nonreturning detector tails, and inadequate integrated signal are retained as
quality faults; they do not produce a fabricated ratio.
Input AC coupling and demodulator sinc filtering are disabled and verified;
their original values are restored. The two detectors are configured and
retained independently. HF2LI DC operation alone does not establish the upstream
detector's DC transfer function; these areas are not calibrated optical energy.

Device settings and readbacks determine the pulse commands, lowpass aperture,
filter settling, and quantized cycle interval. Timers and polling observe
completion; they do not create precise pump/probe edges. Calibration is optional
for raw relative acquisition. Programmed delay, any observed electrical timing,
and independently calibrated optical arrival remain separate fields. A raw
command-binned trace is not a resolved optical lifetime measurement.

The dual observable is Q=S/R and ΔA=−log₁₀(Q/Q₀). Raw Q is not labelled absolute
transmission or absorbance. Absolute absorbance additionally needs a measured
applicable path-balance factor B, through A=−log₁₀(Q/B). Single mode uses its
compatible sequential blank. Missing support remains missing, and covariance
and baseline uncertainty are retained. Missing optical timing, sample-reset
interpretation, or temperature metadata does not erase valid raw signals;
unresolved optical timing prevents a resolved-lifetime claim.

## Persistence and integration

Each tab has its own state and immutable operation snapshots. The app's Save
Location is frozen at run start; output is written below
`measurements/nanosecond_stroboscopy/<single|dual>/<run ID>/`. Native detector
values, timestamps, configuration/readbacks, partial events, and restoration
records are preserved. Existing version-1 native files remain loadable; newly
processed data identify their analysis version. The DC complex-area kernel is
`sparse_dc_complex_probe_area_v2`; records from the older calibrated signed-area
kernel remain readable but cannot serve as its normalization baseline. There are
no hash-matching gates.

Install the module beside the measurement host. Discovery of `registration.py`
creates exactly two handles with IDs `nanosecond_stroboscopy:single` and
`nanosecond_stroboscopy:dual`. Simulators are retained for injected development
and tests only. No physical measurement is performed by unattended tests.

## Verification

Scoped verification of the visible-form/QCL 1 correction passed 142 experiment
and shared-panel checks. Physical commissioning was not performed.

The module tests cover both detector modes through the installed adapter with
injected transports, default live-factory selection, automatic overrides,
metadata-independent compatibility, uncalibrated raw reconstruction, device
failures, abort, cleanup, and native preservation. QCL 1 routing, saved-setting
migration, actual pulse readbacks, and the exact inclusive 30% duty boundary are
covered with injected transports. UI renders at 1100×780 are
compared with the established Phase Scan layout. The screenshots under
`software/tests/measurement_modules/nanosecond_stroboscopy/artifacts/` display
synthetic example data in the actual app; they are not physical measurements.
The shared compact panel and
its API are owned by the host task; this package does not duplicate that framework.

From the task worktree, with software dependencies available:

```powershell
$env:PYTHONPATH = "$PWD/software"
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest software/tests/measurement_modules/nanosecond_stroboscopy -q
```
