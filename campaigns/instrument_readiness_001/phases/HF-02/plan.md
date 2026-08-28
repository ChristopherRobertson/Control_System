# HF-02 — cross-stream alignment loss and endurance

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `HF-01, MD-01, MSW-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 15. HF-02 — cross-stream alignment, loss, and endurance

Verify simultaneous Sample, Reference, and complete-DIO timestamps, API/server
buffering, dropped samples, and boundary behavior over exactly three maximum-
duration records: one complete retained continuous sweep, one longest planned
HRP-C-CO recovery stream, and one longest planned MbCO acquisition stream.
Additional endurance records are acquired only if a retained configuration
fails. A biological record may serve both configurations only when HF-01 has
documented numeric equivalence and the maximum-duration envelopes are also
identical; preserve the cross-reference rather than silently omitting a test.
Import the HF-01 filter/rate response bundle; HF-02 tests streaming integrity
and duration only and must not repeat AWG transfer, settling, range, or noise
mapping.

Mandatory closeout deliverables: native streams, common-event alignment table,
sample-count and gap audit, loss/reorder/duplicate statistics, host/server
clock record, resource/endurance log, configuration reload check, and a maximum
supported scan envelope with uncertainty or limitation.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
