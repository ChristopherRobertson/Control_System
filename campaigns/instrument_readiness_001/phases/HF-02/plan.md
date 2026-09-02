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

For normal acquisition, use the
[default detector adapter/tee wiring](../../../../instrument/default_wiring_state.md):
sample feeds HF2LI Signal 1 In (+)/PicoScope CHA and reference feeds HF2LI
Signal 2 In (+)/PicoScope CHB. Both receivers stay connected even when only
HF2LI streams are recorded. Record temporary timing/IRF topology separately.
For Phase Scan, retain that detector topology, connect the MS-02.1-qualified T660-1
CHD route to PicoScope EXT, and keep MIRcat Sweep Active on HF2LI DIO21. Apply the
accepted MSW-01 CHD-to-Sweep-Active alignment quantity and configuration ID; do not
replace it with an assumed simultaneous edge.

Verify simultaneous Sample, Reference, complete-DIO, and—where diagnostic only—
PicoScope timestamps, API/server buffering, dropped samples, and boundary behavior for
the maximum-duration envelope of every materially distinct CH-00.1-retained acquisition
architecture. Shared endurance evidence is permitted only when HF-01.1 documents full
numeric and data-path equivalence and the duration, event, topology, recorder, and
sample-count envelopes are identical; preserve the cross-reference rather than silently
omitting a test. Additional endurance records are acquired only if a retained
configuration fails.
For the longest retained Phase-Scan records, verify that each CHD-triggered PicoScope
block brackets the complete HF2LI-observed Sweep Active interval after the accepted
offset is applied and that optical detector records, wavelength markers, timestamps,
and scan indices remain aligned across boundaries, retries, reconnects, and service
buffer rollover. Separate PicoScope block/stream loss, trigger loss, reorder, or
duplication from an optical pulse absent in both detector channels; QB-01 owns the
source-omission envelope.
Import the HF-01 filter/rate response bundle; HF-02 tests streaming integrity
and duration only and must not repeat AWG transfer, settling, range, or noise
mapping.

Mandatory closeout deliverables: native streams, common-event alignment table,
sample-count and gap audit, loss/reorder/duplicate statistics, host/server
clock record, resource/endurance log, configuration reload check, and a maximum
supported scan envelope with uncertainty or limitation. Phase-Scan products also
include a marker-aligned PicoScope/HF2LI block table, boundary-coverage audit, and
classification of recorder loss versus dual-detector optical omission.

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
