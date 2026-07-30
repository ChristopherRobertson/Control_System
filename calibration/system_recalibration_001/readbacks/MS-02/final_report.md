# MS-02 final report

Status: **PASS — MS-02 COMPLETE**

Sign convention: B minus A; positive means CHB arrived later. Splitter sign is
S2 minus S1.

## Acquisition and reconnection

- Reused MS-01: 100 normal and 100 swapped accepted captures.
- MS-02 reconnection: 100 normal and 100 swapped accepted captures.
- Rejected captures: zero in both MS-02 orientations.
- Scope/path reconnection difference: `-0.020058898 ns`.
- Splitter reconnection difference: `+0.008218018 ns`.
- Reconnection uncertainty uses half the two-realization range.

## MS-02 result

The estimate is the midpoint of the two complete connection realizations.

- PicoScope channel/path skew B-A:
  `0.109947073 ± 0.581707394 ns` combined standard uncertainty.
- Splitter branch skew S2-S1:
  `0.013383015 ± 0.577390856 ns` combined standard uncertainty.

## Sensitivities and pulse fidelity

- Threshold band: 3000–7000 ADC around the operational 5000-ADC threshold.
- Scope threshold half-range: `0.005605248 ns`.
- Splitter threshold half-range: `0.002831776 ns`.
- Scope interpolation-method difference: `0.069976522 ns`.
- Splitter interpolation-method difference: `0.000725993 ns`.
- PicoScope timebase 1; sample interval `2 ns`; configured data-sheet bound
  `±2 ppm`.
- Mean pulse width across orientations/channels: approximately
  `149.93–149.95 ns`.
- Mean 10–90% rise time: approximately `6.99–7.03 ns`.

## USER_INPUT_REQUIRED

- PicoScope calibration certificate and calibration age.
- CLOCK-SPLITTER-01 manufacturer bandwidth, insertion-loss, and impedance
  specifications.
- A multi-cycle reconnection distribution was not measured; the controlled
  evidence contains two complete connection realizations.

## Restoration and final state

- Operator confirmed EXT REF and normal CLOCK-SPLITTER-01 distribution restored.
- Final safe-idle readback matched with no mismatches: both trigger sources OFF
  and all eight T660 outputs OFF.
- Every later phase was not started.
