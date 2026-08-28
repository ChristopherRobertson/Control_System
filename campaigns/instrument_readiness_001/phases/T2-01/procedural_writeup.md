# T2-01 — direct T660-2 routes: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Phase ID | `T2-01` |
| Phase run ID(s) | No stable phase-run ID is present in the retained T2-01 overview. |
| Domain | Calibration |
| Scientific disposition | `PASS — COMPLETE` |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Operator | Christopher Robertson |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; review remains pending. |
| Document version | `0.1.0` |
| Execution closeout | Final restoration and safe-idle pass recorded 2026-08-08; exact start UTC was not reconstructed. |
| Draft date | 2026-08-27 |
| Governing records | `plan.md`; `run_record.md`; `final_report.md`; `t2_01_results.json` |
| Imported correction | MS-02 CHB-minus-CHA `0.109947073 ± 0.581707394 ns` |

## Executive synopsis

T2-01 measured the installed electrical timing from the T660-2 EXT REF route to
three destinations: the HF2LI DAQ input, MIRcat trigger input, and T660-1 trigger
input. Each route was exercised at six programmed delays from 0 ns through 1 ms,
with 100 accepted traces per delay.

All 1,800 retained measurement traces were accepted and none rejected. Corrected
zero-delay fitted intercepts were `0.948750 ns` for HF2LI DAQ, `11.350148 ns`
for MIRcat TRIG IN, and `0.133764 ns` for T660-1 TRIG IN, with combined standard
uncertainties near 0.694–0.695 ns. The Setup 3 capture planner required a
corrected replacement because its 10 us target pulse initially approached the
window boundary; the replacement, not the superseded record, is the reported
authority.

## 1. Purpose — WHY

The control system programs T660-2 delays, but downstream devices receive pulses
after propagation through installed outputs, bulkheads, cables, and inputs. T2-01
was required to distinguish programmed delay from physical arrival time and to
provide route-specific intercept, slope, jitter, fidelity, and uncertainty terms
for later timing closure.

The phase imported the MS-02 measurement-path correction rather than repeating
oscilloscope calibration. It remained electrical and nonemitting and did not
promote a canonical bundle or authorize T1-01.

## 2. Procedure performed — HOW

### 2.1 Entry state and measurement definition

Exclusive PicoScope ownership was verified and both T660s matched the safe-idle
recipe. For every route, PicoScope CHA observed the final HF2LI EXT REF cable-end
event and CHB observed the destination-route event. Positive corrected timing
means the destination arrived after the EXT REF reference. Physical separation
was computed as raw CHB-minus-CHA minus the MS-02 correction.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | PicoScope ownership and T660 safe idle were checked. | Establish an inhibited, exclusive entry state. | `preflight_status.json`; initial safe-idle records | Preflight passed. |
| 2 | The EXT REF reference and HF2LI DAQ destination route were connected to the two PicoScope channels. | Measure the installed EXT REF-to-DAQ timing relation. | `setup_1_extref_to_daq/`; setup records | Six delay points were acquired with 100 accepted traces each. |
| 3 | The destination measurement was moved to MIRcat TRIG IN while preserving the reference definition. | Characterize the installed MIRcat trigger route. | `setup_2_extref_to_mircat/`; setup records | Six delay points were acquired with 100 accepted traces each. |
| 4 | The destination measurement was moved to T660-1 TRIG IN. | Characterize the master-to-secondary timing route. | `setup_3_extref_to_t6601/`; setup records | The first record exposed a capture-window boundary problem for the 10 us pulse. |
| 5 | The shared planner was corrected to reserve programmed delay, target pulse width, and post-edge margin; Setup 3 was reacquired at the same six points. | Require both edges, post-edge samples, and no overflow before acceptance. | Corrected Setup 3 directory; `run_record.md`; `final_report.md` | Replacement contained 600 accepted complete-pulse traces, zero rejections, and no unavailable widths. |
| 6 | Edge timing, weighted line fits, threshold/interpolation sensitivity, jitter, amplitude, width, and polarity were evaluated. | Produce route intercepts, scale slopes, and validity diagnostics. | Per-route `analysis.json`; `t2_01_results.json` | All three route result sets passed. |
| 7 | Default installed routes and normal clock distribution were restored and safe idle was read back. | Return the instrument to the pre-phase configuration. | `restoration_confirmation.json`; final safe-idle records | Both trigger sources and all eight outputs were off. |

### 2.3 Acquisition and analysis design

The programmed grid was 0 ns, 100 ns, 1 us, 10 us, 100 us, and 1 ms. A line
`t = b + m d` was fit per route, where `d` is programmed delay and `b` is the
corrected installed-route intercept. Combined intercept uncertainty included fit
uncertainty, the common MS-02 correction, and threshold half-range as documented
by the retained analysis. Linear interpolation was the reporting estimator;
nearest-sample differences were retained as sensitivity evidence.

### 2.4 Deviations and supersession

The initial Setup 3 capture policy did not provide sufficient post-falling-edge
margin for the authoritative 10 us T660-1 trigger-input pulse. That record was
not silently used. A complete same-grid replacement was acquired after the
planner correction. It agreed with the earlier timing within an intercept change
of `0.00484 ns` and slope change of `0.249 ppm`. The superseded files were moved
under operator authorization to the recorded archive location; the replacement
is the sole in-repository Setup 3 authority.

## 3. Results — WHAT

| Installed route | Corrected intercept (ns) | Standard uncertainty (ns) | Slope deviation (ppm) | Residual RMS (ns) |
| --- | ---: | ---: | ---: | ---: |
| EXT REF to HF2LI DAQ | 0.948750 | 0.694521 | 6.752 | 0.046545 |
| EXT REF to MIRcat TRIG IN | 11.350148 | 0.695142 | 6.542 | 0.056715 |
| EXT REF to T660-1 TRIG IN | 0.133764 | 0.694360 | 6.753 | 0.025435 |

All measured polarities were positive. EXT REF and the first two destination
pulses were approximately 5 V and 150 ns wide; the T660-1 trigger-input test used
the authoritative 10 us target width. Jitter sample standard deviations ranged
from `0.077 ns` to `2.527 ns` across the retained route/delay sets. The final
accepted population was 1,800 traces, with zero rejected measurement traces.

## 4. Implications, caveats, and claims

T2-01 supports the reported linear route corrections for the installed routes,
six-point delay interval, electrical configurations, reference plane, and common
MS-02 measurement correction. The near-unity fitted slopes support use of the
programmed T660-2 delay over the tested 0–1 ms interval with the retained ppm
deviations and uncertainty.

The phase does not establish optical emission timing, other cable geometries,
certificate-level voltage accuracy, or behavior outside the tested route and
delay envelope. PicoScope certificate information remained unresolved. The
MS-02 term is a common correlated contribution and must not be treated as an
independent new calibration for every route.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Accepted route populations | Setup directories and acquisition indexes | Use 100 accepted traces for each route/delay. |
| Corrections, fits, sensitivities | Per-route `analysis.json`; `t2_01_results.json` | Subtract the MS-02 CHB-minus-CHA value using the recorded sign. |
| Setup 3 replacement | `run_record.md`; `final_report.md` | Exclude the archived superseded record from the reported population. |
| Restoration | `restoration_confirmation.json`; final readbacks | Confirm the four routes and clock distribution were restored. |

Minimal reproduction is to load each accepted trace population, apply the
retained edge estimator and MS-02 correction, fit the six programmed delays, and
compare full-precision outputs to `t2_01_results.json`.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Verify the accepted/superseded Setup 3 boundary. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Review fit and correlated-uncertainty interpretation. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
