# Exploratory Phase-Scan Changes

## Purpose and disposition

This file records deliberate changes and operating decisions for the disposable
Phase-Scan proof-of-concept branch. The objective is to demonstrate that
room-temperature MbCO recombination can be observed after photolysis with the
single-scan phase-delay method. These measurements and outputs are exploratory,
are not campaign qualification evidence, and are not eligible for publication.

The application, recipe, test, and workflow changes described here remain on the
`exploratory` branch. When the proof-of-concept work is complete, only this file
is intended to be retained on `main`; the exploratory implementation is not to be
merged or pushed to `main`.

The Nd:YAG iris-control work is not an exploratory change. It is part of the
current main-branch base and remains available in this branch through that base.

## Implemented exploratory changes

### Direct Sweep Active observation

- PicoScope CHA remains connected to the sample detector.
- PicoScope CHB remains connected to the reference detector and is the primary
  optical-pulse witness.
- The detector outputs remain split by the normal tees to the HF2LI and
  PicoScope.
- PicoScope EXT observes MIRcat DB9 pin 2, `Tuned / Sweep Active`, through a
  direct high-impedance branch. The existing pin-2 route to HF2LI DIO21 remains
  connected.
- The PicoScope EXT branch uses MIRcat DB9 pin 7 as its ground reference.
- T660-1 CHD is disconnected and disabled for this exploratory configuration.
- The direct BNC-to-mini-hook lead is treated as a 1x cable, not as a 10x
  attenuating probe. Its 50-ohm description is the cable impedance and does not
  authorize a 50-ohm termination at the observed DB9 signal.
- PicoScope EXT is configured for the rising Sweep Active edge with zero
  process-trigger offset. The configured trigger threshold is an initial
  candidate that must be checked against the observed pin-2 low and high levels.
- This direct trigger configuration is explicitly marked exploratory and cannot
  satisfy or replace the campaign CHD-to-Sweep-Active qualification.

### Exploratory output classification

- Background, test-scan, reconstruction, CSV, native-data, and plot products are
  marked `EXPLORATORY_PROOF_OF_CONCEPT` and not eligible for publication.
- Completed exploratory plots carry a visible `NOT FOR PUBLICATION` watermark.
- Missing-pulse-incomplete outputs retain their stricter
  `INCOMPLETE_MISSING_PULSE_COVERAGE` status and leave deficient regions empty.
- The complete original and repeated acquisitions remain preserved even when an
  attempt or region is rejected.

### Direct-trigger tests

- Hardware-free tests exercise the direct Sweep Active trigger contract, rising
  EXT edge, disabled T660-1 CHD, zero trigger offset, and nonpublication status.
- Missing-pulse retry tests continue to verify that the nominal pass completes
  before retries and that no more than three additional attempts are made for an
  affected phase delay.

## Retained missing-pulse behavior

The exploratory workflow retains the established missing-pulse acceptance and
gap-filling behavior:

- A MIRcat optical pulse is classified as missing only when its expected
  opportunity is absent from both CHA and CHB.
- A one-channel-only event is recorded as a detector/path discrepancy rather
  than a MIRcat omission.
- A phase delay is selected for reacquisition when two consecutive opportunities
  are absent from both channels, when a reconstruction interval has less than
  90% coverage, or when the whole-scan missing fraction exceeds 5%.
- All nominal phase delays are acquired before missing-pulse analysis begins.
- Only affected phase delays are retried, with no more than three additional
  attempts.
- Retrying stops as soon as the marker-aligned union of the original and repeats
  provides acceptable coverage for every required reconstruction region. A
  single omission-free replacement scan is not required.
- Valid original regions are retained. Valid repeat regions fill deficient
  regions, and multiple acceptable contributors are combined with pulse-coverage
  weighting while preserving per-region acquisition provenance.
- Isolated single missing opportunities are already accepted by the default
  90%-of-ten-opportunities rule for a 5-microsecond interval at 2 MHz.
- Missing optical opportunities are not replaced with synthetic pulses.
  Interpolation may be considered only for a visibly marked diagnostic preview;
  it must not replace measured values or convert an incomplete result into a
  complete result.

## Sample/reference processing decision

- The sample beam contains MbCO.
- The reference beam contains a matched water-and-buffer blank.
- Each acquisition is normalized as sample detector divided by reference
  detector before pump-induced absorbance is calculated.
- The optical background is an unpumped MbCO acquisition made with the blank
  simultaneously present in the reference path.
- The desired difference spectrum is
  `-log10[(S/R)/(S0/R0)]`.
- Pulse detection, local expected-grid fitting, Sweep Active alignment,
  wavelength-marker alignment, and reconstruction-bin assignment occur before
  attempts are combined.
- For repeated attempts, valid sample/reference transmission-ratio bins are to
  be coverage-weighted and merged before applying the logarithm. Independently
  merging sample and reference channels, or averaging already-log-transformed
  absorbance from unlike attempts, is not the intended final processing order.

## Approved proof-of-concept acquisition settings

The following settings were selected for the exploratory measurement but have
not yet all been applied to the workflow defaults:

| Setting | Exploratory value | Rationale |
|---|---:|---|
| MIRcat current | 750 mA | Reduce the risk of detector saturation in the strongly absorbing aqueous configuration; increase only after a pump-blocked signal check if necessary. |
| Probe repetition rate | 2 MHz | Retain the established external probe train and 500 ns expected-opportunity period. |
| Probe pulse width | 150 ns | Retain the established exploratory pulse setting. |
| Spectral span | 10 cm^-1 | Minimum proof-of-concept window, centered on the experimentally observed main A1 maximum after it is located. |
| Sweep rate | 10,000 cm^-1/s | Produces an approximately 1 ms sweep across a 10 cm^-1 window. |
| Phase increment | 5 microseconds | Retain the requested reconstruction grid and missing-pulse interval width. |
| Pre-pump window | 2 ms | Provide an unpumped baseline region at every reconstructed wavenumber. |
| Post-pump window | 5 ms | Capture approximately 99.5% recovery under the literature biexponential guide while avoiding an unnecessarily long phase series. |
| Minimum pump-shot interval | 250 ms | Provide conservative time for sample reset, acquisition transfer, preservation, and device readiness. Actual intervals may be longer and are reconstructed from observed timing. |
| Repetitions | 1 | Minimize proof-of-concept duration and sample exposure. |

For a 10 cm^-1, 1 ms sweep with 2 ms before-pump coverage, 5 ms after-pump
coverage, and a 5-microsecond phase increment, the plan contains approximately
1,601 pumped phase positions. A 250 ms minimum pump-shot interval gives a nominal
duration of approximately 6.7 minutes before setup and missing-pulse retries.

## Approved exploratory HF2LI change

The existing `campaign_sweep_qualification_candidate` preset is not to be
modified for this proof of concept. A separate exploratory Phase-Scan preset is
to be used so the campaign candidate retains its original settings and meaning.

The exploratory detector demodulators are to start near:

- 20 kSa/s detector-stream rate for both sample and reference;
- 50 to 100 microseconds time constant, with 50 microseconds as the initial
  proof-of-concept value;
- the existing external 2 MHz reference topology and detector assignments;
- the independently configured timing/DIO stream needed to observe Sweep Active,
  wavelength markers, and the electrical pump reference.

The faster detector settings are necessary because the previous 2 kSa/s,
1-millisecond detector configuration would supply only about two detector sample
intervals across a 1 ms sweep and would smear most of a 10 cm^-1 window. The
pump-blocked background and test scan must confirm usable signal-to-noise,
absence of clipping, marker recovery, and successful PicoScope transfer before
photolysis begins.

## Optical preparation still required

- Determine an OPO iris diameter that passes the desired pump wavelength while
  rejecting the visible halos from other wavelengths.
- Center the cleaned pump beam on the MIRcat-probed sample volume and record the
  final iris diameter and OPO wavelength readback.
- Confirm that pump scatter does not reach either infrared detector.
- Locate the sample's main A1 maximum and center the final 10 cm^-1 scan window
  on the observed peak rather than treating a literature value as the measured
  center.
- Confirm positive, unsaturated sample and reference signals on both the HF2LI
  and PicoScope before recording the optical background.

## Validation record

Before the subsequently approved current, cadence, spectral-window, and HF2LI
changes, the exploratory direct-trigger and missing-pulse implementation passed
the offline suite with 151 tests passed, 11 skipped, and 24 subtests passed. The
suite and diff checks must be rerun after each implementation update, and the
result recorded here without treating a software test as hardware validation.

