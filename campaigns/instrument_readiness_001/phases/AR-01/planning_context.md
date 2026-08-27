# AR-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: characterization measurement matrix

| Field | Preserved value |
| --- | --- |
| `phase_id` | AR-01 |
| `purpose` | Optically validate sweep HRP fixed-point and MbCO fixed-point configurations without repeating HF01 electrical mapping |
| `dependencies` | system_recalibration_001:HF-01 system_recalibration_001:HF-02 system_recalibration_001:DET-01 system_recalibration_001:DET-02 system_recalibration_001:DET-03 system_recalibration_001:DET-04 QB-01 SC-01 |
| `emission_allowed` | no until separately approved |
| `minimum_repetitions` | selected sweep plus one slower reference in both directions;selected HRP and MbCO point transitions with one bracket only after prediction failure or guard-band result |
| `mandatory_raw_products` | native Sample Reference DIO step and scan records with imported HF01 transfer links |
| `mandatory_results` | imported-versus-observed settling filter-memory peak-shift broadening covariance residual and uncertainty |
| `closeout_gate` | three experiment-specific configuration IDs optically validated with every bracket escalation rule recorded |
| `current_status` | PLANNED |
