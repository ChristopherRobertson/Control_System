# Prospective slow-scan and time-resolved acquisition procedures

Status: **REQUIREMENTS-LEVEL; NOT EXECUTABLE; NO BIOLOGICAL DATA ACQUIRED**

These procedures apply independently to HRP and MbCO at room temperature and 77 K.
Numeric
recipes remain locked until promoted calibration/characterization bundles exist.
All modes preserve native pulse-level and stream-level Sample, Reference, complete
DIO, MIRcat readback, observed pump, temperature, configuration, exclusion, and
restoration evidence under the measurement-campaign data contract.

The HF2LI is the primary normalized Sample/Reference recorder. The PicoScope is an
independent waveform, trigger, detector-response, saturation, branch-transfer, and IRF
diagnostic; its records do not silently replace the primary spectral streams. Normal
simultaneous dual-detector wiring and temporary sample-detector/pump-detector timing
wiring have separate configuration IDs and are bridged only by calibrated quantities.
Probe carrier/rate optimization is independent of the maximum pump-event rate.

## Mandatory initial slow scans

Before time-resolved work, acquire and accept a condition-specific slow scan for each
of room-temperature HRP–CO, room-temperature MbCO, 77 K HRP–CO, and 77 K MbCO.
Each determines actual centers, widths, integrated areas, baselines, interference,
direction dependence, sensitivity, and local windows. Literature values are search
anchors, not final setpoints. A new preparation, cell reload, temperature/thermal
cycle, matrix, material time gap or state change, optical/acquisition configuration, or
failed reference checkpoint triggers the applicable scan again.

## Fixed-wavelength kinetics

For prospectively declared primary, secondary, and off-band wavelengths: settle and
accept a pre-pump baseline; acquire matched negative-delay or pump-blocked controls;
observe rather than infer the pump event; record through the entire required
recovery; enforce cumulative exposure and recovery before another accepted event;
and randomize or balance wavelength and delay order. Abort or exclude without
deleting data when state, recovery, exposure, temperature, saturation, timing, or
stream-quality gates fail.

## Phase-shifted rapid-scan stroboscopy

Repeated recoverable events scan the declared window while pump time shifts relative
to scan start over a frozen phase schedule. Both directions, pump-blocked, and no-
sample/artifact controls are mandatory. Every sample retains corrected instantaneous
wavenumber and delay relative to the observed pump. Measure scan-to-scan power and
wavelength repeatability. Freeze the two-dimensional reconstruction, weighting, and
interpolation support rule before opening biological results; publish the actual
`(wavenumber, delay)` coverage matrix and label unidentifiable regions. Unsupported
interpolation is rejected. Demonstrate reconstruction on a nonbiological surrogate
first. A single rapid scan is never an instantaneous spectrum.

## Single-scan phase-delay reconstruction

When an equivalent initial state can be demonstrated, acquire one rapid scan per
accepted pump event at a prospectively varied pump phase. Retain the actual scan
trajectory, direction, start/turnaround history, observed pump, complete native
coverage, and state/reset evidence. This architecture is distinct from repeated
rapid-scan stroboscopy and is rejected when recovery, fresh-position, or equivalent-
state criteria fail. Its reconstruction must pass the same nonbiological bias,
missing-data, noise, edge, filter-memory, and interpolation tests.

## Single-pump rapid/logarithmic scan-burst reconstruction

For slow cryogenic recovery where repeated pumping cannot preserve state, admit one
independently observed pump event followed by a frozen sequence of rapid scans or
logarithmically scheduled scan bursts. Preserve the full command/event/scan schedule,
actual `(wavenumber,time)` coverage, thermal and probe-duty history, missing bursts,
and observation-limit accounting. Unsupported gaps are labeled; interpolation cannot
create a measured region. Additional pump events require a new qualified state,
position, or preparation and remain separate records.

## Wavelength-by-wavelength stroboscopic reconstruction

At each wavelength, use the frozen delay grid and repeat accepted events at every
delay. Change wavelength only after recovery and state checks. Acquire matched
pump-off, negative-delay, and off-band controls. Normalize through the qualified
sample/reference covariance model, then combine independent traces into
`DeltaA(wavenumber,time)`. Retain wavelength-dependent probe power, linewidth,
timing, detector response, uncertainty, and provenance. Different configurations
cannot be pooled without an explicit bridge study.

Nanosecond and microsecond wavelength-by-wavelength acquisition are separate
configurations even if the wavelength list is shared. Each requires its own optical
time origin, integration aperture, detector/branch response, HF2LI filter and stream
envelope, jitter/IRF, SNR, dose/recovery schedule, and nonbiological reconstruction
validation.

## Experiment-specific boundaries

HRP targets approximately second-scale recovery and only faster features supported
by IRF and SNR. Use the minimum duty and rate meeting resolution/precision. Low-rate
and high-rate probe architectures have separate IDs and a bridge if both are used;
neither inherits a final value from the pump's rate limit.

MbCO begins only after HRP closeout, verified restoration, explicit handoff, QB-01M,
and MbCO-specific promotion. The cryogenic timescale is a hypothesis until measured.
Pulse-level resolution uses the direct detector/PicoScope path; HF2LI contributes
only inside its qualified envelope. Every mode remains in this design if later
evidence rejects it; the result is recorded as a limitation, not deletion.

All five reconstruction methods—nanosecond and microsecond wavelength-by-wavelength,
repeated rapid scan, single-scan phase delay, and single-pump rapid/log scan burst—are
validated separately against native coverage and a known nonbiological target before a
matching biological claim. Missing scans/samples, drift, heteroscedastic noise, phase
error, direction, edge effects, filter memory, interpolation, and identifiable regions
are explicit validation outputs. Chemical time zero is an optically observed
sample-plane pump/probe relation, never an electrical-command or equal-cable-length
assumption.
