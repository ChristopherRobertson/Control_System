# T1-01 final report

Status: **PASS — T1-01 COMPLETE; PT-01 NOT STARTED**

Operator: Christopher Robertson

## Final route results

- T660-1 TRIG IN to FIRE: `50.7471 ns ± 3.1419 ns` standard uncertainty.
- FIRE to Q-SWITCH: `0.149286 ns ± 0.951338 ns` standard uncertainty.
- T660-1 TRIG IN to Q-SWITCH: `50.9372 ns ± 3.0676 ns` standard uncertainty.
- Direct-versus-derived EXT REF to Q-SWITCH closure residual: `0.0407522 ns` — PASS.

The T660-1 fits used six programmed delays from 0 ns through 1 ms. Final
trigger-input route intercepts subtract the T2-01 EXT REF-to-T660-1-TRIG-IN
intercept from the adapter-corrected T1 direct measurements.

## Adapter characterization

Normal and swapped splitter orientations each accepted 100/100 traces. The
resulting delays are Adapter A `6.43913 ns ± 0.322384 ns` and Adapter B
`6.34175 ns ± 0.322384 ns`. These corrections remove Adapter A from the
direct routes; adapter reversal isolates FIRE-to-Q-SWITCH without assigning
either adapter a zero delay.

## Evidence and final state

- 2,600 accepted measurement traces were retained.
- No trace from a valid measurement configuration was rejected.
- The 300 initial-wiring traces remain preserved as rejected evidence.
- Trigger-count diagnostics and chain closure passed.
- The operator confirmed default wiring restoration on 2026-08-13.
- Final safe idle matched with no mismatches.
- No canonical calibration output was promoted.
- PT-01 and later phases were not started.

The PicoScope calibration certificate and calibration age remain
`USER_INPUT_REQUIRED` as a claim limitation.
