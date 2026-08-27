# PT-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | PT01 |
| `measured_quantity` | reference to Process Trigger |
| `physical_reference_plane` | FIRE or approved common reference |
| `target_reference_plane` | MIRcat DB9 pin-4 arrival |
| `measurement_method` | two-channel falling-edge capture and polarity |
| `required_equipment` | T660s Pico approved breakout |
| `wiring_setup` | pin 4 only; reserved pin 5 disconnected; pins 6 and 8 unused and unwired |
| `programmed_values` | six-point sweep where valid |
| `repetitions` | 100 accepted per point |
| `raw_data_product` | raw Pico traces |
| `correction_terms` | MS02 Pico path plus T1-01 adapter differential |
| `type_a_uncertainty` | shot jitter |
| `type_b_uncertainty` | timebase threshold load |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with completed campaign evidence |
| `traceability_source` | T660/MIRcat/Pico sources |
| `dependencies` | S0 MS02 T1-01 |
| `closure_test` | derived cross-generator timing |
| `thesis_or_handoff_destination` | electrical table |
| `current_status` | PASS COMPLETE IN PT-01 |
| `bypass_allowed` | no |
| `effect_of_bypass` | MC-01 process behavior remains separately gated |
