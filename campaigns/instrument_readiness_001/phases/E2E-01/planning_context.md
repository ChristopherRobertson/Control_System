# E2E-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | E2E01 |
| `measured_quantity` | three retained experiment-specific end-to-end workflows |
| `physical_reference_plane` | normal configured platform |
| `target_reference_plane` | processed axes finite events and safe stop |
| `measurement_method` | one probe-only sweep plus HRP-style and MbCO-style rare-pump nonbiological runs |
| `required_equipment` | all installed equipment including the permanent electronic iris when OPO-540 is used |
| `wiring_setup` | normal wiring and locked ATT01 iris mount |
| `programmed_values` | one retained sweep config plus separate HRP and MbCO config IDs with qualified post-iris OPO-540 |
| `repetitions` | 3 runs total; no-emission fault only if orchestration differs from FE01 |
| `raw_data_product` | all native streams manifests ledgers iris command/readbacks and logs |
| `correction_terms` | all retained corrections including ATT01 iris DET04 FE01 and configuration-specific filter terms |
| `type_a_uncertainty` | cross-run topology and configuration checks |
| `type_b_uncertainty` | component budgets |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | complete calibration chain |
| `dependencies` | ATT01 CL01 SP02 HF02 DET02 DET04 FE01 |
| `closure_test` | artifact timing event iris-mismatch stop normalization and configuration-ID checks |
| `thesis_or_handoff_destination` | validation table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | no |
| `effect_of_bypass` | full calibration impossible |
