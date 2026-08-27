# Predeclared three-point HF2LI model validation design

These points were frozen before any HF-01 response data were viewed. They are
instrument-model anchors, not experiment presets.

The readback utility must confirm each value is supported before acquisition;
unsupported values are quantized by the device and the actual readback is
recorded before any data. One active measurement demodulator is used initially
so aggregate output-rate limits are unambiguous.

| Anchor ID | Order | Time constant | Predicted -3 dB cutoff | Initial output rate | Normalized offset-carrier tests | Role |
|---|---:|---:|---:|---:|---|---|
| `HF01-ANCHOR-FAST-001` | 1 | 4 us | 39,800 Hz | 460 kSa/s | +3,980; +39,800; +199,000 Hz | Short-time/low-order anchor, chosen so the native rate exceeds 8 times cutoff while spanning the fastest practical readout region. |
| `HF01-ANCHOR-INTERMEDIATE-001` | 4 | 1 ms | 69.2 Hz | 2 kSa/s | +6.92; +69.2; +346 Hz and -69.2 Hz | Repository provisional order-four point and sign-asymmetry anchor. |
| `HF01-ANCHOR-SLOW-001` | 8 | 100 ms | 0.479 Hz | 10 Sa/s | +0.0479; +0.479; +2.395 Hz | Long-time/high-order, low-noise/settling anchor. |

For each anchor the stimulus is a monitored carrier at `2 MHz + f_offset`.
Each anchor also contains a connected-zero baseline/noise interval and three
independent rising plus three independent falling 2 MHz carrier steps. Segment
duration is at least the manufacturer 99% settling prediction plus 20%, with a
minimum of three independent analysis windows.

No fourth point is allowed unless `HF01-MODEL-RESIDUAL-v1` fails and localizes
an unbounded region. The extra point must be chosen from that region before its
data are viewed. If it also fails, acquisition stops for prospective amendment.
