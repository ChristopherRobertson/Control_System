# MC-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | MC01 |
| `measured_quantity` | selected external process-trigger sequence |
| `physical_reference_plane` | DB9 pin-4 active-low command |
| `target_reference_plane` | MIRcat retained point/process state |
| `measurement_method` | GUI-controlled inhibited control and bounded repeats |
| `required_equipment` | MIRcat GUI T660-1 HF2LI readback |
| `wiring_setup` | normal pin-4 only |
| `programmed_values` | one CH-00-selected discrete point/process sequence; unused modes excluded |
| `repetitions` | 1 inhibited control plus 3 bounded repeats |
| `raw_data_product` | GUI records readbacks and raw DIO |
| `correction_terms` | state-based waiting/tuned confirmation |
| `type_a_uncertainty` | three-repeat one-command/one-process agreement |
| `type_b_uncertainty` | DIO21 persistence ambiguity and unsynchronized clocks |
| `combined_standard_uncertainty` | reported |
| `expanded_uncertainty` | reported with completed campaign evidence |
| `traceability_source` | MIRcat manual observed states and SDK API 2.4.1 |
| `dependencies` | S0 PT01 CH00 |
| `closure_test` | one-command/one-process state safe-stop and restoration agreement |
| `thesis_or_handoff_destination` | method table |
| `current_status` | PASS COMPLETE IN MC-01 |
| `bypass_allowed` | yes |
| `effect_of_bypass` | SDK eligible only with documented runtime prerequisites; TR-01 separately gated |
