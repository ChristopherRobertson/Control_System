# MS-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | MS01 |
| `measured_quantity` | Pico A-B differential skew |
| `physical_reference_plane` | common pulse split plane |
| `target_reference_plane` | Pico A and B digitized edges |
| `measurement_method` | normal and channel-exchanged S1/S2 captures |
| `required_equipment` | T660-2 Pico CLOCK-SPLITTER-01 |
| `wiring_setup` | dedicated non-laser setup with integral S1/S2 directly to scope and third branch open |
| `programmed_values` | 0 ns |
| `repetitions` | 100 each orientation |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | edge model and path assignment |
| `type_a_uncertainty` | repeatability |
| `type_b_uncertainty` | sampling timebase threshold |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with manufacturer-spec basis |
| `traceability_source` | Pico serial and applicable manufacturer specification |
| `dependencies` | S0 |
| `closure_test` | orientation algebra |
| `thesis_or_handoff_destination` | electrical timing method |
| `current_status` | PASS COMPLETE |
| `bypass_allowed` | yes |
| `effect_of_bypass` | all two-channel timing provisional |
