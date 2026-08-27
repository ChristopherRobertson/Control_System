# T2-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | T201 |
| `measured_quantity` | EXT REF to DAQ timing |
| `physical_reference_plane` | HF2LI DIO0 cable-end arrival |
| `target_reference_plane` | HF2LI DIO1 cable-end arrival |
| `measurement_method` | two-channel edge capture |
| `required_equipment` | T660-2 Pico final cables |
| `wiring_setup` | destination ends to Pico A/B |
| `programmed_values` | 0;100ns;1us;10us;100us;1ms |
| `repetitions` | 100 accepted per point |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS01 measurement-only paths |
| `type_a_uncertainty` | shot jitter |
| `type_b_uncertainty` | timebase threshold reconnection |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with manufacturer-spec basis |
| `traceability_source` | direct T660 results plus Pico serial/specification |
| `dependencies` | S0 MS01 MS04 |
| `closure_test` | fit residual and monotonicity |
| `thesis_or_handoff_destination` | electrical table |
| `current_status` | PASS COMPLETE IN T2-01 |
| `bypass_allowed` | yes |
| `effect_of_bypass` | DAQ timing unavailable |

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | T202 |
| `measured_quantity` | EXT REF to MIRcat TRIG IN |
| `physical_reference_plane` | HF2LI DIO0 cable-end arrival |
| `target_reference_plane` | MIRcat TRIG IN cable-end arrival |
| `measurement_method` | two-channel edge capture |
| `required_equipment` | T660-2 Pico final cables |
| `wiring_setup` | destination ends to Pico A/B |
| `programmed_values` | 0;100ns;1us;10us;100us;1ms |
| `repetitions` | 100 accepted per point |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS01 |
| `type_a_uncertainty` | shot jitter |
| `type_b_uncertainty` | timebase threshold reconnection |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with manufacturer-spec basis |
| `traceability_source` | direct T660 results plus Pico serial/specification |
| `dependencies` | S0 MS01 MS04 |
| `closure_test` | fit residual |
| `thesis_or_handoff_destination` | electrical table |
| `current_status` | PASS COMPLETE IN T2-01 |
| `bypass_allowed` | yes |
| `effect_of_bypass` | MIRcat timing unavailable |

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | T203 |
| `measured_quantity` | EXT REF to T660-1 TRIG IN |
| `physical_reference_plane` | HF2LI DIO0 cable-end arrival |
| `target_reference_plane` | T660-1 trigger pin arrival |
| `measurement_method` | two-channel edge capture |
| `required_equipment` | T660-2 Pico final cables |
| `wiring_setup` | destination ends to Pico A/B |
| `programmed_values` | 0;100ns;1us;10us;100us;1ms |
| `repetitions` | 100 accepted per point |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS01 |
| `type_a_uncertainty` | shot jitter |
| `type_b_uncertainty` | timebase threshold reconnection |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with manufacturer-spec basis |
| `traceability_source` | direct T660 results plus Pico serial/specification |
| `dependencies` | S0 MS01 MS04 |
| `closure_test` | fit residual |
| `thesis_or_handoff_destination` | electrical table |
| `current_status` | PASS COMPLETE IN T2-01 |
| `bypass_allowed` | yes |
| `effect_of_bypass` | cross-generator chain blocked |

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | T204 |
| `measured_quantity` | T660-2 pulse fidelity and channel skew |
| `physical_reference_plane` | corrected common reference |
| `target_reference_plane` | each relevant output end |
| `measurement_method` | waveform metrology |
| `required_equipment` | T660-2 Pico |
| `wiring_setup` | within T201-T203 |
| `programmed_values` | all sweep points |
| `repetitions` | 100 each |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS01 and scope response |
| `type_a_uncertainty` | repeatability |
| `type_b_uncertainty` | amplitude bandwidth termination |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with nominal-voltage limitation |
| `traceability_source` | T660/Pico sources |
| `dependencies` | T201 T202 T203 |
| `closure_test` | route consistency |
| `thesis_or_handoff_destination` | electrical table |
| `current_status` | COMPLETE VIA T2-01 ANALYSIS |
| `bypass_allowed` | yes |
| `effect_of_bypass` | quality claims limited |
