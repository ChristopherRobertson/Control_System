# MD-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | MD01 |
| `measured_quantity` | retained MIRcat DB9 mapping qualification |
| `physical_reference_plane` | MIRcat DB9 pins 1-3 plus pin-4 process state |
| `target_reference_plane` | HF2LI complete DIO word |
| `measurement_method` | campaign confirmation of accepted mapping |
| `required_equipment` | MIRcat HF2LI T660 |
| `wiring_setup` | normal DB9 1-4 only; reserved pins excluded |
| `programmed_values` | one retained sweep config in both directions plus point/process sequences under separate HRP and MbCO config IDs |
| `repetitions` | 3 scans per direction plus 3 point/process repeats per biological config |
| `raw_data_product` | complete DIO stream and MIRcat log |
| `correction_terms` | timestamp alignment |
| `type_a_uncertainty` | repeatability |
| `type_b_uncertainty` | logic threshold and state semantics |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | accepted side mapping plus manuals |
| `dependencies` | MC01 HF01 |
| `closure_test` | direction marker active and process signatures under all applicable configurations |
| `thesis_or_handoff_destination` | wiring table |
| `current_status` | MAPPING ACCEPTED; CAMPAIGN MEASUREMENTS NOT STARTED |
| `bypass_allowed` | no |
| `effect_of_bypass` | axis and point/process segmentation blocked |
