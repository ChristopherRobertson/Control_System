# HF-02 — cross-stream alignment loss and endurance

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `HF-01.1, MD-01, MSW-01, MS-02.1`
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 15. HF-02 — cross-stream alignment, loss, and endurance

Verify simultaneous Sample, Reference, complete-DIO, and—where diagnostic only—
PicoScope timestamps, API/server buffering, dropped samples, and boundary behavior for
the maximum-duration envelope of every materially distinct CH-00.1-retained acquisition
architecture. Shared endurance evidence is permitted only when HF-01.1 documents full
numeric and data-path equivalence and the duration, event, topology, recorder, and
sample-count envelopes are identical; preserve the cross-reference rather than silently
omitting a test. Additional endurance records are acquired only if a retained
configuration fails.
Import the HF-01 filter/rate response bundle; HF-02 tests streaming integrity
and duration only and must not repeat AWG transfer, settling, range, or noise
mapping.

Mandatory closeout deliverables: native streams, common-event alignment table,
sample-count and gap audit, loss/reorder/duplicate statistics, host/server
clock record, resource/endurance log, configuration reload check, and a maximum
supported scan envelope with uncertainty or limitation.

## `EXPERIMENTS.md` allocation and decision contract

HF-02 covers the stream-integrity portions of `EXP-CAL-13`, `EXP-CHAR-02`,
`EXP-CHAR-13`, and `EXP-VAL-06` for all nine architecture rows in the
CH-00.1 matrix. Acceptance requires complete event/sample accounting, bounded
cross-stream skew, no unexplained loss/reorder/duplication, and restart/reload behavior
inside the frozen limit. Native streams and service/resource logs are retained.
Topology, recorder, sample rate, filter, trigger/event schema, duration, server/API,
host, firmware, or analysis changes trigger revalidation. This phase does not establish
electrical transfer, optical time zero, spectral calibration, or biological kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
