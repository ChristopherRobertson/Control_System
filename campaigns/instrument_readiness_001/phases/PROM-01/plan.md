# PROM-01 — calibration promotion gate

Campaign: `instrument-readiness-001`  
Domain: `promotion`  
Registry status: `planned`  
Required dependencies: `RPT-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 27. PROM-01 — promotion gate

Present results, uncertainties, bypasses, unresolved terms, closure/E2E results,
retention audit, proposed canonical diff, and characterization prerequisites.
Make no canonical change without the exact approval phrase
`APPROVE CALIBRATION PROMOTION`.

Mandatory closeout deliverables: reviewed promotion candidate, exact diff,
approved calibration bundle ID and validity date if promoted, rollback/archive
plan, and updated downstream dependency record. After promotion and retention
review, the campaign directory can be archived as one independent unit.

The promotion candidate must include the electronic-iris control/optical-
transfer bundle and the qualified WM-01 replacement working-reference bundle. It must
not promote the original OM-01 mixed-spectrum indication as post-iris 540 nm
sample-plane power or a wavelength-spectrometer center value as a spectral-power
fraction.

Promotion is prohibited while a required CH-00.1 row lacks accepted, reviewer-linked
evidence or is marked unresolved/unsupported for the proposed validity envelope. The
gate must explicitly review MS-02.1 dual-recorder corrections, normal-versus-timing
topologies, configuration-specific timing/IRFs, and the four mandatory slow-scan
prerequisites. Creating a registry row, report, bundle directory, or manifest is not
promotion.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
