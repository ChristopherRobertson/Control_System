# PT-01 final report

Campaign: `system_recalibration_001`  
Phase run: `system_recalibration_001_PT-01_001`  
Decision: **PASS — PT-01 CLOSED AT NON-EMITTING ELECTRICAL BOUNDARY**

## Result

The approved FIRE reference to MIRcat Process Trigger pin-4 route was measured
at six programmed delays from 0 ns through 1 ms. All 600 required traces were
accepted and zero were rejected. Raw attempts, settings, recipes, command logs,
operator confirmations, and both provisional and corrected analyses are
retained.

The MS-02 PicoScope CHB-minus-CHA correction and T1-01 Adapter B-minus-A
correction produce a zero-programmed-delay route intercept of `-5.48577 ns`
with combined standard uncertainty `13.4873 ns`. Slope error is `4.36180 ppm`;
fit residual RMS is `0.440978 ns`; maximum threshold half-range sensitivity is
`1.42956 ns`. Jitter standard deviation spans `9.03911–29.7387 ns` across the
six points.

Both measured lines are active low. FIRE pulse width averaged approximately
`9.99643 us`; Process Trigger pulse width averaged `10.000020 ms`, consistent
with the approved nominal 10 ms active-low process-trigger recipe. Reference
planes and correction signs are explicit in `reference_planes.md`.

## Safety, retention, and restoration

The initial preflight passed previously and was not rerun. Setup 1 received
operator confirmation and post-connection safe idle passed before outputs were
enabled. The Nd:YAG and MIRcat destination connectors were physically isolated
during acquisition; neither laser emitted. Pin 5, pins 6/8, and T660-1 CHD were
excluded. No sample, CO, or biological work occurred.

The acquisition finalizer returned the T660s to safe idle. The operator then
restored default wiring, and the final restoration safe-idle readback passed
with zero mismatches. Both T660 trigger sources and all outputs are disabled.
No splitter was moved. No canonical calibration promotion occurred.

## Closeout decision

All mandatory PT-01 measurement, uncertainty, retention, operator connection,
restoration, and safe-idle deliverables are complete. **MC-01 is the exact next
calibration phase and remains not started and unauthorized.**
