# DET-02 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | DET02 |
| `measured_quantity` | per-channel response linearity saturation and SNR at merged probe anchors |
| `physical_reference_plane` | independently measured incident power |
| `target_reference_plane` | detector amplifier and HF2LI outputs |
| `measurement_method` | qualified-power endpoint series and one closure control |
| `required_equipment` | detectors amplifiers HF2LI power meter and attenuation |
| `wiring_setup` | controlled channel input with hardwired interlock |
| `programmed_values` | one Mylar anchor;two HRP anchors;merged MbCO A1 upper diagnostic;one off-band;low and high power |
| `repetitions` | 3 readings per channel/anchor/endpoint plus one revisit; midpoint only after failed residual |
| `raw_data_product` | raw meter detector HF2LI and interchange records |
| `correction_terms` | dark ATT01 and meter corrections |
| `type_a_uncertainty` | repeatability and interchange |
| `type_b_uncertainty` | incident transfer wavelength placement gain range and saturation |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | OM01 ATT01 detector records |
| `dependencies` | P0-D001 DET01 HF01 OM01 ATT01 |
| `closure_test` | per-channel fit residual and common-source closure |
| `thesis_or_handoff_destination` | detector response table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | yes |
| `effect_of_bypass` | gain separation and normalization provisional |
