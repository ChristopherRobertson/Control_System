# CH-00 acceptance criteria and uncertainty allocation

Criterion set: `CH00-AU-v1`

## Phase-close criteria

CH-00 passes only when every retained claim maps to a measurement class and
phase, the two-region/three-source/two-topology grid is frozen, every optional
extension is excluded, calibration dependencies have explicit validity states,
P0 decisions are imported, and configuration, exposure, uncertainty, and
identity conventions are fixed. All criteria pass in this record.

## Downstream acceptance rules

- Each quantitative result must identify its measurement plane, units,
  correction state, configuration ID, analysis version, and standard or
  expanded uncertainty. Missing inputs are `USER_INPUT_REQUIRED`, never zero.
- A retained endpoint or revisit is accepted only under its phase's frozen
  repeatability, residual, saturation, drift, and safe-restoration checks. A
  midpoint may be added only after the named endpoint-linearity rule fails.
- The sweep topology must support the independently frozen polystyrene fit and
  Mylar holdout without using Mylar or biological data to revise the correction.
- The point topology must support the retained HRP bands and MbCO A1 plus one
  shared off-band control, with measured settling, temporal response, event
  admission, loss accounting, and longest-recovery clock closure.
- Manufacturer-only values remain specifications. Unmeasured capabilities are
  unvalidated. Derived mean pulse energy is allowed only from measured average
  power and verified repetition rate and must retain that limitation.
- No downstream phase may pass if its calibration link is pending, outside its
  validity envelope, or missing a stated uncertainty/limitation. Hash or
  checksum equality is never an operational acceptance condition.

## Uncertainty allocation

| Family | Required contributors | Allocated owner |
|---|---|---|
| Spectral position/shape | SP-02 axis covariance, authoritative feature uncertainty, scan direction, fitting, DET-04 normalization, repeatability | SP-02, SV-01, SV-02 |
| Average power/transfer | meter basis, wavelength/range correction, zero/background, repeatability, attenuation, placement, drift | OM-01, ATT-01, PB-01, PB-02, OG-01 |
| Timing/IRF | MS-01/MS-02 path correction, T-route fits, PT-01, OP-01, FE-01, CL-01, DET-03, threshold/interpolation, repeatability | calibration phases and IR-01 |
| Acquisition response | HF filter response, dwell, scan direction, timestamp alignment/loss, detector response, covariance | HF-01, HF-02, AR-01, PF-01 |
| Geometry/overlap | scale, profile convention, placement, transfer, polarization, realignment, overlap model | OG-01, OV-01 |
| Reproducibility | within-run, between-run, restoration/reinstallation, observational environment | RP-01 |

Correlated inputs remain correlated in propagation; shared measurements are
linked once rather than treated as independent duplicates. Numeric tolerances
that depend on instrument performance remain phase-resolved and cannot be
invented at CH-00.
