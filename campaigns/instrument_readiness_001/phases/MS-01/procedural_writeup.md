# MS-01 — PicoScope differential channel and path skew: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Phase ID | `MS-01` |
| Phase run ID(s) | No stable phase-run ID is present in the retained MS-01 records. |
| Domain | Calibration |
| Scientific disposition | `PASS — COMPLETE` |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Operator | Christopher Robertson |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; review remains pending. |
| Document version | `0.1.0` |
| Execution interval | Exact UTC start/end were not reconstructed from the retained overview. |
| Draft date | 2026-08-27 |
| Governing records | `plan.md`; `run_record.md`; `final_report.md`; `ms01_results.json` |

## Executive synopsis

MS-01 quantified the timing offset introduced by the PicoScope channel pair and
the fixed measurement leads, while also estimating the branch difference of
`CLOCK-SPLITTER-01`. The same pulse source and splitter were measured in normal
and channel-swapped orientations so that channel/path and splitter contributions
could be separated algebraically.

One hundred traces were accepted in each orientation and none were rejected. The
phase estimated PicoScope channel/path skew, CHB minus CHA, as
`0.119976522 ns ± 0.577372813 ns` standard uncertainty and splitter skew, S2
minus S1, as `0.009274007 ns ± 0.577372813 ns`. The result is bounded by the
2 ns sampling contribution and lacks certificate and multi-reconnection terms.

## 1. Purpose — WHY

Later route delays are observed as a difference between two PicoScope channels.
Without a channel/path correction, that observation conflates physical device
delay with the oscilloscope and lead asymmetry. MS-01 therefore established the
first working correction and its sign convention before the installed T660
routes were characterized.

The acceptance objective was to obtain complete normal and swapped trace sets,
derive separate channel/path and splitter terms, retain uncertainty and
repeatability evidence, restore normal clock distribution, and finish in safe
idle. The phase did not calibrate the PicoScope against an accredited standard
or authorize MS-02 automatically.

## 2. Procedure performed — HOW

### 2.1 Entry state, equipment, and configuration

Exclusive PicoScope ownership was established for PicoScope 5244D serial
`10261`; T660-1 serial `00369` and T660-2 serial `00431` were controlled
directly. Initial safe idle matched the repository recipe, and both lasers and
the room interlock were operator-confirmed inhibited/ready. No MIRcat Process
Trigger command was used.

The PicoScope was configured for 8-bit, DC-coupled CHA/CHB acquisition at the
10 V range and zero offset. The rising-edge trigger was on CHA at 5000 ADC,
without auto-trigger. Timebase 1 gave a 2 ns sample interval, with 100000
samples and 1000 pre-trigger samples per capture.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | Ownership and safe-idle preflight were checked. | Prevent acquisition with an unknown controller or enabled output. | `preflight_status.json`; `safe_idle_initial_readback.json`; `preflight_command_log.txt` | PicoScope ownership and T660 safe idle passed. |
| 2 | The installed clock connections were parked while the fixed T660-2 CHA 12-inch SMB-to-BNC bulkhead remained installed. | Preserve the fixed path and temporarily make `CLOCK-SPLITTER-01` the measurement splitter. | `run_record.md`; `final_report.md` | Splitter input was connected to the CHA bulkhead; the third branch remained open. |
| 3 | In the normal orientation, S1 was connected directly to PicoScope CHA and S2 directly to CHB. | Observe the combined channel/path and splitter contributions. | Normal configuration and raw records; `final_report.md` | 100 traces were accepted; none were rejected. |
| 4 | Only S1 and S2 were exchanged at the PicoScope; splitter input and open third branch were unchanged. | Reverse the splitter contribution while preserving the channel/path sign. | Swapped configuration and raw records; `final_report.md` | 100 traces were accepted; none were rejected. |
| 5 | Edge times were estimated and the normal/swapped means were combined by swap algebra. | Separate CHB-minus-CHA channel/path skew from S2-minus-S1 branch skew. | `analyze_ms01.py`; `ms01_results.json` | Both correction estimates and repeatability statistics were produced. |
| 6 | EXT REF and normal clock distribution were restored, followed by final safe-idle readback. | Return the system to its installed starting topology. | `restoration_confirmation.json`; final safe-idle records; `final_report.md` | Restoration was operator-confirmed and final readback matched with no mismatches. |

### 2.3 Analysis and uncertainty workflow

For each accepted trace the reported timing estimator located the pulse edge on
both channels and formed `B - A`; positive values mean CHB arrived later. The
normal and swapped means were `0.129250529 ns` and `0.110702516 ns`. Their
midpoint estimates the channel/path term, while half their difference estimates
S2 minus S1. The uncertainty combined orientation standard errors with the
2 ns sample-resolution standard-uncertainty term. Normal and swapped sample
standard deviations were `0.076662454 ns` and `0.067346895 ns`.

### 2.4 Deviations and restoration

Cable-reconnection repeatability was not separately measured in MS-01. During
restoration, two final readback attempts failed because the T660-2 RS-232 cable
was physically unplugged; no output-enable command was sent. After reconnection,
the final safe-idle readback passed. The failed readback attempts are retained as
part of the restoration history and do not alter the accepted trace population.

## 3. Results — WHAT

| Quantity | Result | Population and qualification |
| --- | ---: | --- |
| Normal mean CHB minus CHA | `0.129250529 ns` | 100 accepted traces |
| Swapped mean CHB minus CHA | `0.110702516 ns` | 100 accepted traces |
| PicoScope channel/path skew, CHB minus CHA | `0.119976522 ± 0.577372813 ns` | Standard uncertainty |
| Splitter branch skew, S2 minus S1 | `0.009274007 ± 0.577372813 ns` | Standard uncertainty |
| Pooled within-orientation repeatability | `0.072155167 ns` | Sample standard deviation |

All 200 required traces were accepted and zero were rejected. The completion
criteria for acquisition, analysis, restoration, and safe state passed. The
recorded scientific disposition is PASS/complete; this reconstructed writeup
remains review pending.

## 4. Implications, caveats, and claims

MS-01 supports use of the reported signs and working corrections for the exact
PicoScope configuration and fixed-lead geometry recorded by the phase. It shows
that the observed orientation means are repeatable within the retained run.

It does not support certificate-level timing or voltage traceability, a
manufacturer specification for the unmarked splitter, or a general correction
for other channel ranges, timebases, leads, reconnections, or oscilloscopes.
PicoScope certificate uncertainty, splitter specifications, and independent
reconnection variability remained unresolved. MS-02 was therefore required to
add a second complete connection realization and sensitivity analysis.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Ownership, wiring, settings, counts | `final_report.md`; `run_record.md` | Reconstruct the two orientations without changing retained evidence. |
| Machine-readable result | `ms01_results.json` | Use full-precision values as numerical authority. |
| Raw population | `normal/`; `swapped/` | Apply only the recorded eligibility and edge-analysis rules. |
| Restoration and safe state | `restoration_confirmation.json`; final readback records | Include the preserved RS-232 interruption in the audit trail. |

Minimal reproduction is to run the retained MS-01 analysis against the indexed
normal and swapped traces, verify accepted counts, and compare the generated
quantities with `ms01_results.json`. Hash equality is not an acceptance gate.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Verify configuration and raw-population references. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Review swap algebra and uncertainty wording. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
