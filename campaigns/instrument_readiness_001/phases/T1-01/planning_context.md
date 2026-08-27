# T1-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | T101 |
| `measured_quantity` | T660-1 trigger to FIRE |
| `physical_reference_plane` | T660-1 trigger pin arrival |
| `target_reference_plane` | NdYAG pin-7 cable-end arrival |
| `measurement_method` | two-channel edge capture |
| `required_equipment` | T660s Pico approved breakout |
| `wiring_setup` | destination/reference to Pico |
| `programmed_values` | 0;100ns;1us;10us;100us;1ms |
| `repetitions` | 100 accepted per point |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS01 breakout delay |
| `type_a_uncertainty` | shot jitter |
| `type_b_uncertainty` | timebase threshold load |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with manufacturer-spec basis |
| `traceability_source` | direct T660 results plus Pico serial/specification |
| `dependencies` | T203 MS01 |
| `closure_test` | EXTREF-to-FIRE closure |
| `thesis_or_handoff_destination` | electrical table |
| `current_status` | PASS COMPLETE IN T1-01 |
| `bypass_allowed` | yes |
| `effect_of_bypass` | FIRE chain blocked |

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | T102 |
| `measured_quantity` | T660-1 trigger to Q-switch |
| `physical_reference_plane` | T660-1 trigger pin arrival |
| `target_reference_plane` | NdYAG pin-6 cable-end arrival |
| `measurement_method` | two-channel edge capture |
| `required_equipment` | T660s Pico approved breakout |
| `wiring_setup` | destination/reference to Pico |
| `programmed_values` | 0;100ns;1us;10us;100us;1ms |
| `repetitions` | 100 accepted per point |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS01 breakout delay |
| `type_a_uncertainty` | shot jitter |
| `type_b_uncertainty` | timebase threshold load |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with manufacturer-spec basis |
| `traceability_source` | direct T660 results plus Pico serial/specification |
| `dependencies` | T203 MS01 |
| `closure_test` | EXTREF-to-Q closure |
| `thesis_or_handoff_destination` | electrical table |
| `current_status` | PASS COMPLETE IN T1-01 |
| `bypass_allowed` | yes |
| `effect_of_bypass` | Q-switch chain blocked |

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | T103 |
| `measured_quantity` | FIRE to Q-switch |
| `physical_reference_plane` | NdYAG pin-7 arrival |
| `target_reference_plane` | NdYAG pin-6 arrival |
| `measurement_method` | two-channel edge capture |
| `required_equipment` | T660s Pico approved breakout |
| `wiring_setup` | both disconnected device lines to Pico |
| `programmed_values` | 0;100ns;1us;10us;100us;1ms |
| `repetitions` | 100 accepted per point |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS01 breakout skew |
| `type_a_uncertainty` | shot jitter |
| `type_b_uncertainty` | timebase threshold loads |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with manufacturer-spec basis |
| `traceability_source` | direct T660 results plus Pico serial/specification |
| `dependencies` | T101 T102 |
| `closure_test` | direct-versus-derived Q closure |
| `thesis_or_handoff_destination` | electrical table |
| `current_status` | PASS COMPLETE IN T1-01 |
| `bypass_allowed` | yes |
| `effect_of_bypass` | Q closure unavailable |

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | T104 |
| `measured_quantity` | EXT REF to FIRE |
| `physical_reference_plane` | HF2LI EXT REF cable-end arrival |
| `target_reference_plane` | NdYAG pin-7 arrival |
| `measurement_method` | two-channel edge capture |
| `required_equipment` | T660s Pico |
| `wiring_setup` | destination ends to Pico |
| `programmed_values` | 0;100ns;1us;10us;100us;1ms |
| `repetitions` | 100 accepted per point |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS01 |
| `type_a_uncertainty` | shot jitter |
| `type_b_uncertainty` | timebase threshold loads |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with manufacturer-spec basis |
| `traceability_source` | direct T660 results plus Pico serial/specification |
| `dependencies` | T203 T101 |
| `closure_test` | derived T203+T101 |
| `thesis_or_handoff_destination` | electrical table |
| `current_status` | PASS COMPLETE IN T1-01 |
| `bypass_allowed` | yes |
| `effect_of_bypass` | FIRE closure unavailable |

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | T105 |
| `measured_quantity` | EXT REF to Q-switch |
| `physical_reference_plane` | HF2LI EXT REF cable-end arrival |
| `target_reference_plane` | NdYAG pin-6 arrival |
| `measurement_method` | two-channel edge capture |
| `required_equipment` | T660s Pico |
| `wiring_setup` | destination ends to Pico |
| `programmed_values` | 0;100ns;1us;10us;100us;1ms |
| `repetitions` | 100 accepted per point |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS01 |
| `type_a_uncertainty` | shot jitter |
| `type_b_uncertainty` | timebase threshold loads |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with manufacturer-spec basis |
| `traceability_source` | direct T660 results plus Pico serial/specification |
| `dependencies` | T203 T102 |
| `closure_test` | direct versus T104+T103 and T203+T102 |
| `thesis_or_handoff_destination` | closure table |
| `current_status` | PASS COMPLETE IN T1-01 |
| `bypass_allowed` | no |
| `effect_of_bypass` | complete chain cannot pass |
