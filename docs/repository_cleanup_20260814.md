# Repository refocus record — 2026-08-14

This record documents the thesis-level repository refocus. It does not alter
or supersede campaign evidence.

## Preserved authorities and evidence

- `calibration/system_recalibration_001/` remains the calibration authority.
- `characterization/system_characterization_001/` is the characterization
  authority.
- The separately maintained theoretical Mathematica notebook remains the
  theoretical authority.
- Completed S0, MS-01, MS-02, T2-01, and T1-01 evidence was left in place.
- The in-progress PT-01 record was left in place.

## Active-tree changes

- SV-02 now uses a declared polystyrene alignment partition to fit and freeze
  the final spectral correction before any Mylar or biological data are
  opened. Mylar is an independent validation standard and cannot refit the
  correction.
- The definitive P0 decision register is
  `calibration/system_recalibration_001/manifests/p0_requirement_decisions.md`.
- Calibration now includes optical-transfer, detector/electronics response,
  detector latency, and installed non-50/50 splitter-balance phases.
- Characterization has phase gates, mandatory closeout products, aggregation
  tables, and downstream biological-entry criteria.
- Generic hardware checks write to `runs/`. Their outputs are operational
  records unless an approved phase wrapper indexes them explicitly.
- The MIRcat sweep workflow is disabled as a candidate until either MD-01 or
  MSW-01 is approved and its stable phase directory is named.
- The generic experiment-builder YAML was moved under `tests/fixtures/`; it is
  software-test input, not an experimental recipe.

## Recoverable archive

Retired publication-era, sample-specific, Day-based, and monolithic materials
were moved to:

`C:\Users\Chris\Documents\GitHub\Control_System_Archives\archive\20260814_thesis_refocus_retired_workflows`

The archive is historical reference only. No archived file is an active
procedure or scientific authority. No material was permanently deleted as
part of this cleanup.

## Deferred experimental designs

No executable polystyrene, Mylar, horseradish-peroxidase, or myoglobin-CO
recipe is active. SV-02 recipes will be written only after required promoted
calibration and characterization inputs exist. Biological campaigns will be
designed from scratch after `PROM-CH` using those promoted bundles and the
theoretical notebook.
