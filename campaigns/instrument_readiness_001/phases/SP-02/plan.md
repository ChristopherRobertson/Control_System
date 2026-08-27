# SP-02 — spectral-axis calibration

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `SP-01, AR-01, DET-04`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 21. SP-02 — spectral-axis calibration

Measure internal-readback accuracy, trigger-derived axis, per-channel behavior,
direction hysteresis, crossovers, effective sampling/interpolation, reference
agreement, and scan-to-scan repeatability using qualified prior phases. Import
the DET-04 balance/normalization bundle; do not estimate or assume a 50/50
split from the spectral data.

The grid contains only two disjoint validated regions: the CH-00 Mylar/
polystyrene carbonyl window and the combined 1885-1980 cm^-1 HRP/MbCO window.
Use one accepted continuous-sweep configuration and three scans per direction
per retained region. Add a module-crossover condition only when a retained
region crosses one. Do not run the former broad 1650-2050 cm^-1 candidate.

Mandatory closeout deliverables: native spectra/readbacks/DIO streams, exactly
three planned scans per direction and relevant channel, frozen calibration fit,
residual and hysteresis tables, interpolation method, uncertainty budget,
independent validation partition, DET-04 correction ID, raw and normalized
Sample/Reference products, and validity range. Calibration data and validation
data must remain separately identifiable. Another scan is allowed only after a
predeclared acceptance criterion fails.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
