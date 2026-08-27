# MSW-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | MSW01 |
| `measured_quantity` | retained sweep and point-tune timing |
| `physical_reference_plane` | MIRcat sweep or point command |
| `target_reference_plane` | DIO markers active state and tuned point |
| `measurement_method` | continuous and discrete timing capture |
| `required_equipment` | MIRcat HF2LI T660 |
| `wiring_setup` | normal wiring |
| `programmed_values` | one CH-00-selected sweep speed and marker config plus point-tune sequences under separate HRP and MbCO config IDs |
| `repetitions` | 3 scans per direction plus 3 point sequences per biological config |
| `raw_data_product` | raw HF2LI DIO and MIRcat records |
| `correction_terms` | timestamp alignment |
| `type_a_uncertainty` | count and timing repeatability |
| `type_b_uncertainty` | clock edge process semantics and configuration-specific sampling |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | MIRcat and HF2LI sources |
| `dependencies` | MD01 HF01 |
| `closure_test` | expected counts measured spacing and point-state closure under all applicable configurations |
| `thesis_or_handoff_destination` | sweep and point timing table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | no |
| `effect_of_bypass` | wavelength axis and point timing blocked |
