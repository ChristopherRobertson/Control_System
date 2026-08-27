# Prospective fixed-wavelength and stroboscopic acquisition procedures

Status: **REQUIREMENTS-LEVEL; NOT EXECUTABLE; NO BIOLOGICAL DATA ACQUIRED**

These procedures apply independently to HRP and optional cryogenic MbCO. Numeric
recipes remain locked until promoted calibration/characterization bundles exist.
All modes preserve native pulse-level and stream-level Sample, Reference, complete
DIO, MIRcat readback, observed pump, temperature, configuration, exclusion, and
restoration evidence under the measurement-campaign data contract.

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

## Wavelength-by-wavelength stroboscopic reconstruction

At each wavelength, use the frozen delay grid and repeat accepted events at every
delay. Change wavelength only after recovery and state checks. Acquire matched
pump-off, negative-delay, and off-band controls. Normalize through the qualified
sample/reference covariance model, then combine independent traces into
`DeltaA(wavenumber,time)`. Retain wavelength-dependent probe power, linewidth,
timing, detector response, uncertainty, and provenance. Different configurations
cannot be pooled without an explicit bridge study.

## Experiment-specific boundaries

HRP targets approximately second-scale recovery and only faster features supported
by IRF and SNR. Use the minimum duty and rate meeting resolution/precision. Low-rate
preferred and high-rate fallback architectures have separate IDs and a bridge if
both are used.

MbCO begins only after HRP closeout, verified restoration, explicit handoff, QB-01M,
and MbCO-specific promotion. The cryogenic timescale is a hypothesis until measured.
Pulse-level resolution uses the direct detector/PicoScope path; HF2LI contributes
only inside its qualified envelope. Every mode remains in this design if later
evidence rejects it; the result is recorded as a limitation, not deletion.
