# P0 — provenance and inventory baseline: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Retained execution campaign | `system_recalibration_001` |
| Phase ID | `P0` |
| Phase run ID(s) | No stable phase-run ID is present in the retained P0 records. |
| Domain | Calibration/readiness foundation |
| Scientific disposition | `COMPLETE` |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Experimental operator | Christopher Robertson |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; evidence-traceability, technical, and thesis review remain pending. |
| Document version | `0.1.0` |
| Execution interval | Physical inventory began 2026-07-23; execution-baseline bookkeeping closed 2026-07-24; final requirement decisions were accepted 2026-08-15. |
| Draft date | 2026-08-27 |
| Governing records | `plan.md`; `p0_execution_baseline.md`; `p0_requirement_decisions.md` |

## Executive synopsis

P0 established what instrument, software, reference materials, wiring resources,
and documentary evidence actually existed before calibration measurements began.
It was deliberately a documentation, inspection, and software-validation phase:
no hardware connection was opened, no device was queried or commanded, no cable
was moved, and no measurement was acquired.

The phase produced an installed-equipment inventory, software provenance,
repository and recipe checks, a blocker register, and 21 final requirement
decisions. It closed the planning baseline without claiming that any listed
device or reference was calibrated. The principal limitation is that several
values came from labels, operator reports, or documents and therefore remained
identity or planning evidence until later phases directly verified behavior.

## 1. Purpose — WHY

The calibration program could not be made reproducible until device identities,
available accessories, installed routes, software versions, source documents,
and missing metrology inputs were separated from assumptions. P0 reduced the
risk of applying a procedure to the wrong T660 unit, treating a nominal cable
length as a measured delay, or treating an undocumented reference as traceable.

Its objective was to create the evidence boundary and decide which proposed
requirements would be kept, narrowed, deferred, or discarded. The phase was not
intended to verify safe idle, acquire timing data, qualify optical behavior, or
authorize S0 or any later hardware phase.

## 2. Procedure performed — HOW

### 2.1 Entry state and evidence sources

The repository, installed software, instrument labels, procurement documents,
operator observations, and existing recipes were inspected. The hardware-access
boundary was frozen in `p0_execution_baseline.md`: documentation and software-
only checks were allowed, while connections, commands, queries, rewiring, and
acquisition were prohibited.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Retained evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | The operator inspected available labels, accessories, installed routes, and spectral-reference materials. | Record exact observed identities and expose missing markings rather than infer them. | `p0_physical_inventory.md` | PicoScope, T660, MIRcat, HF2LI, laser/OPO, detector, cable, splitter, and reference-material identities were recorded with source and timestamp. |
| 2 | Repository paths, recipes, wiring conventions, and inactive MUX-related routes were reviewed. | Establish which paths were current and which were excluded or historical. | `p0_execution_baseline.md`; `p0_physical_inventory.md`; `prehardware_provenance.md` | Direct wiring was retained; the disabled Arduino MUX and a historical splitter use were not treated as active measurement paths. |
| 3 | Installed application, DLL, driver, package, Python, PowerShell, and Windows information was inventoried without opening a device. | Make later acquisitions attributable to an identified software environment. | `p0_execution_baseline.md`; `p0_python_environment.txt` | PicoScope, MIRcat, and LabOne software provenance was recorded; live device firmware remained for S0. |
| 4 | Software-only tests and configuration checks were run. | Verify that the procedure code and control-app support functions were internally usable before hardware access. | `p0_execution_baseline.md` | Timing tests passed 17/17, T660 persistent-state tests 6/6, experiment-builder tests 6/6, and the listed workflow/configuration checks passed. |
| 5 | Missing resources and ambiguous requirements were collected in a blocker table. | Prevent missing information from being represented as zero or silently ignored. | `p0_blocker_table.md` | The unresolved items were made explicit and assigned later owners or decisions. |
| 6 | Twenty-one requirement dispositions were reviewed and accepted. | Bound the campaign to work that was necessary and supportable. | `p0_requirement_decisions.md` | Each item received an accepted KEEP, NARROW, or DISCARD disposition; later phases inherited those decisions. |
| 7 | The repository baseline and bookkeeping were closed without hardware activity. | End P0 at its authorized boundary. | `p0_execution_baseline.md`; `post_merge_provenance.md` | P0 was recorded complete; S0 still required separate authorization. |

### 2.3 Analysis and uncertainty treatment

P0 used classification rather than numerical estimation. Evidence was labeled by
source—physical label, operator report, installed-file metadata, procurement
document, or repository inspection. Unknown manufacturer characteristics,
certificate information, dimensions, and uncertainties remained unresolved or
were assigned to later phases. No identity observation was promoted to a device-
performance or calibration claim.

### 2.4 Deviations and restoration

No physical procedure was performed, so no hardware restoration was required.
T660 firmware was not guessed from prior knowledge; it was explicitly deferred
and later resolved by the S0 readbacks. Contemporaneous absolute paths are
retained as historical provenance, while current repository links use the
canonical phase directory.

## 3. Results — WHAT

- The installed inventory distinguished T660-1 serial `00369` from T660-2
  serial `00431`, recorded PicoScope 5244D serial `10261`, MIRcat serial `10524`,
  HF2LI device `dev18500`, installed source identities, both detector chains,
  and available polystyrene and Mylar materials.
- `CLOCK-SPLITTER-01` received a campaign-local identity, but its manufacturer,
  bandwidth, insertion loss, and branch symmetry were not claimed.
- Signal-dependent measurement assemblies and cable lengths were documented as
  configuration inputs, not as substitutes for measured propagation delay.
- The software-only validation suite reported all listed checks passing.
- All 21 requirement decisions were accepted and became the planning basis for
  subsequent readiness work.
- No raw measurement population exists for P0 because acquisition was expressly
  outside scope.

The recorded scientific disposition is complete. This retrospective narrative
does not change that disposition and is not yet reviewer-accepted documentation.

## 4. Implications, caveats, and claims

### Supported claims

P0 supports the claim that the campaign began from an explicit, source-labeled
inventory and an accepted requirement-disposition record. It also supports the
negative claim that no hardware access or measurement occurred during P0.

### Unsupported or prohibited claims

P0 does not establish timing, gain, spectral accuracy, optical power, detector
response, reference traceability, safe-idle behavior, or readiness to emit. A
recorded model or serial number is not evidence of installed performance.

### Caveats and downstream implications

Some identities and route descriptions were operator-reported rather than
queried. Missing certificate and manufacturer information remained explicit.
Later phases were therefore required to import the P0 identities but establish
their own readbacks, configurations, uncertainties, and validity envelopes.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Hardware-access boundary and software checks | `p0_execution_baseline.md` | Review the dated statement and enumerated check results; do not rerun hardware. |
| Installed identities and routes | `p0_physical_inventory.md` | Preserve each value's source and timestamp. |
| Requirement disposition | `p0_requirement_decisions.md` | Account for all 21 accepted decisions. |
| Unresolved planning inputs | `p0_blocker_table.md` | Interpret in light of the later accepted decision register. |
| Repository provenance | `prehardware_provenance.md`; `post_merge_provenance.md` | Treat hashes as informational provenance, never an operational gate. |

Minimal reproduction consists of reading those retained records, confirming the
decision count and source labels, and verifying that no P0 record claims a device
command or acquisition. Native evidence must not be rewritten.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Draft reconstructed solely from retained P0 records. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Confirm identity wording and scope boundaries. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
