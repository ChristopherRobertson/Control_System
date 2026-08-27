# HF-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | HF01 |
| `measured_quantity` | three-anchor HF2LI response-model validation and three experiment-specific configurations across two topologies |
| `physical_reference_plane` | monitored PicoScope-AWG voltage and measured T660 reference/marker copies related to the HF2LI input planes |
| `target_reference_plane` | HF2LI readbacks and data |
| `measurement_method` | three separated carrier-step/offset-carrier anchors plus computational evaluation selected-setting range rate channel-exchange and reload confirmation |
| `required_equipment` | HF2LI T660-2 PicoScope 5244D AWG CLOCK-SPLITTER-01 retained for 10 MHz distribution plus HF01-STIMULUS-TEE-01 and BNC assembly |
| `wiring_setup` | CLOCK-SPLITTER-01 unchanged from T660-2 CLOCK to T660-1 and HF2LI CLOCK;separate passive tee on AWG stimulus;T660 A direct to HF2LI DIO0 with B copy to Pico B;C direct to HF2LI DIO1 with D copy to Pico EXT;B disconnected from MIRcat and D from T660-1 |
| `programmed_values` | exactly three model anchors leading to computationally selected sweep HRP-C-CO and MbCO configuration IDs |
| `repetitions` | 3 independent windows/transitions per measured condition;selected settings confirmed;maximum 1 challenger per case only after ambiguity;fourth anchor only after model failure |
| `raw_data_product` | linked native PicoScope stimulus/reference-copy and HF2LI streams settings readbacks clock-lock and copy-offset checks model evaluation ledger and configurations |
| `correction_terms` | reference/filter complex transfer settling ENBW temporal bias total-error rate decimation tee/copy loading and selected-setting channel-equivalence model |
| `type_a_uncertainty` | window transition destination-exchange copy-offset clock-lock and revisit repeatability |
| `type_b_uncertainty` | AWG/Pico timebase voltage tee/cable loading T660 copy offset external-clock status HF2 setting quantization filter residual range clipping throughput and retained-claim terms |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | HF2LI manual PicoScope 5000D datasheet T660 records and monitored direct records |
| `dependencies` | T201 MS01 MS02 CH00 |
| `closure_test` | three-anchor model closure external-clock lock measured timing-copy relation unique or challenger-resolved selection selected-setting channel equivalence reload and default-wiring restoration agreement |
| `thesis_or_handoff_destination` | acquisition table |
| `current_status` | NOT STARTED |
| `bypass_allowed` | yes |
| `effect_of_bypass` | acquisition claims limited |
