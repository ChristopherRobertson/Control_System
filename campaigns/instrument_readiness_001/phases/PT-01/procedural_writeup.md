# PT-01 — MIRcat Process Trigger electrical timing: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Retained execution campaign | `system_recalibration_001` |
| Phase ID | `PT-01` |
| Phase run ID | `system_recalibration_001_PT-01_001` |
| Domain | Calibration |
| Scientific disposition | `PASS — COMPLETE AT NONEMITTING ELECTRICAL BOUNDARY` |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Operator | Christopher Robertson |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; review remains pending. |
| Document version | `0.1.0` |
| Execution interval | Initial preflight 2026-08-13; Setup 1 and closeout 2026-08-17. Exact UTC start/end are preserved in phase logs rather than reconstructed here. |
| Draft date | 2026-08-27 |
| Governing records | `plan.md`; `run_record.md`; `final_report.md`; `phase_manifest.json` |
| Imported corrections | MS-02 PicoScope path correction; T1-01 Adapter B-minus-A correction |

## Executive synopsis

PT-01 measured the active-low electrical timing from the disconnected Nd:YAG
FIRE reference to MIRcat DB9 pin 4 at the MIRcat-disconnected cable end. Both
laser destinations were physically isolated, so the work characterized the
control route without optical emission.

Six programmed delays from 0 ns through 1 ms were measured with 100 accepted
traces each. The corrected zero-delay intercept was
`-5.48577 ± 13.4873 ns` standard uncertainty, with a slope error of
`4.36180 ppm`. The sign is target CHB minus reference CHA; the negative
intercept is small relative to its uncertainty and must not be interpreted as a
resolved causal lead. The phase closed with default wiring restored and final
safe idle passing.

## 1. Purpose — WHY

The MIRcat point/process workflow depends on a T660-1 channel-C pulse reaching
the Process Trigger input. Before control behavior could be qualified in MC-01,
the electrical route needed a stated reference plane, polarity, pulse width,
delay response, uncertainty, and restoration record. This prevented software
observations from being conflated with an unmeasured cable/adapter delay.

PT-01 was limited to the disconnected electrical route. It excluded MIRcat DB9
pin 5, pins 6/8, T660-1 channel D, optical emission, samples, CO, and biological
work. No canonical calibration promotion was authorized.

## 2. Procedure performed — HOW

### 2.1 Entry state, topology, and reference planes

The passed initial preflight from 2026-08-13 was retained rather than rerun.
Before acquisition, the complete Nd:YAG timing DB9 was disconnected from the
laser and the MIRcat cable was disconnected at the MIRcat. Adapter A observed
Nd:YAG FIRE pin 7 relative to pin 2 on PicoScope CHA. Adapter B observed the
MIRcat-disconnected cable pin 4 relative to pin 7 on CHB. Positive timing means
the Process Trigger target arrived later than FIRE.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | The retained preflight evidence was reviewed and the disconnected/nonemitting boundary was confirmed. | Enter Setup 1 without reopening an already passed preflight or exposing a laser destination. | `initial_preflight_status.json`; `run_record.md`; `setup_1_operator_confirmations.md` | Entry state accepted. |
| 2 | Adapter A was connected to the disconnected Nd:YAG timing harness FIRE/ground pins and PicoScope CHA. | Establish the FIRE reference plane. | `setup_1_operator_confirmations.md`; `reference_planes.md` | Reference connection confirmed by the operator. |
| 3 | Adapter B was connected to pin 4/7 at the MIRcat-disconnected cable end and PicoScope CHB; excluded pins/routes remained disconnected. | Establish the Process Trigger target plane without connecting the MIRcat. | `setup_1_operator_confirmations.md`; setup status/readbacks | Complete Setup 1 wiring and post-connection safe idle passed. |
| 4 | The approved T660-1 CHC active-low process pulse was exercised at 0 ns, 100 ns, 1 us, 10 us, 100 us, and 1 ms. | Characterize route intercept, slope, jitter, polarity, and width over the operating delay grid. | `setup_1_fire_to_process_trigger/`; `acquisition_index.csv` | 100 traces per delay were accepted; zero rejected. |
| 5 | Falling-edge separation was fit and corrected for the MS-02 scope path and T1-01 adapter differential. | Express timing at the defined physical reference planes. | Analysis outputs; `measurements.csv`; `uncertainty_budget.csv` | Corrected intercept, slope, residual, and sensitivities were produced. |
| 6 | The acquisition finalizer disabled outputs; adapters were removed and both device cables restored. | Return to default wiring without changing excluded routes or the splitter. | `restoration_confirmation.json`; `setup_1_operator_confirmations.md` | Operator confirmed default wiring restored. |
| 7 | Final T660 safe idle was read back. | Verify both trigger sources and all outputs were disabled. | `final_restoration_status.json`; final readbacks | Passed with zero mismatches. |

### 2.3 Analysis and uncertainty workflow

Falling-edge arrival separation was evaluated at each programmed delay, then a
weighted six-point line fit supplied the zero-delay intercept and slope. The raw
CHB-minus-CHA result was corrected by subtracting the MS-02 PicoScope CHB-minus-
CHA term and the T1-01 Adapter B-minus-A term. Combined standard uncertainty of
`13.487329 ns` includes fit uncertainty (`13.472116 ns`) and the two common
correction terms. Threshold and interpolation sensitivity are reported
separately in the uncertainty table so they are not silently double-counted.

### 2.4 Deviations and restoration

The phase records no rejected measurement trace. Raw attempts and both
provisional and corrected analyses were retained. The splitter was not moved,
and the operator confirmed that T660-1 CHD and the reserved/unused MIRcat pins
remained outside the setup. Neither laser emitted.

## 3. Results — WHAT

| Quantity | Result | Qualification |
| --- | ---: | --- |
| Corrected zero-delay route intercept | `-5.485768681 ± 13.487329161 ns` | Combined standard uncertainty |
| Slope error | `4.36180 ppm` | Six-point fit |
| Fit residual RMS | `0.440978 ns` | Six residuals |
| Maximum threshold half-range | `1.42956 ns` | Sensitivity result |
| Jitter sample standard deviation | `9.03911–29.7387 ns` | Range across six delay points |
| FIRE pulse width | approximately `9.99643 us` | Active low |
| Process Trigger pulse width | approximately `10.000020 ms` | Active low; approved nominal 10 ms recipe |

The population comprised 600 accepted traces and zero rejected traces. Required
measurement, uncertainty, retention, connection, restoration, and safe-idle
criteria passed. The scientific disposition is complete; the writeup itself
remains a draft pending review.

## 4. Implications, caveats, and claims

PT-01 supports the bounded electrical route model and active-low polarity at the
defined disconnected-harness reference planes. The slope supports programmed
delay transfer over the tested 0–1 ms grid. Because the intercept uncertainty is
larger than its magnitude, the result is consistent with a small unresolved
zero-delay offset and does not demonstrate a physically meaningful negative
latency.

The phase does not establish MIRcat internal processing latency, optical output,
other DB9 pins, alternate adapters, or an emitted pump event. Interpolation
sensitivity is large enough to remain visible in downstream uncertainty review.
MC-01 was still required to qualify one-command/one-process control behavior.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Topology and sign | `reference_planes.md`; `setup_1_operator_confirmations.md` | Preserve disconnected-device reference planes. |
| Trace population | `acquisition_index.csv`; Setup 1 raw/configuration records | Use all 600 accepted traces. |
| Numerical results | `measurements.csv`; phase analysis outputs | Machine-readable values are authoritative. |
| Corrections and uncertainty | `calibration_links.csv`; `uncertainty_budget.csv` | Apply MS-02 and T1-01 terms with recorded signs and correlation context. |
| Restoration | `restoration_confirmation.json`; final readbacks | Confirm cable restoration and safe idle. |

Minimal reproduction is to evaluate eligible falling edges, fit the six delay
points, apply both named corrections, and compare with `measurements.csv`. Native
records and criteria must remain unchanged.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Verify topology, corrections, and counts. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Review fit uncertainty and negative-intercept wording. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
