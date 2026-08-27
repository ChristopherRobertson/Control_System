# MS-02 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | MS02 |
| `measured_quantity` | splitter branch skew |
| `physical_reference_plane` | splitter input |
| `target_reference_plane` | integral branches S1 and S2 |
| `measurement_method` | normal and swapped S1/S2 captures |
| `required_equipment` | T660-2 Pico CLOCK-SPLITTER-01 |
| `wiring_setup` | non-laser splitter setup with third branch open |
| `programmed_values` | 0 ns |
| `repetitions` | 100 each orientation |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS01 |
| `type_a_uncertainty` | repeatability and reconnect |
| `type_b_uncertainty` | timebase threshold |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with splitter-spec limitation |
| `traceability_source` | splitter ID plus Pico source |
| `dependencies` | MS01 |
| `closure_test` | swap algebra |
| `thesis_or_handoff_destination` | optical timing method |
| `current_status` | PASS COMPLETE |
| `bypass_allowed` | yes |
| `effect_of_bypass` | splitter-corrected results unavailable |

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | MS04 |
| `measured_quantity` | Pico sample interval timebase accuracy settings and sensitivities |
| `physical_reference_plane` | Pico clock and waveform |
| `target_reference_plane` | reported edge time |
| `measurement_method` | settings/readback manual bound and reanalysis |
| `required_equipment` | PicoScope |
| `wiring_setup` | timebase series |
| `programmed_values` | no delay plus representative delays |
| `repetitions` | all completed electrical datasets |
| `raw_data_product` | settings and sensitivity results |
| `correction_terms` | timebase interpolation threshold |
| `type_a_uncertainty` | repeatability |
| `type_b_uncertainty` | manufacturer specification and model choice |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with manufacturer-spec basis |
| `traceability_source` | Pico serial and applicable manufacturer specification |
| `dependencies` | MS01 |
| `closure_test` | residual consistency |
| `thesis_or_handoff_destination` | uncertainty budget |
| `current_status` | COMPLETE VIA MS-02 ANALYSIS |
| `bypass_allowed` | yes |
| `effect_of_bypass` | timing uncertainty incomplete |
