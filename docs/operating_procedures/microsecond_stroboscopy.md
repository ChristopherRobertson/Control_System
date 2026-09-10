# Microsecond Stroboscopy

The application discovers **Microsecond Stroboscopy** and **Dual-Detector
Microsecond Stroboscopy** through this package's `registration.py`. Their stable
instance IDs are `microsecond_stroboscopy:single` and
`microsecond_stroboscopy:dual`; the experiment ID is
`microsecond_stroboscopy`. Install the package beside the completed version 1
measurement host and restart the application. No other experiment package is
required. The established Phase Scan tabs are unchanged.

The room-temperature condition is **RT-Mb-R-K / ARC-RT-MB-US**. The cryogenic
condition is the **microsecond branch of 77K-Mb-G-F / ARC-77-MB-NSUS**. The latter
retains the biological fast-program identity shared with its nanosecond branch,
but imports no nanosecond acquisition software. Each detector tab has its own
settings, blank, preliminary record, review, cancellation and results.

## Readiness and operating values

`EXPERIMENTS.md` supplies scientific requirements, not operating values. Initial
values in these tabs are explicitly **EXAMPLE ONLY** for offline planning and
simulation. The approximately 185 µs and 1 ms literature components appear only
in the optional labeled coverage example; fitting never fixes those rates or
requires two exponentials.

The maintained promoted-bundle registry contained no promoted bundles when this
implementation was verified. Connected biological operation therefore requires
applicable promotion and installed readbacks. Simulation and saved-data analysis
remain available. Passing software tests does not commission the instrument.

Load an applicable promoted qualification using its stable bundle ID, load the
accepted sample spectral-selection record, and check connected capabilities.
The capability action is itself an exclusively owned instrument operation with
preservation and cleanup. Ordinary tab construction, editing and plan preview
perform no discovery or device I/O. Supported manual overrides remain visible;
loading qualified recommendations preserves fields that the operator edited.

An impossible timing request, incompatible detector role, unsupported readback
or capacity excess is a planning error. A delay increment below the response
width is a **scientific resolution warning**. A missing optical calibration,
reset-equivalence record, temperature observation or applicable promotion is a
**readiness item**. These distinctions do not erase the requested settings.

The accepted standalone `sample_spectral_selection` format is the host v1
interchange record. It carries sample/condition identity, measured windows,
uncertainty, source and named acceptance. It does not promote instrument
calibration and does not require Slow Scan to be installed.

## Operator sequence

1. Choose the application's top-bar **Save Location**. Select simulation or
   connected hardware, the condition profile, and the actual sample,
   preparation, cell, position, matrix and temperature identities.
2. Enter measured band and off-band coordinates in cm⁻¹. Multiple points with
   the same band label form a local integration window. Include off-band support
   on both sides where accessible. A single center supports point kinetics,
   not a complete spectrum or a band-area claim.
3. Enter delays in µs, averages and the response/timing overrides. **Use IRF-sized
   early + logarithmic later grid** derives an early region and late coverage
   from the entered response and observation limit. It is a planning aid, not a
   demonstration of recovery. Inspect the error/readiness messages and the full
   time/event/memory/storage budget. Save and load plans without starting devices.
4. In single mode, physically load the matched sequential blank and acquire its
   complete unpumped wavelength/delay/average sequence, or load a compatible
   completed blank. Then load the sample. In dual mode, load the sample and
   matched-buffer reference simultaneously; there is no routine separate full
   blank sequence.
5. Acquire the preliminary unpumped sample (or sample/reference) record. Review
   measured support, signal levels, flags and identity, then explicitly check
   the preliminary-review control. Press **Start pumped microsecond acquisition**
   to begin the reviewed experiment.
6. At each wavenumber the software tunes, checks actual readiness/wavenumber,
   settles, acquires an unpumped baseline and controls, then checks recovery
   before each isolated pump event. It completes that wavenumber's delay series
   and final recovery check before moving to the next wavenumber. There are no
   automatic biological retries.
7. Inspect **Native points**, **Local spectral map**, **Wavelength / band-area
   kinetics** and **Coverage**. Linked numeric time/wavenumber controls and held
   arrows select actual measured slices. Missing samples remain gaps. Image and
   view actions are in the plot toolbar. Save/load native runs and export numeric
   point data from the panel.

Changing scientific settings, selected sample/calibration records or a relevant
instrument state invalidates incompatible approval with the named mismatch.
Restoring compatibility clears stale errors but never silently checks review.
**New run** clears this tab's blank/preliminary/review/results while preserving
entered settings and saved files. It does not alter the other detector tab.

Physical sample loading, beam blocking, thermal reset and moving/replacing a
sample remain operator actions. The installed adapter does not invent shutters,
stages, flow, temperature control or temperature sensors. Automatic repeated
events use only qualified passive recovery. A cryogenic sample needing a manual
reset between events must not be run as an unattended repeated-event sequence.
The online local baseline check supplements the selected multi-observable reset
qualification; it is not a new full-spectrum equivalence measurement.

## Timing and the measured observable

The implemented architecture uses a **continuous, high-rate MIR probe train**
at one stationary wavenumber. T660-1 supplies the maintained reference/probe/frame
input routes. T660-2 uses explicit finite frames, with one authorized pump event
per independently checked block and inert leading/trailing frames. Precise edges
come from the device timing table. Host polling observes progress; host sleeps
are used only for settling, recovery and timeouts. A per-frame clock interval is
not the biological pump cadence.

The compiler validates device quantization, pulse ordering, frame capacity,
integer division, duty and capture bounds. It uses the existing T660 pending-field
table uploader, acknowledges each frame, reports progress and checks cancellation.
Blocks are explicitly planned equivalent-event acquisitions, not silent splits
of a declared continuous experiment. The continuous quantity is the probe carrier;
each finite pump block has separate native timing and readout support.

HF2LI remains the spectral recorder. The maintained installed mapping uses
sample demodulator 0 / ADC 0, reference demodulator 3 / ADC 1, and timing demodulator
2. Both detector filters/rates are configured and read back separately. Aggregate
sample/reference/timing throughput is part of planning and capability validation.
The in-phase X observable requires a qualified reference phase; X and Y both
remain native. Nonpositive signals are excluded, never made positive with an
absolute-value repair.

DIO17 records the installed electrical Variable Sync signal. A promoted
Variable-Sync-to-pump latency locates an **estimated optical arrival**. This is
distinct from an independently observed optical event. Native records preserve
programmed commands, electrical edges, the origin's calibration identity and
unresolved optical fields separately. PicoScope qualification supplies applicable
timing/IRF evidence; PicoScope never replaces HF2LI spectral recording here.
There is no invented connected DIO1 gate.

For n cascaded HF2LI filter sections with time constant τf, the causal engineering
kernel is

`h(t) = t^(n−1) exp(−t/τf) / [(n−1)! τf^n], t ≥ 0`.

The forward kernel also includes detector latency, time-zero offset, Gaussian
jitter and the software integration aperture. Its engineering width/support estimate
includes `n τf² + jitter² + aperture²/12 + 1/(12 sample_rate²)`. Systematic latency
and time zero remain separate from random width. The engineering kernel must be
qualified against the actual optical/probe/detector response and carrier sampling;
it is not independently measured merely because these fields are filled in.
For native-point fitting, the actual valid matched sample times define the
integration weights. Missing reference points never contribute fictitious samples
to the forward model. The maps retain the declared aperture bins and record each
cell's actual mean delay separately; point fits use the actual native coordinates.
The `1/sample_rate` term is a conservative sampling-support diagnostic, not an
extra physical boxcar in the fit. HF2 decimation supplies timestamps; it does not
establish an integration exposure of one sample interval.

The reconstructed point integrates native HF2LI samples in its selected aperture
relative to the calibrated origin. Dual samples are matched one-to-one on
latency-corrected native timestamps within the configured alignment uncertainty
and sampling support. The calculation never equates array indexes, interpolates
missing samples or deconvolves unsupported bandwidth. The matched reference must
be stable and its separately retained transfer response applicable to the sample
path; unequal filters require qualified transfer/alignment evidence.
Unequal sample/reference filters leave recovery fits unresolvable unless an
applicable measured static-reference/transfer record is supplied. A variable
reference filtered differently from the sample must not be mistaken for recovery.

## Normalization, fits and uncertainty

Dual mode retains `Q = S/R` and compatible unpumped `Q0`. On valid positive
matched support, `ΔA = −log10(Q/Q0)`. Absolute transmission `Q/B` and absorbance
`A = −log10(Q/B)` require an applicable **measured** background/path-balance
factor B with provenance; Q0 is never relabeled as B. Single mode uses its
compatible sequential blank for the corresponding absolute ratio and its own
unpumped sample for the pump-induced change. Missing B leaves Q explicitly labeled
as a reference-normalized signal.

The uncertainty in Q uses the paired covariance of the sample/reference means:
with `g = [1/R, −S/R²]`, `var(Q) = gᵀ Cov(S,R) g`. Q0 uncertainty is propagated
through the logarithm. Native detector values, clocks, covariance inputs and flags
remain available. These are technical uncertainties, not independent biological
preparations; preparation, temperature, dose, spectral-axis and calibration
uncertainties must accompany a scientific claim.

Recovery fitting compares a constant/no-response model with freely estimated
apparent recovery and an offset; a second component is optional in the processing
API. It uses AICc and requires an improvement greater than 6 to justify additional
complexity. Linear fits provide initial estimates only. The final forward equation
filters intensity before applying the logarithm:

`ΔA_model(t) = b − log10[h * 10^(−[c + Σ ai exp(−t/τi)] H(t))]`.

The constant c represents a persistent post-pump offset; b represents the residual
baseline. The filter is integrated analytically/numerically at the measured
nonuniform times, followed by aperture/jitter quadrature. The fit retains candidate
scores, residuals, local parameter covariance, 95% intervals, identifiability and
coverage limits. Inadequate SNR, unqualified response, sparse support or poorly
identified rates yield **unresolvable**. Nonzero late signal yields **unrecovered**
at the observed limit; it is not forced to return to zero. Neither one nor two
rates establishes a molecular pathway.

Local band areas use trapezoid weights on explicitly measured coordinates within
each band label, with propagated point errors. All required coordinates must be
present; an interrupted window yields an area gap. Point kinetics and areas remain
separate. Baseline drift versus acquisition order and pump-blocked controls are
retained as diagnostics rather than silently detrended away.
The area curve carries its propagated uncertainty; it is not fitted by applying
an intensity logarithm to absorbance·cm⁻¹. Rate estimates come from the constituent
response-convolved wavelength fits. An area-level rate claim needs a justified
joint spectral model.

The promoted acquisition profile is retained in every native run. Its
`normalization.dark_offsets` contains sample and, in dual mode, reference entries
with `offset`, `standard_error` and the matching measured `record_id`. Connected
operation with required dark correction rejects absent or incompatible entries.
Processing subtracts these offsets on a copy and propagates their uncertainties;
native detector arrays are unchanged. Optional `normalization.background_factors`
are exact measured wavenumber entries with `value` and `record_id`; no missing
balance value is interpolated. Optional `normalization.reference_transfer` must
identify the accepted static-reference/transfer record for unequal filter claims.

The profile also supplies `hf2li.phase_shift_deg` for each active detector and a
`signed_x_calibration_id`, qualified input/PLL/integrity settings,
`timing_clock_readbacks` for both T660 devices, and the optical latency calibration.
Readback expectations are taken from the applicable installed profile rather
than inventing firmware status values. Loading a profile through the host's
promotion-validating loader does not create or promote calibration evidence.

## Preservation, progress and stopping

The host freezes the chosen root, settings, plan and selected records before
dispatch. Runs live under
`<Save Location>/measurements/microsecond_stroboscopy/<single|dual>/<run UUID>/`.
Preferences use only `measurements/microsecond_stroboscopy/<mode>/v1/` through the
scoped host API; the module does not change global QSettings groups.

Native preservation preflights the destination before device work, then writes
immutable revisions during acquisition and after restoration. `latest.json`
points to the last durable record. Array files preserve native dtype, integer
timestamps, signed zero and missing values; unchanged observations are reused
between revisions to avoid multiplying storage by the block count. Records contain
settings/readbacks, native polls and streams, event provenance, rejected/partial
blocks, controls, analysis and restoration outcomes. Earlier revisions and failed
write artifacts are preserved. There are no checksum/hash-matching operational
gates.

Progress reports configuration, acknowledged upload, tuning/settling, recovery,
capture, retrieval, restoration, native saving and analysis. The displayed wall
estimate includes preparation, the single-mode blank where applicable, preliminary,
controls, reset, upload, retrieval, restoration and final processing. Physical
loading/review and unresolved manual actions are explicitly open-ended; the estimate
is not a promise about those durations.

**Abort** targets this tab's current operation. A normal stop reports
**Acquisition stopped**, retains available native/partial records, and attempts all
cleanup actions. Ownership remains held through cleanup and required preservation.
A restoration or storage failure takes precedence over a normal stop and leaves
an actionable host recovery fault. Do not interpret worker completion as verified
physical safety. Host emergency stop is a separate lifecycle action.
After a storage failure, **Retry native save…** writes the retained arrays and
original error/restoration records to a writable location. New run and closing
remain blocked until that preservation succeeds. The retry performs no device
operation and does not clear the host's instrument fault; use explicit host
recovery for that separate outcome. Loading an interrupted run can reconstruct
its native points and coverage without requesting a kinetic fit.

## Verification and remaining commissioning

Module tests cover deterministic timing/quantization and uploader acknowledgment,
host pair discovery/isolation, hardware-free construction, compatibility, guided
simulation, installed APIs through injected devices, known µs/ms signals,
response/intensity convolution, nonuniform timing, mismatched detector latency,
covariance, missing/bad references, clipping/unlock/count errors, incomplete
recovery, interrupted blocks, cancellation, storage failure and cleanup precedence.
The unchanged host contract/interchange/presentation/integration tests are also
run. All verification is offline; no new physical acquisition was performed.

The final module and unchanged host contract/interchange/presentation/integration
run passed **127 tests**. The existing single/dual Phase Scan regression suites
passed **186 tests**, with **6 existing skips**. The package also passes Python
bytecode compilation and Git whitespace checks. Run the focused module suite from
the task checkout with `python -m pytest software/tests/measurement_modules/microsecond_stroboscopy -q`
using the repository UI environment.

Before biological use, promote applicable installed topology and tee/receiver
loading, discrete tune/settle response, input ranges/linearity and X phase,
aggregate stream rates, pump/probe timing and optical IRF, detector/reference
transfer, dark/artifact controls, measured sample spectral selection, reset
equivalence, dose/cadence and illuminated-sample temperature evidence. These remain
explicit commissioning items. In particular, an electrical timing marker is not
an independently observed optical pump count, and a local pre-event check cannot
establish a cryogenic reset that has never been qualified.
