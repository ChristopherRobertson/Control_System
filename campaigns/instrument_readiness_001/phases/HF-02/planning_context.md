# HF-02 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | HF02 |
| `measured_quantity` | cross-stream alignment loss and maximum-duration integrity |
| `physical_reference_plane` | common physical events |
| `target_reference_plane` | Sample Reference and DIO streams |
| `measurement_method` | three retained maximum-duration captures |
| `required_equipment` | HF2LI MIRcat T660 |
| `wiring_setup` | normal wiring |
| `programmed_values` | one longest continuous sweep plus one longest HRP recovery and one retained MbCO stream |
| `repetitions` | 1 record per retained configuration; biological reuse only after HF01 equivalence and identical duration envelope |
| `raw_data_product` | raw streams and loss log |
| `correction_terms` | stream latency |
| `type_a_uncertainty` | configuration comparison |
| `type_b_uncertainty` | clock API buffering and host timing |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | HF2LI manual |
| `dependencies` | HF01 MD01 MSW01 |
| `closure_test` | cross-stream alignment and zero-loss acceptance |
| `thesis_or_handoff_destination` | acquisition table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | no |
| `effect_of_bypass` | end-to-end axis or recovery timing blocked |
