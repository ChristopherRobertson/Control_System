# MB-06 — MbCO timing IRF and discovery kinetics

Campaign: `mbco-cryo-001`  
Domain: `experiment`  
Registry status: `optional`  
Required dependencies: `MB-05`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
the campaign `../../requirements.md`.

## Phase-specific procedure and deliverables

This phase inherits the campaign-wide scientific, safety, acquisition, analysis, and data-contract requirements in `../../requirements.md`.

| **MB-06 timing/IRF and discovery kinetics** | MB-05 passes; OP/CL/IR/DET valid | Verify time zero on surrogate, acquire adaptive negative/prompt/slow/recovery schedule, assess SNR/identifiability, repeat-pulse spacing | Time-zero/IRF link; discovery traces; identifiability simulation; selected delay/rate/filter design | Abort mechanistic extension if 180 ns component unidentifiable; abort all kinetics for trigger mismatch, incomplete recovery, or sample damage. |

Keep room-temperature nanosecond, room-temperature microsecond, room-temperature
single-scan phase-delay, 77 K nanosecond/microsecond, and 77 K single-pump scan-burst
records separate. Each imports its own optical time zero, IRF, detector/HF2LI settings,
native coverage, temperature/geometry, dose/reset rule, missing-data/noise validation,
and accepted MB-04 slow scan. Probe rate is selected independently of pump cadence.
Reject an architecture that cannot meet reset, coverage, SNR, IRF, or identifiability
criteria without deleting its evidence.

The room-temperature single-scan phase-delay block imports the promoted Phase-Scan
configuration, including the T660-1 CHD-to-PicoScope-EXT electrical qualification,
CHD-to-Sweep-Active alignment quantity and ID, dual-detector optical-omission envelope,
and E2E-CH-validated coverage/retry/merge policy. Preserve every nominal and repeated
scan and its attempt/bin provenance. Stop biological acquisition for an invalid marker
alignment or unclassifiable pulse record. If the retry budget is exhausted, retain the
best-effort diagnostic reconstruction as
`INCOMPLETE_MISSING_PULSE_COVERAGE`, with deficient regions visibly absent and every
derived table and plot marked not for publication; do not use that delay/run for a
biological conclusion.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
