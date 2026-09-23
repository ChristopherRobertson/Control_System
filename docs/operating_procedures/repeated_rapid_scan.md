# Rapid Scan Phase Delay

The installed tabs are **Rapid Scan Phase Delay** and **DD Rapid Scan Phase Delay**,
registered as `repeated_rapid_scan:single`
and `repeated_rapid_scan:dual`. They share pure algorithms and have independent
settings, native records, cancellation and instrument ownership.

This page records the implementation contract. A full operator manual is deferred.

## Compact acquisition workflow

Enter the sample name, spectral limits, recovery observation duration, phase
count and repeats. The summary shows the resulting movie count, scans, timing
and storage. Automatic choices use installed capabilities and current readbacks;
supported overrides remain visible in a framed group. Acquisition uses the installed-device
adapter. Test devices are injected by tests and are not an operator mode.
Loaded plans and preferences retain removed engineering controls only as
source metadata; new runs resolve those settings automatically. Accessible
overrides, their independent Auto choices and selected analysis bands remain.

This instrument uses **QCL1 only**. **Repetition rate** sets the external T660
cadence that triggers MIRcat pulses in mode 2. **Pulse width** sets the MIRcat
SDK optical pulse-width parameter; it is distinct from the T660 TTL width.
External cadence times actual MIRcat width must not exceed **30% duty** or a
stricter installed vendor limit. The internal MIRcat rate stays automatic and
must also satisfy that duty limit and exceed the external cadence. Missing
MIRcat values are resolved from QCL1 readbacks before applying a complete pair.
Requested values and actual readbacks are retained; readback alone does not
establish the optical pulse shape at the sample.

**Start** configures the owned instruments, obtains an unpumped baseline when
needed, records each complete movie, restores the instrument and saves native
and derived data. A compatible existing unpumped record is reused automatically.
There are no preliminary approval boxes, preparation acknowledgements,
temperature confirmations or promoted-evidence requirements in this workflow.
Optional condition and calibration records remain provenance. Actual device
limits, malformed schedules and unavailable required hardware are still reported.

Single mode can load or acquire a matched blank for absolute normalization.
Without it, native signals and relative sample changes remain available. Dual
mode records sample and reference simultaneously and retains their unpumped
ratio; it does not add a routine sequential blank. Physical pump-blocked or dark
controls require an actually installed means of establishing those conditions.
The standard run does not invent a shutter or pause for an acknowledgement to
pretend such a condition was acquired; unsupported requested controls are recorded.

The top-bar Save Location is frozen when an operation starts. Files go beneath
`measurements/repeated_rapid_scan/<mode>/<unique-run-id>/`. Plans and saved runs
can be loaded, and derived coordinates exported. Optional scientific labels do
not invalidate reusable native data. Detector mode, actual acquisition settings,
known sample identity and required spectral support prevent incompatible reuse.

## Timing and native reconstruction

Each pumped movie contains its pre-pump scans, one pump-crossing scan and every
post-pump scan through the chosen observation duration. Fire and Q-switch occur
once, not in each scan frame. A final all-disabled terminal frame prevents
unintended repeated outputs. There is no separate qualification-train approval
step. Precise edges come from the acknowledged finite T660 table; host polling
only retrieves data and status. A simultaneous dual recording has the same
movie duration as its single-detector schedule.

The [timing contract](../../software/control_app/measurement_modules/repeated_rapid_scan/recipes/timing_contract.json)
records the installed channel assignments, finite memory and uploader invariants.
No movie is silently split, slowed, or recycled through a circular buffer.
Missing or extra independently observed pump events are retained and reported;
a biological pump is never retried automatically.

Native integer timestamps are preserved exactly. Coordinates use

`aligned_s = (native_timestamp - native_origin) * unit_s * clock_scale + offset_s - latency_s`

`reaction_time_s = aligned_sample_s - aligned_observed_pump_s`

Integer origins are removed before float conversion. Every wavelength comes from
that scan's observed trajectory. Measured jitter, crossing points and sampling
gaps survive. Observed nominal marker coordinates remain available without a
promoted calibration and are labeled uncalibrated. Missing support is never
filled with invented detector observations. Directions are retained separately.
Requested phase, scan number and pointwise time are distinct quantities.

Electrical sync remains the timing basis unless applicable optical timing data
are supplied. A calibrated electrical-to-optical correction is explicitly
separate from an independent optical observation for each pump event.

## Signals and bounded analysis

Dual normalization retains `Q = S/R` and an unpumped `Q0`.
`ΔA = -log10(Q/Q0)` is evaluated only on matched valid reference support.
Absolute absorbance requires measured path balance `B`: `A = -log10(Q/B)`.
Without B, Q is a reference-normalized signal, not absolute transmission.
Single-mode relative changes use the unpumped sample signal in the same manner.
A saved approval flag or descriptive condition label is not a normalization gate.

Native sample/reference covariance is retained. Ratio uncertainty includes
`var(S)/R² + S² var(R)/R⁴ - 2 S cov(S,R)/R³`; missing uncertainty inputs remain
unknown. Clipped, unlocked, rejected and missing-reference points remain in the
native record and are excluded from quantitative support.

The plots show native detectors, supported time/spectral points, individual
scans, band-area kinetics and phase/direction consistency. Band integrals retain
the full time span of their contributing scan. The measured final band and
off-band return-to-baseline assessment still prevents another equivalent pump
when the sample has not recovered. A finite incomplete-recovery movie is a saved
outcome, not permission to restart a timer or repeat the pump.

Optional apparent-recovery fitting uses a supplied, identified response kernel
and spectral template at actual native points. It neither changes acquisition
readiness nor promotes its source. The model accounts for the observed scan
trajectory throughout supported filter history, retains residuals/covariance,
and records missing support and conditional uncertainty. A seconds-long
component or biexponential alone does not establish solvent recombination;
concentration, mass balance and artifact evidence remain necessary for stronger
interpretation.

## Preservation and verification

Runs contain `run.json` and `native.npz`, preserving native dtypes/values,
operation settings, readbacks, exclusions, partial movies and restoration
outcomes. Stable IDs, paths, timestamps and versions supply provenance; no
repository hash-matching gate is used. Existing files are not overwritten.

Abort targets this tab's operation. A normal stop reports **Acquisition stopped**;
restoration or storage failures remain visible. Ownership is held through
cleanup and preservation. In-memory native data after a storage failure can be
saved to a new location before New run clears the session. Other tabs and all
saved files remain untouched.

The module tests cover timing compilation, device injection, record compatibility,
normalization, native transient reconstruction, cancellation, incomplete recovery,
cleanup/storage failure and tab isolation. Development and test execution do not
operate physical hardware or change instrument qualification. Maintained hardware sources are
[instrument wiring](../../instrument/wiring_map.yaml), the
[MIRcat process-trigger correspondence](../../references/manuals/MIRcat/daylight_db9_process_trigger_correspondence.md),
and the T660 manuals under `references/manuals/T660/`.
