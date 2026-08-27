# SP-02 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | SP02 |
| `measured_quantity` | spectral-axis calibration over two retained regions |
| `physical_reference_plane` | reference peak positions |
| `target_reference_plane` | readback and trigger-derived axes |
| `measurement_method` | opposite-direction reference spectra |
| `required_equipment` | MIRcat HF2LI detectors and references |
| `wiring_setup` | normal spectral setup |
| `programmed_values` | CH-00 Mylar/polystyrene carbonyl window plus 1885-1980cm-1 biological region;one sweep config |
| `repetitions` | 3 scans per direction per retained region |
| `raw_data_product` | raw MIRcat HF2LI DIO spectra |
| `correction_terms` | DET04 normalization and axis interpolation |
| `type_a_uncertainty` | scan repeatability and direction |
| `type_b_uncertainty` | feature uncertainty trigger mapping and balance correction |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | SP01 authority plus device manuals |
| `dependencies` | SP01 MSW01 HF02 DET02 DET04 |
| `closure_test` | feature residual direction closure and partition audit |
| `thesis_or_handoff_destination` | spectral table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | yes |
| `effect_of_bypass` | relative-only spectral claims |
