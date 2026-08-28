# HF-01 — HF2LI configuration and external-reference qualification: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Retained execution campaign | `system_recalibration_001` |
| Phase ID | `HF-01` |
| Phase run ID | `system_recalibration_001_HF-01_001` |
| Domain | Calibration/electrical acquisition characterization |
| Scientific disposition | `PASS` with an explicit MbCO applicability limitation |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Operator | Christopher Robertson |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; review remains pending. |
| Document version | `0.1.0` |
| Execution interval | Exact UTC bounds are preserved across the action ledger and 42 indexed attempts; a single inferred interval is not substituted here. |
| Draft date | 2026-08-27 |
| Governing plan/criteria | `HF01-PLAN-v3`; `HF01-MODEL-RESIDUAL-v3`; authorization `HF01-AUTH-001` with amendments |
| Device/configuration | HF2LI `dev18500`; `HF01-TIMING-COPY-v3`; three selected configuration IDs |

## Executive synopsis

HF-01 electrically characterized the installed HF2LI acquisition chain using a
PicoScope 5244D monitored generator and T660 timing copies. It validated the
manufacturer filter model at three sparse paired-demodulator anchors, evaluated
the installed supported parameter space computationally, selected experiment-
specific configurations, confirmed those selections and the second signal input,
verified reload equivalence, and restored the pre-phase state. Lasers remained
nonemitting and shutters closed.

The fast, intermediate, and replacement slow anchors passed all retained model
criteria. A complete 133,056-row discrete candidate table supported selection of
order 4, about 1.002 ms and 899.465 Sa/s for sweep/HRP work, and the fastest valid
two-channel boundary—order 1, about 5.600 us and 230263.158 Sa/s—for MbCO. The
MbCO boundary is explicitly invalid for the mandatory 1 us feature: it provides
0.230263 sample per microsecond and the modeled response retains only 17.579011%
magnitude. Repeating HF-01 at another supported HF2LI setting cannot remove that
instrument limitation.

## 1. Purpose — WHY

HF2LI settings couple filter order, time constant, sample rate, noise bandwidth,
settling, phase/group delay, throughput, and clipping headroom. Choosing settings
from nominal labels alone could distort scan features or miss fast biological
dynamics. HF-01 was required to validate the installed response model, search the
full supported space, select restorable configurations, and expose any hard
bandwidth limit before downstream detector and acquisition phases.

The phase remained electrical-only. It excluded laser arming/firing, emission,
open shutters, optical alignment, detector response, chemistry, biology,
later-phase execution, and canonical promotion.

## 2. Procedure performed — HOW

### 2.1 Entry state, safety, and topology

The operator freshly confirmed the Nd:YAG/OPO nonemitting state and closed
shutters. PicoScope ownership/AWG-zero and T660 safe idle were verified. The
normal 10 MHz `CLOCK-SPLITTER-01` distribution from T660-2 to T660-1 and HF2LI
was left unchanged. The temporary monitored stimulus was PicoScope AWG through
`HF01-STIMULUS-TEE-01` and retained RG-58 branches to HF2LI Signal Input 1 and
PicoScope CHA. T660-2 supplied DIO/timing copies; no temporary output reached a
laser controller.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | Fresh laser/shutter observations, component labels, PicoScope ownership/AWG-zero, T660 safe idle, and HF2LI prechange settings were recorded. | Establish the nonemitting boundary and a complete restoration target. | `operator_confirmations.md`; preflight JSON/readbacks | Preflight passed. |
| 2 | The temporary monitored stimulus and timing-copy topology was installed under the safe-state gates. | Supply a known electrical stimulus while measuring its connected amplitude and common-clock timing. | `temporary_wiring_plan.md`; `action_ledger.csv`; operator confirmations | Wiring and first nonzero AWG enable were explicitly confirmed. |
| 3 | A bounded 10 Hz timing-copy check and reference/clock diagnostics were performed. | Verify external reference integrity before response characterization. | `HF01-TIMING10-R5-001`; diagnostic records | Accepted timing-copy record retained; T660-1/HF2LI external lock recovered without moving the splitter. |
| 4 | Three predeclared paired-demodulator anchors—fast, intermediate, and slow—were acquired. | Test the installed filter model across the validated response interval. | Anchor acquisition directories; `validation_point_declaration.md` | Fast and intermediate passed; the first slow record exceeded the prospective settling limit. |
| 5 | The identical slow setting was repeated under bounded authorization. | Replace the failed attempt without selecting a more favorable model point. | `HF01-ANCHOR-SLOW-V3-R1-001`; exclusions/deviations | Replacement passed; the first slow record remained rejected. |
| 6 | Demodulator 0 was divided by the synchronized wideband demodulator 1 on exact overlapping timestamps; reference transfer and one bounded pipeline delay were applied. | Estimate magnitude, phase, cutoff, step/settling, and group delay without host-clock phase assumptions. | `analyze_dual_demod_validation.py`; dual-demod analysis report | All criteria passed for the three primary anchors. |
| 7 | The full installed domain was enumerated computationally. | Evaluate supported combinations without running a large physical parameter grid. | Supported-space tables/report; `selected_configurations.json` | 133,056 discrete rows plus the continuous time-constant interval were evaluated. |
| 8 | Unique sweep, HRP, and MbCO configurations were selected under the frozen rules. | Balance response, rate, settling, noise, range, and throughput for each downstream case. | Supported-configuration analysis; `selected_configurations.json` | Sweep and HRP shared numeric settings; MbCO retained only a limited boundary configuration. |
| 9 | Selected and immediately lower rates, Signal Input 2 equivalence, and low/high range endpoints were physically confirmed. | Test the selection boundary and second-channel applicability without expanding to an open-ended grid. | Selected-confirmation acquisitions/report | Selected rates retained; lower rates rejected; both inputs and endpoints passed. |
| 10 | Each configuration ID was loaded twice and the pre-HF-01 settings were restored. | Demonstrate machine-restorable settings and an exact return target. | `HF01-CONFIG-RELOAD-001`; final restoration record | Integer/string nodes matched and maximum observed double-node relative difference was zero. |
| 11 | AWG/temporary outputs were disabled, temporary wiring removed, default routes restored, and final state read back. | Close with no active output, altered wiring, lost sample, or clip flag. | `restoration_confirmation.json`; `HF01-FINAL-RESTORATION-STATE-R1-001` | Final accepted restoration passed after one preserved contention attempt. |

### 2.3 Analysis, controls, and uncertainty workflow

The three anchors used demodulator 0 as the filter under test and demodulator 1
as a same-input, same-clock wideband reference. Exact shared timestamps supplied
the complex ratio. The reference-filter transfer was restored analytically and a
single zero-intercept paired-pipeline delay, bounded below one native sample, was
removed before phase/group-delay comparison. Frozen criteria covered data
integrity, magnitude, phase, complex RMS, cutoff, step/settling, group delay,
positive/negative frequency pairs, clipping, loss, lock, and final idle.

Only after all anchors passed did the analysis enumerate 11 ranges, eight filter
orders, eight input modes, three readout modes, 21 dual-channel rates, and the
continuous writable time-constant interval. Candidate evaluation propagated
attenuation, temporal bias, delay, memory, noise bandwidth, sampling, clipping,
throughput, duration, volume, and validated-model uncertainty. Physical
confirmation was restricted to the selected boundary, the immediately lower
rate, second-input equivalence, endpoints, and reload checks.

### 2.4 Deviations, troubleshooting, and supersessions

Earlier v1/v2 timing/model records are preserved as rejected, diagnostic, or
superseded evidence. The first v3 slow acquisition failed its prospective
settling rule and was replaced once at identical settings; it was not erased or
used in the accepted fit. An analog-reference diagnostic did not lock and remains
rejected. The first final-restoration attempt encountered COM3 contention; the
accepted repeat passed. Photographs were declined by the operator and recorded as
`HF01-DEV-001`; none were fabricated or inferred.

## 3. Results — WHAT

| Anchor/configuration | Result | Qualification |
| --- | ---: | --- |
| Fast anchor | complex RMS residual `0.00005360` | Order 1; 4.000020 us; 230263.158 Sa/s; PASS |
| Intermediate anchor | complex RMS residual `0.00024149` | Order 4; 1.001889 ms; 899.465 Sa/s; PASS |
| Slow replacement anchor | complex RMS residual `0.01767391` | Order 8; 71.1531 ms; 112.433 Sa/s; PASS |
| Sweep selected | order 4; `1.001888708 ms`; `899.465461 Sa/s` | Dynamic validity envelope |
| HRP selected | same numeric settings as sweep | Separate HRP validity envelope |
| MbCO boundary | order 1; `5.600017468 us`; `230263.157895 Sa/s` | Outside mandatory 1 us envelope |

The selected-to-cutoff rate ratio was 13.017 for sweep/HRP and 8.102 for MbCO;
their immediately lower rates produced 6.509 and 4.051 and were rejected. Signal
Input 2 equivalence and range endpoints passed. All 42 attempted acquisitions are
indexed with accepted, rejected, diagnostic, partial, or superseded status; the
retained overview does not collapse those categories into an invented accepted
count.

The phase passed its authorized electrical scope. The MbCO limitation remains a
hard qualification, not a passing 1 us result. No canonical promotion occurred.

## 4. Implications, caveats, and claims

HF-01 supports the installed filter-model response within the three validated
anchors and use of the selected sweep/HRP configurations inside their recorded
electrical validity envelopes. It supports Signal Input 2 equivalence at the
tested settings and reproducible reloading of the three configuration IDs.

It does not qualify optical scan distortion, installed detector noise/clipping,
biological precision, source behavior, or arbitrary settings outside the
validated model envelope. AR-01 retains final optical scan-response authority,
and detector phases must establish their own voltage/noise interval. The MbCO
configuration cannot support a mandatory 1 us feature; the claim or acquisition
path must change rather than merely selecting another HF2LI setting. Changes
listed in `revalidation_triggers.md` require checking or revalidation before
reuse.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Safety/topology chronology | `action_ledger.csv`; `operator_confirmations.md`; `temporary_wiring_plan.md` | Preserve observed physical states and nonemitting boundary. |
| Accepted model anchors | Anchor raw/configuration directories; `analysis/hf01_dual_demod_model_validation_report.md` | Use exact overlapping timestamps and the v3 criterion. |
| Exclusions/supersessions | `exclusions.csv`; `deviations.md` | Retain failed slow, reference, legacy, and contention attempts. |
| Supported-space evaluation | Candidate tables; `analysis/hf01_supported_configuration_report.md` | Enumerate installed settings only after model acceptance. |
| Selected settings and confirmation | `selected_configurations.json`; selected-confirmation report | Preserve downstream envelopes and lower-rate decisions. |
| Reload/restoration | `HF01-CONFIG-RELOAD-001`; final restoration JSON/readbacks | Restore the 25 prechange nodes and default wiring. |

Minimal reproduction runs the retained paired-demodulator analysis on eligible v3
anchors, regenerates the supported candidate table under frozen criteria,
compares selected IDs and confirmation outputs, and audits all 42 indexed attempts.
Native data and criteria remain unchanged; hash equality is not a result gate.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Reconcile 42 attempts, v3 anchors, and all supersessions. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Review model, selection, and MbCO limitation. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
