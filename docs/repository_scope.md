# Repository scope

This repository supports thesis-level calibration, characterization, and
experimental control for the pump-probe platform.

## Canonical scientific authorities

1. `calibration/system_recalibration_001/` defines calibration measurements,
   corrections, uncertainty, promotion, and preserved evidence.
2. `characterization/system_characterization_001/` defines pump, probe,
   geometry, spectral, temporal, sensitivity, and reproducibility performance.
3. The separately maintained theoretical Mathematica notebook defines the
   scientific forward models and required experimental inputs.

Publication drafts, journal submission packages, and paper-specific validation
plans are outside this repository and are not authorities for hardware work.
They may be created later from promoted data and completed procedures.

The implemented refocus and recoverable archive are itemized in
`docs/repository_cleanup_20260814.md`.

## Experimental boundary

- Polystyrene and Mylar are nonbiological characterization materials. SV-02
  uses polystyrene to define and freeze the wavenumber correction, then uses
  Mylar as the independent validation standard.
- Horseradish-peroxidase and myoglobin-CO requirements-level designs define
  the claims and operating conditions used to trim calibration and
  characterization. Their numeric settings and executable recipes belong to
  downstream campaigns finalized from promoted bundles.
- No biological sample may define or refit calibration or characterization
  corrections.

## Active workflow rule

An active evidence-producing recipe or procedure must identify its campaign,
phase, required bundle/configuration IDs, approval state, output directory,
mandatory controls, retention tables, and restoration gate. Generic device
utilities may remain under `control_app/`, but a run produced by a generic UI
or development utility is not campaign evidence unless an approved phase
wrapper explicitly imports it.

Legacy sample-specific recipes, Day-based workflows, and journal-oriented
validation files were removed from the active tree on 2026-08-14. They are
preserved outside this repository under
`Control_System_Archives/archive/20260814_thesis_refocus_retired_workflows` and must
not be executed or copied into a new campaign as an authority.
