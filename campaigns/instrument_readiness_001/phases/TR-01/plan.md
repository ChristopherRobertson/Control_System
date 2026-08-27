# TR-01 — retained identity and measurement-resource closure

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `historical_complete`  
Required dependencies: `P0`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../shared/phase_execution_requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### 8. TR-01 — retained identity and measurement-resource closure — COMPLETE / PASS

Close only requirements retained or narrowed in
`manifests/p0_requirement_decisions.md` plus metrology resources actually
selected for later phases. Do not repeat completed measurements and do not
retrieve certificate or accessory metadata that the decision register
discarded. Devices whose installed performance is measured directly require
identity, configuration, evidence, uncertainty, and validity limits—not a
formal certificate. Only instruments serving as measurement references need
an applicable uncertainty basis, which may be a manufacturer specification,
available calibration record, or qualified comparison.

Mandatory closeout deliverables:

- A concise measurement-resource register listing stable equipment ID, role
  (`DEVICE_UNDER_TEST` or `WORKING_REFERENCE`), configuration/range used,
  uncertainty basis where applicable, validity conditions, and source record.
- Final P0 decision-register export showing every item as retained, narrowed,
  or discarded with its downstream claim consequence.
- PicoScope serial `10261`, actual timebases/ranges used, and applicable
  manufacturer accuracy; voltage accuracy is required only for a reported
  quantitative voltage, not a threshold diagnostic.
- MIRcat and LabOne/HF2LI software versions for accepted configurations, the
  existing schema/analysis-version convention, the retained detector identity
  requirement, applicable wiring authority, and the metrology resources
  actually selected after experimental requirements are defined.

All P0 decision rows are resolved. TR-01 may proceed in parallel with
nondependent analysis and cannot add discarded work back into the campaign.
PROM-01 must describe the actual uncertainty basis without claiming accredited
traceability that the campaign does not establish. The replacement
reference-detector SIP model/serial and detector model/serial must be recorded
after arrival and before reference-detector-dependent DET phases begin.

TR-01 closed by records audit in `evidence/calibration/system_recalibration_001/phases/TR-01/`. It imported completed
campaign evidence by stable identifier, retained the applicable PicoScope
manufacturer-specification basis, classified spectral authority as deferred to
SP-01 and optical resource qualification as deferred to OM-01, and made no
hardware or canonical-calibration change. It designated OM-01 as its successor;
OM-01 is now complete and retained without reacquisition.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
