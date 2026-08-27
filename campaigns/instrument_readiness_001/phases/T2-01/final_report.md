# T2-01 final report

Status: **PASS — T2-01 COMPLETE; T1-01 NOT STARTED**

Operator: Christopher Robertson

## Acquisition and correction

- Three installed T660-2 channel-plus-route measurements were completed over
  0 ns, 100 ns, 1 us, 10 us, 100 us, and 1 ms.
- Each route contains 100 accepted captures at each delay: 1,800 accepted
  traces total and zero rejected traces.
- Physical timing is corrected by subtracting the MS-02 PicoScope CHB-minus-CHA
  value `0.109947073 ns`, combined standard uncertainty `0.581707394 ns`.
- Positive timing means the destination-route event arrived after the final
  HF2LI EXT REF cable-end event.

## Route results

| Installed route | Corrected fitted intercept (ns) | Combined standard uncertainty (ns) | Slope | Slope deviation (ppm) | Slope uncertainty (ppm) | Residual RMS (ns) |
|---|---:|---:|---:|---:|---:|---:|
| EXT REF -> HF2LI DAQ | 0.948750 | 0.694521 | 1.000006752 | 6.752 | 3.743 | 0.046545 |
| EXT REF -> MIRcat TRIG IN | 11.350148 | 0.695142 | 1.000006542 | 6.542 | 3.749 | 0.056715 |
| EXT REF -> T660-1 TRIG IN | 0.133764 | 0.694360 | 1.000006753 | 6.753 | 3.746 | 0.025435 |

The combined intercept uncertainties include fit uncertainty, the common
MS-02 correction uncertainty, and threshold half-range treated as a
rectangular contribution. They do not invent an unavailable calibration-
certificate term.

## Pulse fidelity and sensitivities

- All measured polarities were positive.
- EXT REF/DAQ mean amplitudes: `5.071 V` / `5.098 V`; mean widths:
  `149.801 ns` / `149.804 ns`.
- EXT REF/MIRcat mean amplitudes: `5.067 V` / `5.199 V`; mean widths:
  `149.866 ns` / `149.766 ns`.
- EXT REF/T660-1-trigger mean amplitudes: `5.069 V` / `5.076 V`; mean widths:
  `149.881 ns` / `9999.953 ns`. The 10 us CHD width is the authoritative
  T660-1 trigger-input test recipe. Every replacement trace contained the
  falling edge; unavailable target widths: zero.
- Per-delay jitter sample standard-deviation ranges were `0.195–0.547 ns`,
  `0.077–2.527 ns`, and `0.134–1.855 ns`, respectively.
- Maximum threshold half-ranges were `0.0245 ns`, `0.0586 ns`, and `0.0231 ns`.
- Mean absolute linear-versus-nearest-sample interpolation differences were
  `0.675 ns`, `0.686 ns`, and `0.549 ns`. Linear interpolation is the reported
  timing estimator; full diagnostics and six fit residuals per route are in
  each `analysis.json` and `t2_01_results.json`.

## Corrected Setup 3 acquisition

The first Setup 3 capture policy placed some 10 us falling edges at the window
boundary. The shared planner was corrected to reserve programmed delay, target
pulse width, and post-edge margin; acceptance now requires both edges,
post-edge samples, and no overflow. The complete six-point replacement agreed
with the prior timing (intercept difference `0.00484 ns`, slope difference
`0.249 ppm`) and became the sole in-repository Setup 3 record. The superseded
record was moved under explicit operator authorization to
`C:\Users\Chris\Documents\GitHub\Control_System_Archives\Calibration\T2-01_unused`.

## Restoration and unresolved metadata

- The operator confirmed CHA -> HF2LI EXT REF, CHC -> HF2LI DAQ, CHB -> MIRcat
  TRIG IN, and CHD -> T660-1 TRIG IN were restored.
- CLOCK-SPLITTER-01 remained in normal clock distribution.
- Final safe idle matched the repository recipe: both trigger sources OFF and
  all eight T660 outputs OFF.
- `USER_INPUT_REQUIRED`: PicoScope calibration certificate and calibration
  age. Reported amplitudes use the configured 10 V range and nominal ADC
  conversion and do not claim certificate-level voltage accuracy.
- No canonical calibration output was promoted. T1-01 was not started.
