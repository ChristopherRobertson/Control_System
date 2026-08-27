# OP-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | OP01 |
| `measured_quantity` | pump-command-to-sample timing for the shared retained biological optical path under separate acquisition configurations |
| `physical_reference_plane` | T660-1 CHB command plane |
| `target_reference_plane` | sample-equivalent optical plane |
| `measurement_method` | electrical monitor plus optical detector capture |
| `required_equipment` | T660s Pico splitter adapter detector NdYAG OPO and static qualified electronic iris for OPO-540 |
| `wiring_setup` | permanent-iris OPO-540 path shared by HRP then MbCO |
| `programmed_values` | separate HRP and MbCO HF2LI configuration IDs on one optical timing path |
| `repetitions` | blocked plus 1 preview plus prospective count capped at 100 |
| `raw_data_product` | raw traces shot ledger layout iris and HF2LI command-readback/configuration and correction records |
| `correction_terms` | MS01 MS02 adapter DET03 ATT01 iris/path and configuration-specific filter corrections |
| `type_a_uncertainty` | shot jitter placement and configuration repeatability |
| `type_b_uncertainty` | detector placement timebase splitter adapter path wavelength iris and filter validity |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | completed timing and retained detector/metrology/iris records |
| `dependencies` | S0 MS01 MS02 DET02 DET03 OM01 ATT01 HF01 |
| `closure_test` | corrected repeatability for the qualified post-iris 540 path under both acquisition IDs |
| `thesis_or_handoff_destination` | optical timing table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | yes |
| `effect_of_bypass` | pump scheduling latency unavailable |
