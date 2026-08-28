# SV-01 — independent FTIR reference acquisition

Campaign: `instrument-readiness-001`  
Domain: `validation`  
Registry status: `planned`  
Required dependencies: `SP-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### SV-01 — independent FTIR reference-data acquisition

Acquire or register one specimen-matched high-resolution FTIR reference set for
polystyrene and one for Mylar. No other standard and no biological spectrum is
part of this phase. Match the retained polarization/orientation basis and
acquire only the resolution/coadds required by the frozen position/shape
uncertainty allocation. Do not refit the QCL axis here.

Mandatory deliverables:

- FTIR instrument/configuration identity, sampling geometry, resolution,
  apodization, scans, background, sample presentation, observational
  temperature, available path/thickness information, preprocessing, and
  source-data provenance. Missing film thickness does not block peak-position
  alignment or independent validation.
- Immutable native FTIR exports plus normalized CSV in the notebook-required
  layout, artifact IDs/paths/sizes/timestamps, feature/uncertainty authority,
  and preprocessing source/version.
- Separation of calibration, independent validation, and illustrative-only
  records.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
