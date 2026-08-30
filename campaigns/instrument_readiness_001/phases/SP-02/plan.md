# SP-02 — spectral-axis calibration

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `SP-01, AR-01, DET-04`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 21. SP-02 — spectral-axis calibration

Measure internal-readback accuracy, trigger-derived axis, per-channel behavior,
direction hysteresis, crossovers, effective sampling/interpolation, reference
agreement, and scan-to-scan repeatability using qualified prior phases. Import
the DET-04 balance/normalization bundle; do not estimate or assume a 50/50
split from the spectral data.

The grid contains only two disjoint validated regions: the CH-00.1 Mylar/
polystyrene carbonyl window and the combined 1885-1980 cm^-1 HRP/MbCO window.
Use accepted slow-scan, repeated rapid-scan, discrete-tune, and scan-burst
configurations wherever they produce an axis, with three scans or transition sequences
per direction/history per retained region. Keep room-temperature and 77 K optical
configurations separate even when the source command is numerically identical. Add a module-crossover condition only when a retained
region crosses one. Do not run a broad 1650-2050 cm^-1 candidate.

Mandatory closeout deliverables: native spectra/readbacks/DIO streams, exactly
three planned scans per direction and relevant channel, frozen calibration fit,
residual and hysteresis tables, interpolation method, uncertainty budget,
independent validation partition, DET-04 correction ID, raw and normalized
Sample/Reference products, and validity range. Calibration data and validation
data must remain separately identifiable. Another scan is allowed only after a
predeclared acceptance criterion fails.

## `EXPERIMENTS.md` allocation and decision contract

SP-02 implements `EXP-CAL-05`, `EXP-CAL-06`, `EXP-CHAR-04`, and
`EXP-OPT-06`. Acceptance requires independent validation residuals,
direction/history and mode-specific uncertainty, native coverage, and a bounded
interpolation rule. Module/source service, reference material, optical path, mode,
window, direction/speed, event mapping, detector normalization, temperature geometry,
or analysis change triggers revalidation. It supplies the axis prerequisite for all
four mandatory slow scans and all five reconstruction methods but does not establish
condition-specific biological peak centers, widths, areas, or kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
