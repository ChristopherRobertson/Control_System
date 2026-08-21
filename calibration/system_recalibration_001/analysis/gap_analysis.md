# Calibration-gap analysis

## Conclusion

The installed system is **not presently demonstrated fully calibrated**.
Historical canonical values remain comparison-only. Campaign-local results from
completed S0 through T1-01 are valid preserved inputs to the remaining campaign
but have not been canonically promoted. The prior timing procedure did not
cover the complete campaign and conflicted with current safety restrictions.

## Critical conflicts and omissions

1. The obsolete T660-1 CHD route and all executable dependencies on it have been removed. T660-1 CHD is unmapped, disconnected, and unused; no equivalent measurement is scientifically required for the approved topology.
2. An operator-confirmed side experiment established the HF2LI captured-word mapping for MIRcat DB9 pins 1–3 as bits 20, 21, and 22. Campaign-local raw evidence for that side experiment was not supplied, so MD-01 must still verify polarity/state semantics, bidirectional behavior, pulse signatures/counts, timing, and repeatability.
3. Historical canonical timing data contain retired CHD results and raw-source paths under the protected `Control_System` repository. They are comparison-only and cannot validate this run or reintroduce the retired route.
4. MS-01/MS-02 provide run-local Pico A/B skew, splitter branch separation, sensitivities, pulse fidelity, and controlled reconnection evidence. OP-01 measures operational monitor-to-sample latency and subtracts the MS-01 scope-path skew, signed MS-02 drive-minus-monitor branch delay, the OP-01 adapter engineering correction, and detector response delay. The adapter is assigned directly in OP-01 as 0.125 ns with 0.0722 ns rectangular standard uncertainty from a conservative 0–0.25 ns one-way interval; detector latency, saturation/noise/linearity, and sample-plane placement remain unresolved.
5. **Resolved by completed T2-01 and T1-01:** run-local slope/intercept/jitter estimates, pulse fidelity, readbacks, counts, reference planes, controlled corrections, and electrical closure are preserved in their stable phase records. They are imported downstream and are not repeated.
6. The MIRcat DB9 1–3 captured-word bit assignments are accepted from the side experiment, but direction reversal, process-trigger GUI sequence, sweep pulse accounting, active/gap timing, repeated mapping qualification, and host-independent wavelength correlation are not established as a single controlled calibration chain.
7. Spectral alignment still requires authoritative polystyrene features and uncertainty plus authoritative Mylar validation features and uncertainty. Film thickness and quantitative etalon/absolute-film claims are intentionally outside scope.
8. HF2LI demodulator timing, filter response, range/clipping margin, timestamp alignment, cross-stream loss, and full-duration endurance are incomplete.
9. Detector dark noise, drift/stability, cross-talk, per-channel gain/response, linearity, saturation, SNR, and normalization uncertainty are incomplete. The installed sample/reference splitter and downstream paths have not been shown to be 50/50 and must not be assumed equal. ATT-01 measures both splitter ports; DET-02 separates detector/electronics responses; DET-04 establishes the wavelength-dependent detector-plane optical balance, system baseline ratio, covariance, and normalization correction. Results are installed-chain measurements referenced to the qualified available power meter; accredited absolute responsivity is not claimed.
10. Optical Q-switch-to-sample timing lacks the run-local OP-01 adapter record, detector correction, placement uncertainty, bounded shot accounting, blocked control, preview evidence, and restoration repeatability.
11. Complete reference-plane-compatible timing closure, operational delay equation, two-run end-to-end validation, failure recovery, uncertainty budgets, and thesis-claim-to-raw provenance remain outstanding.
12. Retained lightweight software-version records, replacement detector/SIP identity, available-meter qualification, applicable wiring authority, and spectral-reference authority remain incomplete. Device-under-test certificate retrieval and calibrated environmental claims were discarded.
13. Both biological briefs require finite post-iris OPO-540 events at the sample while the Nd:YAG/OPO source remains at its qualified cadence. Command counts, the T660 shot-counter reset, and iris motion do not prove admitted optical events or enforce a finite exposure. FE-01 now qualifies one shared OPO-540 finite-event mechanism with independent optical-event reconciliation and no-emission fault paths.
14. The HRP-C-CO and MbCO briefs require gas-tight aqueous CaF2 sample cells and temperature evidence but those are sample-hardware qualifications rather than calibration corrections. Characterization SC-01 now qualifies only the minimum selected cell/path and 293 K/298 K states using nonbiological blanks; CO loading and protein-state work remain in the experiments.
15. The Coherent WaveMaster is the visible/near-IR wavelength working reference. Its 2026-08-20 query-only connection intake recorded electronic identity, firmware, COM/adapter identities, installed driver, and native query responses without changing settings. The operator confirms that the connected instrument works safely. All phase-entry fields are resolved and preflight is ready; WM-01 still requires separate authorization and must pass before ATT-01. The instrument does not cover the 355 nm drive and cannot determine spectral-power fractions.
16. The permanent ELL15 iris identity, FTDI converter identity, COM observation, driver, native service, and offline tests are registered. Its far-field Z/X/Y mount, accepted 540 nm diameter/tolerance, halo-rejection/core-margin bound, 950 nm home-sensor leakage control, and transfer correction remain ATT-01 outputs. The iris is not a safety shutter, interlock, pulse picker, or finite-event gate.

## Acceptance limits still requiring authoritative inputs

PicoScope timebase accuracy for actual used settings, relevant MIRcat/HF2LI operating limits, detector limits, spectral-reference uncertainty, laser-safe operating constraints, available power-meter specifications, and user-approved engineering closure limits must come from the applicable manufacturer specification or direct campaign measurement. Unknown terms are not assigned zero, but discarded certificates are not execution gates.

## Current classification

`INCOMPLETELY CALIBRATED — PARTIAL CAMPAIGN COMPLETE`.

S0, MS-01, MS-02, T2-01, T1-01, PT-01, MC-01, TR-01, and OM-01 have completed
with preserved phase evidence. These completed measurements are not repeated.
The remaining items above are addressed by the expanded sequence in
`plans/campaign_sequence.md`. WM-01 is the exact next phase, its entry preflight
is ready, and it remains not authorized. ATT-01 follows only after
WM-01 passes. DET-03, DET-04, FE-01, and the RPT-01/PROM-01 reuse package remain
unexecuted. Pump/probe beam performance and the shared nonbiological cell/
temperature qualification are
measured in the separate `system_characterization_001` campaign after its
calibration dependencies are qualified.
