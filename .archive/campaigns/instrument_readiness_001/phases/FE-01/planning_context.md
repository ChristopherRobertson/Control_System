# FE-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | FE01 |
| `measured_quantity` | finite emitted-pump-event control and reconciliation |
| `physical_reference_plane` | approved pump command and optical gate |
| `target_reference_plane` | independently observed admitted event at sample-equivalent plane |
| `measurement_method` | blocked one-event finite-block and no-emission fault tests |
| `required_equipment` | T660s pump sources optical gate or divider event monitor and static qualified electronic iris for OPO-540 |
| `wiring_setup` | permanent-iris OPO-540 path shared by HRP then MbCO |
| `programmed_values` | qualified NdYAG/OPO cadence plus CH-00 rare-event limits; iris aperture remains static |
| `repetitions` | zero plus 1 event plus 1 finite block; no-emission fault cases |
| `raw_data_product` | command and observed-event ledgers traces iris configuration/readbacks and restoration |
| `correction_terms` | OP01 event latency and monitor response |
| `type_a_uncertainty` | event-count and iris-configuration repeatability |
| `type_b_uncertainty` | gate leakage missed/double event clock monitor uncertainty and ATT01 iris validity |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | manufacturer controls ATT01 OP01 and observed events |
| `dependencies` | MC01 HF01 ATT01 OP01 |
| `closure_test` | exact finite count normal stop mismatch stop safe restoration and unchanged iris setpoint |
| `thesis_or_handoff_destination` | finite-exposure control table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | no |
| `effect_of_bypass` | biological exposure cannot be bounded |
