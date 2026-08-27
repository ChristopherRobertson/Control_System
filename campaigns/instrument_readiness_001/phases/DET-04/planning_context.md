# DET-04 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | DET04 |
| `measured_quantity` | installed optical balance and normalization at merged probe anchors |
| `physical_reference_plane` | common incident QCL plane |
| `target_reference_plane` | sample and reference detector planes |
| `measurement_method` | paired optical power and electrical output |
| `required_equipment` | qualified meter splitter detectors amplifiers and HF2LI |
| `wiring_setup` | final installed paths |
| `programmed_values` | same merged anchors and low/high powers as DET02;one retained polarization/alignment |
| `repetitions` | 3 readings per point plus 1 controlled realignment |
| `raw_data_product` | raw dual-port detector-plane and simultaneous electrical records |
| `correction_terms` | ATT01 optical split DET02 channel response and backgrounds |
| `type_a_uncertainty` | repeatability drift covariance and realignment |
| `type_b_uncertainty` | meter placement polarization interpolation channel gain and nonlinearity |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | OM01 ATT01 DET01 DET02 records |
| `dependencies` | P0-D001 ATT01 DET01 DET02 HF01 |
| `closure_test` | system baseline equals optical balance times detector balance |
| `thesis_or_handoff_destination` | normalization table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | no |
| `effect_of_bypass` | quantitative dual-detector absorbance blocked |
