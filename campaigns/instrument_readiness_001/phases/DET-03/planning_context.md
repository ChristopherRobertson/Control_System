# DET-03 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | DET03 |
| `measured_quantity` | installed detector temporal response composed with HF01 HRP and MbCO filter transfers |
| `physical_reference_plane` | qualified stimulus |
| `target_reference_plane` | installed detector amplifier cable and acquisition path |
| `measurement_method` | response capture at fastest required path plus composition analysis |
| `required_equipment` | detector amplifier Pico or HF2LI and stimulus |
| `wiring_setup` | exact OP01 paths |
| `programmed_values` | each channel at fastest required config and low/high signal;one Mylar and one biological anchor;other biological config only after failed or marginal composition check |
| `repetitions` | 3 per retained condition; extra setting/wavelength only after predeclared failure |
| `raw_data_product` | raw response traces configuration and composition products |
| `correction_terms` | MS01 path stimulus and imported HF01 complex transfer |
| `type_a_uncertainty` | repeatability amplitude dependence and composition residual |
| `type_b_uncertainty` | stimulus bandwidth threshold placement wavelength reference filter attenuation and HF01 covariance |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | OM01 DET01 DET02 HF01 and detector records |
| `dependencies` | P0-D001 OM01 DET01 DET02 HF01 |
| `closure_test` | detector-only response plus configuration-specific composition closure and bounded escalation |
| `thesis_or_handoff_destination` | optical timing correction table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | no |
| `effect_of_bypass` | OP01 optical timing blocked |
