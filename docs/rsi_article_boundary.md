# RSI Article Boundary

This repository is the UI and instrument-control project. It must not become the
manuscript package. Use this boundary when adding RSI-related files.

## Keep in this UI repository

Files required to run, reproduce, or audit hardware acquisition belong here:

- workflow code and hardware service adapters under `control_app/`
- hardware recipes under `recipes/`
- timing offsets and canonical calibration CSV/YAML outputs under `calibration/`
- calibration campaign plans, manifests, readbacks, raw data, analyses, and reports under uniquely named `calibration/<campaign-id>/` directories
- operational command logs and non-calibration hardware runs under `logs/` or `runs/`
- hardware-operation notes needed by the UI, timing recipes, workflows, or reproducibility checks
- hardware-check scripts under `tests/hardware_checks/`

The UI repository may contain raw hardware outputs because run manifests and
workflow debugging depend on them. These files are not article-ready tables or
figures.

## Keep in the Article 1 RSI folder

Article-facing outputs belong under:

`C:\Users\Chris\Documents\UC Davis\SETI\Thesis\Article 1 - Review of Scientific Instruments`

Use its subdirectories for:

- manuscript drafts and edited DOCX/PDF proofs
- article-ready figures, panels, captions, and plot exports
- article-ready tables and source-data indexes
- computed manuscript values, claim tables, and placeholder-to-evidence maps
- spectral-validation metric tables, fitted values, and publication-facing uncertainty summaries
- cover letters, author checklists, reviewer lists, and journal package files

Do not write article figures, final manuscript-value tables, or draft DOCX files
inside this UI repository.

## Current RSI validation workflow

New RSI spectral validation data must be acquired from workflow-backed recipes:

- `recipes/polystyrene_validation.yaml`
- `recipes/polystyrene_fast_sweep.yaml`
- `recipes/mylar_validation.yaml`
- `recipes/myoglobin_co_validation.yaml`

Each hardware run must write a `run_manifest.json`, command log, device
readbacks, MIRcat setpoint/actual wavelength records for every scan point, HF2LI
raw CSV files, and HF2LI summary CSV files. If hardware is unavailable, the run
must write `BLOCKED.md`; do not substitute older spectra or synthetic data.

For `recipes/polystyrene_fast_sweep.yaml`, the per-point readback requirement is
replaced by a continuous-sweep metadata requirement: the run must record the
MIRcat sweep settings, HF2LI settings snapshot, T660 reference readback, raw
HF2LI output, and the LabOne/MIRcat `TRIG OUT` marker source needed to map time
to wavenumber.

Article-side analysis may read these raw outputs and manifests, but its figure
exports, computed values, source-data index, and claim tables must be written to
the Article 1 RSI folder.
