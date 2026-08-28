# TR-01 — retained identity and measurement-resource closure: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Retained execution campaign | `system_recalibration_001` |
| Phase ID | `TR-01` |
| Phase run ID | `system_recalibration_001_TR-01_001` |
| Domain | Calibration/resource governance |
| Scientific disposition | `PASS — COMPLETE` |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Experimental operator | Christopher Robertson, as identified in predecessor records |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; review remains pending. |
| Document version | `0.1.0` |
| Execution interval | Records-only closeout; exact UTC drafting interval is retained in artifact metadata and was not inferred here. |
| Draft date | 2026-08-27 |
| Governing records | `plan.md`; `run_record.md`; `phase_manifest.json`; `final_report.md` |

## Executive synopsis

TR-01 converted the P0 inventory and completed calibration evidence into a
usable measurement-resource register. Its purpose was not to repeat a
measurement, but to state which items were working references, which were
devices under test, what evidence supported each identity or behavior, and what
validity limitations later phases had to preserve.

The records-only audit passed. PicoScope 5244D serial `10261` was retained as the
electrical timing working reference under its documented configurations and
manufacturer bounds, while T660, MIRcat, HF2LI, detector, Nd:YAG, and OPO
resources remained devices under test. Polystyrene and Mylar remained deferred,
comparison-only spectral candidates. No device client was opened, no hardware
state changed, and no evidence was copied or reacquired.

## 1. Purpose — WHY

Calibration results are reusable only if later work can identify the resource,
configuration, uncertainty basis, validity envelope, and source evidence. P0 had
recorded many identities and gaps; completed timing/control phases had qualified
specific behaviors. TR-01 reconciled those records without elevating every listed
device to reference status or reviving discarded requirements.

The phase acceptance criteria required a complete resource register, all 21 P0
decisions accounted for, explicit provenance and limitations, retained source
evidence linked in place, and no unsupported traceability claim. Optical
qualification, source/detector characterization, promotion, and hardware activity
were outside scope.

## 2. Procedure performed — HOW

### 2.1 Input eligibility

Only retained P0 records and completed phase evidence were eligible. Accepted,
rejected, partial, comparison-only, excluded, and superseded source records
remained in their original phase packages. TR-01 referenced stable identities and
paths rather than copying them into a new measurement record.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | All 21 final P0 requirement decisions were exported. | Ensure every retained/narrowed/discarded input was accounted for. | `p0_decision_export.csv`; `../P0/p0_requirement_decisions.md` | Complete decision coverage was recorded. |
| 2 | Available instruments, sources, detectors, standards, and environment monitor were entered into a resource register. | Give each resource a stable identity and explicit role. | `measurement_resource_register.csv` | Twelve resources were classified with evidence and limitations. |
| 3 | Completed phase evidence was linked by stable source and artifact identities. | Reuse established behavior without copying or reacquiring it. | `source_provenance_index.csv`; `calibration_links.csv` | MS-01 through MC-01 and CH-00 evidence remained phase-primary. |
| 4 | Working-reference, device-under-test, deferred, and observational-only dispositions were assigned. | Prevent identity or manufacturer information from becoming an unsupported calibration claim. | `measurement_resource_register.csv`; `uncertainty_ambiguity.md` | PicoScope was the bounded electrical working reference; other roles remained limited. |
| 5 | Software/schema/configuration provenance and applicability were recorded. | Make later reuse conditional on explicit versions and configurations. | `conditions.csv`; `phase_manifest.json`; `final_report.md` | MIRcat and LabOne runtime versions and data-contract version were retained. |
| 6 | Unresolved inputs and exclusions were classified by downstream owner. | Keep missing information visible without blocking unrelated closure. | `unresolved_inputs.md`; `exclusions.csv` | Spectral and optical inputs remained deferred to their named phases. |
| 7 | Required tables, identifiers, paths, byte sizes, and relationships were audited. | Confirm that the records-only package was internally usable. | `retention_audit.md`; `artifacts.csv` | Audit passed; no hash comparison was used as an operational gate. |
| 8 | The existing final physical state was recorded without opening a client or changing hardware. | Close at the records-only boundary. | `restoration_confirmation.json`; `run_record.md` | No restoration action was required and no promotion occurred. |

### 2.3 Analysis and uncertainty workflow

TR-01 introduced no new measured quantity. Its analytical operation was
classification: each resource was paired with a source, applicable configuration,
uncertainty/reference basis, validity limit, and disposition. Manufacturer values
were kept as specifications, installed campaign results as measured behavior, and
unqualified capability as unvalidated. Missing values were not replaced by zero.

### 2.4 Deviations and restoration

No hardware, acquisition, or measurement deviation occurred because the phase was
records-only. The final recorded state was inherited from completed MC-01:
MIRcat powered down, shutter closed, interlock inhibiting, default wiring restored,
and T660 safe idle retained. TR-01 did not claim a new observation of that state.

## 3. Results — WHAT

- All 21 P0 decisions were exported and accounted for.
- The resource register contains 12 stable resource rows spanning the PicoScope,
  two T660s, MIRcat, HF2LI, two detector chains, Nd:YAG, OPO, polystyrene,
  Mylar, and the observational environment monitor.
- PicoScope 5244D serial `10261` was retained as a bounded electrical timing
  working reference for the recorded 8-bit/DC/channel/range/timebase settings.
- T660, MIRcat, HF2LI, detectors, Nd:YAG, and OPO remained devices under test,
  with only specifically linked behaviors qualified.
- Polystyrene and Mylar remained comparison-only until SP-01 establishes the
  authoritative feature values and uncertainty needed for spectral claims.
- Required tables and paths passed the retention audit; no physical acquisition
  was attempted and no canonical output was promoted.

## 4. Implications, caveats, and claims

TR-01 supports a bounded resource-governance claim: later phases can identify
what resource and completed result they are using and the associated limitation.
It does not create accredited traceability or convert a device under test into a
reference. The PicoScope manufacturer timebase/gain bounds apply only under their
stated configuration and conditions, and completed analyses retain their own
measurement-path uncertainties.

No absolute spectral, power, detector, source, or environmental-correction claim
follows from this phase. Polystyrene/Mylar gaps, unsynchronized host/device clocks,
and DIO21 ambiguity remain explicit. Later phases must record their own versions
and settings and consume completed values through calibration links.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Resource roles and limits | `measurement_resource_register.csv` | Account for every row and preserve disposition wording. |
| P0 decision coverage | `p0_decision_export.csv` | Verify all 21 stable decision IDs. |
| Completed-source links | `source_provenance_index.csv`; `calibration_links.csv` | Follow sources in place; do not duplicate acquisitions. |
| Uncertainty classification | `uncertainty_ambiguity.md` | Keep manufacturer, measured, and unvalidated classes distinct. |
| Retention and closure | `retention_audit.md`; `restoration_confirmation.json` | Validate IDs/paths/relationships without hash gating. |

Minimal reproduction is a read-only join of the P0 decision export, resource
register, provenance index, and calibration links followed by the documented
retention checks. No hardware action is part of reproduction.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Verify resource and P0-decision coverage. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Review reference/device classifications and limits. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
