# DET-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | DET01 |
| `measured_quantity` | dark detector and electronics performance at retained settings |
| `physical_reference_plane` | detector outputs |
| `target_reference_plane` | HF2LI Sample and Reference records |
| `measurement_method` | dark short long and revisit records |
| `required_equipment` | detectors HF2LI |
| `wiring_setup` | normal detector wiring |
| `programmed_values` | used gains and ranges for the three retained HF configs only |
| `repetitions` | 1 short plus 1 longest record and 1 revisit per channel/config |
| `raw_data_product` | raw HF2LI time series |
| `correction_terms` | HF2LI noise floor and configuration-specific filter model |
| `type_a_uncertainty` | statistical uncertainty |
| `type_b_uncertainty` | range filter environment and identity |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | detector and HF2LI records |
| `dependencies` | P0-D001 HF01 |
| `closure_test` | repeat and revisit agreement |
| `thesis_or_handoff_destination` | detector table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | yes |
| `effect_of_bypass` | uncertainty and SNR limited |
