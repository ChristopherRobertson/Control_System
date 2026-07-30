# Calibration-gap analysis

## Conclusion

The installed system is **not presently demonstrated fully calibrated**. Existing values are historical comparison data only. The prior timing procedure covers useful electrical timing concepts but does not cover the complete campaign and conflicts with current safety restrictions.

## Critical conflicts and omissions

1. The obsolete T660-1 CHD route and all executable dependencies on it have been removed. T660-1 CHD is unmapped, disconnected, and unused; no equivalent measurement is scientifically required for the approved topology.
2. An operator-confirmed side experiment established the HF2LI captured-word mapping for MIRcat DB9 pins 1–3 as bits 20, 21, and 22. Campaign-local raw evidence for that side experiment was not supplied, so MD-01 must still verify polarity/state semantics, bidirectional behavior, pulse signatures/counts, timing, and repeatability.
3. Historical canonical timing data contain retired CHD results and raw-source paths under the protected `Control_System` repository. They are comparison-only and cannot validate this run or reintroduce the retired route.
4. MS-01/MS-02 provide run-local Pico A/B skew, splitter branch separation, sensitivities, pulse fidelity, and controlled reconnection evidence. OP-01 measures operational monitor-to-sample latency and subtracts the MS-01 scope-path skew, signed MS-02 drive-minus-monitor branch delay, the OP-01 adapter engineering correction, and detector response delay. The adapter is assigned directly in OP-01 as 0.125 ns with 0.0722 ns rectangular standard uncertainty from a conservative 0–0.25 ns one-way interval; detector latency, saturation/noise/linearity, and sample-plane placement remain unresolved.
5. Direct-route and cross-generator results need rerun-local slope/intercept/jitter estimates at every required delay, pulse fidelity, readbacks, counts, reference planes, controlled corrections, and closure.
6. The MIRcat DB9 1–3 captured-word bit assignments are accepted from the side experiment, but direction reversal, process-trigger GUI sequence, sweep pulse accounting, active/gap timing, repeated mapping qualification, and host-independent wavelength correlation are not established as a single controlled calibration chain.
7. Absolute spectral calibration lacks verified reference-material provenance and uncertainty. Without it, only relative repeatability/hysteresis/effective sampling may be claimed.
8. HF2LI demodulator timing, filter response, range/clipping margin, timestamp alignment, cross-stream loss, and full-duration endurance are incomplete.
9. Detector dark noise, drift/stability, cross-talk, relative gain, linearity, saturation, SNR, and normalization uncertainty are incomplete; absolute responsivity is unavailable absent a traceable optical-power standard.
10. Optical Q-switch-to-sample timing lacks the run-local OP-01 adapter record, detector correction, placement uncertainty, bounded shot accounting, blocked control, preview evidence, and restoration repeatability.
11. Complete reference-plane-compatible timing closure, operational delay equation, two-run end-to-end validation, failure recovery, complete GUM budgets, and article-to-raw traceability remain outstanding.
12. Software/driver/firmware versions, certificates, cable/splitter/adapter/detector IDs, environmental conditions, and spectral-reference identity are incomplete.

## Acceptance limits still requiring authoritative inputs

PicoScope timebase accuracy, resolution-specific sample interval behavior, bandwidth/range accuracy; T660 delay accuracy/jitter/amplitude specifications; MIRcat sweep/trigger tolerances; HF2LI clock/demodulator specifications; detector limits; spectral reference uncertainty; cable propagation specifications; laser-safe operating constraints; and user-approved engineering closure limits must be extracted from manuals/certificates or measured noise before execution. Unknown terms will not be assigned zero.

## Current classification

`INCOMPLETELY CALIBRATED` (pre-campaign assessment). This is not a failure result; the new campaign has not begun hardware execution.
