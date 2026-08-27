# SV-02A planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: characterization measurement matrix

| Field | Preserved value |
| --- | --- |
| `phase_id` | SV-02A |
| `purpose` | Polystyrene calibration holdout and correction freeze |
| `dependencies` | PF-00 SP-02 SV-01 AR-01 DET-04 |
| `emission_allowed` | no |
| `minimum_repetitions` | prospectively declared partition counts |
| `mandatory_raw_products` | polystyrene calibration and holdout raw streams and frozen analysis |
| `mandatory_results` | correction coefficients covariance validity and Mylar unlock |
| `closeout_gate` | holdout passes without refit and all freeze fields complete |
| `current_status` | PLANNED NOT EXECUTED |

## Source: characterization measurement matrix

| Field | Preserved value |
| --- | --- |
| `phase_id` | SV-02 |
| `purpose` | Freeze polystyrene alignment then validate independently with Mylar |
| `dependencies` | SV-01 system_recalibration_001:SP-02 system_recalibration_001:DET-04 QB-01 OG-01 AR-01 |
| `emission_allowed` | probe only under separate approval |
| `minimum_repetitions` | predeclared polystyrene alignment and holdout sets plus 3 accepted Mylar scans per direction |
| `mandatory_raw_products` | native Sample Reference DIO spectra readbacks feature table partition and unlock records |
| `mandatory_results` | frozen correction covariance holdout metrics Mylar position shape FWHM hysteresis normalization audit and uncertainty |
| `closeout_gate` | correction frozen before Mylar access and no-refit proof accepted |
| `current_status` | PLANNED |
