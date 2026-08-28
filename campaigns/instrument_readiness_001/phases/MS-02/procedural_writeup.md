# MS-02 — splitter branch skew and measurement-system sensitivities: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Phase ID | `MS-02` |
| Phase run ID(s) | No stable phase-run ID is present in the retained MS-02 records. |
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
| Governing records | `plan.md`; `run_record.md`; `final_report.md`; `ms02_results.json` |

## Executive synopsis

MS-02 strengthened the MS-01 measurement-system correction by adding a second
complete normal/swapped connection realization and quantifying threshold,
interpolation, timebase, pulse-fidelity, and reconnection effects. It reused the
200 accepted MS-01 traces and acquired 200 new traces rather than discarding or
repeating the first realization.

The midpoint of the two realizations gave a PicoScope channel/path skew of
`0.109947073 ± 0.581707394 ns` and a splitter S2-minus-S1 skew of
`0.013383015 ± 0.577390856 ns`, both reported as combined standard uncertainty.
The principal limitation is that reconnection evidence comprises only two
complete realizations, so half their range is a bounded uncertainty contribution,
not a measured multi-cycle reconnection distribution.

## 1. Purpose — WHY

MS-01 established the swap algebra, but a single physical connection realization
could not separate stable timing asymmetry from reconnection sensitivity. Later
installed-route calibration also needed evidence that the correction was not
strongly dependent on the edge threshold or interpolation method and that the
source pulses were sufficiently faithful for timing analysis.

MS-02 therefore asked whether a second full realization reproduced the correction
within a defensible uncertainty budget. It did not calibrate the PicoScope against
an accredited reference or establish splitter bandwidth/insertion loss.

## 2. Procedure performed — HOW

### 2.1 Inputs and configuration

The 100 normal and 100 swapped MS-01 traces were retained as realization 1. A
second realization repeated the same controlled normal and swapped geometry,
PicoScope configuration, sign convention, and trace-eligibility rules. Normal
clock wiring was restored after acquisition and final T660 safe idle was checked.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | The accepted MS-01 normal/swapped population was imported without modification. | Preserve the first complete realization and avoid unnecessary reacquisition. | `../MS-01/ms01_results.json`; `run_record.md` | 200 inherited accepted traces entered the comparison. |
| 2 | The splitter and PicoScope were connected in the normal orientation using the MS-01 geometry. | Obtain the second realization of the combined path and splitter timing. | `reconnection_normal/`; configuration/readback records | 100 traces accepted, zero rejected. |
| 3 | Only the splitter branches at the PicoScope were swapped. | Reverse the splitter term while retaining the channel/path sign. | `reconnection_swapped/`; configuration/readback records | 100 traces accepted, zero rejected. |
| 4 | Swap algebra was applied separately to both realizations. | Derive channel/path and splitter estimates before combining them. | `offline_analysis.json`; `ms02_results.json` | Reconnection differences were calculated for both quantities. |
| 5 | The two-realization midpoint and half-range contribution were calculated. | Produce a working correction while exposing the limited reconnection sample. | `ms02_results.json` | Final combined estimates and standard uncertainties were produced. |
| 6 | Edge thresholds from 3000 to 7000 ADC and linear-versus-nearest interpolation were evaluated; pulse width and rise time were summarized. | Bound estimator sensitivity and verify pulse fidelity. | Analysis outputs; `final_report.md` | Sensitivity values and pulse statistics were retained. |
| 7 | EXT REF and normal `CLOCK-SPLITTER-01` distribution were restored and safe idle was verified. | Return to the installed reference topology. | Restoration/readback records; `final_report.md` | Both trigger sources and all eight T660 outputs were off. |

### 2.3 Analysis and uncertainty workflow

The sign convention remained CHB minus CHA, with splitter S2 minus S1. For each
realization, midpoint and half-difference swap algebra yielded channel/path and
splitter estimates. The final estimate was the midpoint of the two complete
realizations. The reconnection contribution was half their range. The combined
uncertainty also retained repeat statistics, sample resolution, threshold
sensitivity, interpolation sensitivity, and the configured 2 ppm timebase term
as documented in `ms02_results.json`.

### 2.4 Deviations and limitations

No rejected MS-02 traces are recorded. The design intentionally contains two,
not many, reconnection realizations; the half-range treatment must not be
described as an empirical reconnection standard deviation. PicoScope certificate
and splitter manufacturer data remained unavailable.

## 3. Results — WHAT

| Quantity | Result | Qualification |
| --- | ---: | --- |
| PicoScope channel/path skew, CHB minus CHA | `0.109947073 ± 0.581707394 ns` | Combined standard uncertainty |
| Splitter branch skew, S2 minus S1 | `0.013383015 ± 0.577390856 ns` | Combined standard uncertainty |
| Channel/path reconnection difference | `-0.020058898 ns` | Difference between two complete realizations |
| Splitter reconnection difference | `+0.008218018 ns` | Difference between two complete realizations |
| Maximum scope threshold half-range | `0.005605248 ns` | 3000–7000 ADC study |
| Scope interpolation-method difference | `0.069976522 ns` | Linear versus nearest sample |

The new MS-02 population contained 200 accepted traces and zero rejections;
including the imported MS-01 realization, the comparison used 400 accepted
traces. Mean pulse widths were approximately 149.93–149.95 ns and mean 10–90%
rise times approximately 6.99–7.03 ns.

All phase criteria passed and the recorded scientific disposition is complete.
This retrospective document remains review pending.

## 4. Implications, caveats, and claims

The reported correction values may be imported by later timing analyses that use
the same PicoScope channels, settings, leads, reference planes, and sign
convention. The two-realization comparison supports a bounded reconnection term
and shows small threshold sensitivity relative to the dominant sampling term.

The phase does not support correction of arbitrary scope configurations,
reconnected cable populations, splitter frequency response, or certificate-level
traceability. It also does not justify treating the two reconnections as a large-
sample distribution. Later route phases must preserve the common correction as a
shared, correlated input rather than count it repeatedly as independent evidence.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Inherited realization | `../MS-01/ms01_results.json` and retained MS-01 traces | Do not copy or relabel the source acquisition. |
| Second realization | `reconnection_normal/`; `reconnection_swapped/` | Apply the same eligibility and sign convention. |
| Full-precision estimates and uncertainty | `ms02_results.json` | Numerical authority for reported values. |
| Sensitivities and pulse fidelity | `offline_analysis.json`; `final_report.md` | Preserve threshold band and estimator definitions. |
| Restoration | Final restoration/readback records | Verify normal clock distribution and safe idle. |

Minimal reproduction is to evaluate both complete realizations with the retained
analysis, form each swap estimate, then calculate the two-realization midpoint and
half-range contribution. Compare with `ms02_results.json`; do not use a stored hash
as an acceptance gate.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Verify inherited and new trace counts. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Review uncertainty and reconnection interpretation. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
