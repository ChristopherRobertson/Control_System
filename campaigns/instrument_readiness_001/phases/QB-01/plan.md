# QB-01 — MIRcat probe-source characterization

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `planned`  
Required dependencies: `MD-01, MSW-01, HF-02, DET-02`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### QB-01 — minimal MIRcat probe-source characterization

Characterize only the module(s) intersecting the retained Mylar/polystyrene
carbonyl window and combined 1885-1980 cm^-1 biological region. In the Mylar
window use the lower edge, selected feature, and upper edge of the accepted
continuous sweep. In the biological region use the merged HRP/MbCO band and
off-band anchors; coincident anchors are one condition. Test the single sweep
operating point and the single fixed-wavenumber/rare-pump operating point.
Measure a module transition only if a retained window crosses one. Reuse SP-02
axis calibration and MSW-01 timing; do not redetermine them or survey unused
modules/ranges.

Mandatory deliverables:

- Synchronized MIRcat readbacks, trigger/DIO records, optical-meter data, module
  identities, operating mode, pulse settings, and all calibration links.
- Power/pulse/stability versus wavenumber, module/crossover behavior, warm-up
  and repeatability tables, saturation limits, uncertainty, and recommended
  operating envelope.
- Measured-versus-manufacturer capability table and safe shutdown record.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
