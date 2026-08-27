# CL-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | CL01 |
| `measured_quantity` | timing closure for retained path and configurations |
| `physical_reference_plane` | compatible electrical and optical planes |
| `target_reference_plane` | continuous-sweep HRP rare-pump and MbCO rare-pump chemical origins |
| `measurement_method` | covariance-aware analysis only |
| `required_equipment` | no rewire |
| `wiring_setup` | operational retained configurations |
| `programmed_values` | qualified post-iris OPO-540;probe sweep;HRP fixed point and longest record;MbCO fixed point and retained record |
| `repetitions` | all accepted component datasets |
| `raw_data_product` | closure CSV clock-bridge records and iris/HF2LI configuration foreign keys |
| `correction_terms` | documented configuration-specific correction model |
| `type_a_uncertainty` | propagated Type A |
| `type_b_uncertainty` | correlated Type B |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | component calibrations |
| `dependencies` | T201-T105 PT01 ATT01 OP01 FE01 HF01 |
| `closure_test` | all retained loops both biological record bridges and static iris validity |
| `thesis_or_handoff_destination` | closure table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | no |
| `effect_of_bypass` | full calibration impossible |
