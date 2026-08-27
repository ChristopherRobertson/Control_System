# Instrument-readiness phase execution requirements

Version: `1.0.0`  
Status: **REQUIRED FOR EVERY INSTRUMENT-READINESS PHASE**

## 1. Authority and organization

The authoritative dependency and status record is
`../../phase_registry.yaml`; the human-readable execution view is
`../../master_sequence.md`. The sole active definition of each phase is:

```text
campaigns/instrument_readiness_001/phases/<phase-id>/
├── README.md
├── phase.yaml
├── plan.md
├── run_record.md                 # when retained from an executed phase
├── phase_manifest.json           # when produced
├── acquisition/artifact/result indexes and logs
├── raw/, analysis/, figures/, and tables/
├── final_report.md and restoration records
└── <other phase-specific planning and execution records>
```

`phase.yaml` identifies the phase, domain, dependencies, registry state, evidence
key, evidence location, and canonical plan. `plan.md` contains the phase-specific
purpose, procedure, acceptance logic, and deliverables. Supporting files may
preserve requirement briefs, recipe contracts, or rows extracted from historical
cross-phase planning matrices.

The registry domain (`calibration`, `characterization`, `validation`, or
`promotion`) describes the work; it does not create a second hierarchy or a
separate execution sequence. Do not add a phase plan anywhere outside its phase
directory. `shared/` contains only requirements, methods, history, crosswalks, and
comparison tables that apply to more than one phase.

## 2. Preserve completed work

The restructure is organizational, not scientific reacquisition. The canonical
phase home is the evidence package registered in
`../../registries/evidence_locations.yaml`; it does not link to a second external
phase tree. Relocation does not copy or alter accepted artifacts, manufacture a
new run, or change a historical scientific disposition.

When a completed phase lacks a document now required by the current data contract,
backfill the document from retained evidence. Mark irrecoverable facts as unknown
and bound the resulting claims. Never rerun a completed measurement only to satisfy
a new directory layout, template, or documentation rule. A new acquisition is
allowed only when independently justified and explicitly authorized as new work.

Historical manifests may name repository paths that existed at acquisition time.
Those strings are part of the historical provenance record. Current phase plans
must use the new canonical paths, but accepted evidence must not be silently
rewritten to conceal the migration.

## 3. Authorization and session boundaries

Creating, editing, reviewing, or discussing a plan does not authorize physical
execution. Before any hardware action, acquisition, phase-state change, closeout,
or promotion, obtain the authorization required by the phase plan and current
operator workflow.

During an approved operator-guided session:

1. Confirm the exact phase ID and its dependency state from the registry.
2. Read the complete phase plan, this shared standard, the applicable hardware
   configuration, wiring map, safety constraints, and imported bundle records.
3. Establish the initial instrument state and evidence destination before changing
   anything.
4. Present one physical action at a time and wait for the operator's actual
   observation or readback. Never infer that an action occurred.
5. Record configuration, acquisition, observation, decision, deviation, and
   restoration evidence contemporaneously in the phase directory.
6. Stop immediately on an interlock, unexpected emission or motion, unsafe state,
   ownership conflict, missing required input, or plan-defined stop condition.
7. Stop at the authorized phase boundary. A successful phase does not implicitly
   authorize its successor or promotion.

Use `USER_INPUT_REQUIRED` for information that only the operator can supply. Do
not replace a missing observation, setting, serial identity, safety confirmation,
or scientific judgment with an assumption.

## 4. Entry review

Before execution, record and resolve as applicable:

- required and optional dependencies, including the exact imported result or
  bundle IDs and their validity envelopes;
- device identities, firmware, drivers, SDKs, software, recipe, analysis, schema,
  and configuration versions;
- wiring, optical topology, reference planes, grounding, channel roles, detector
  roles, ranges, rates, time origins, and sign conventions;
- environmental, stabilization, warm-up, purge, sample, exposure, and metrology
  requirements;
- predeclared acceptance criteria, exclusion rules, stop rules, replication,
  uncertainty treatment, and decision logic;
- expected raw, processed, figure, table, report, restoration, and writeup
  deliverables; and
- the safe idle state and the procedure for returning to it.

Do not repeat an upstream calibration or characterization grid when a retained
result covers the needed configuration and validity envelope. Import it by stable
ID and state precisely how it is used. If coverage is inadequate, document the
gap and obtain authorization for a bounded new measurement.

## 5. Evidence package

New evidence uses the measurement-campaign data contract in
`../../../docs/data_contract/measurement_campaign_data_contract.md`. The
phase directory must retain or index, as applicable:

- phase and run manifests, artifact index, configuration snapshots, readbacks,
  operator/command log, source and producer records, and environment records;
- raw/native acquisitions without undocumented conversion or overwriting;
- processed tables, analysis inputs and outputs, code/parameter versions,
  exclusions, uncertainty records, diagnostics, figures, and tables;
- controls, previews, rejected, failed, aborted, superseded, or bypassed attempts
  when they affect interpretation;
- deviations, troubleshooting, approvals, photographs, wiring/topology records,
  restoration evidence, and unresolved-input records;
- `final_report.md` containing the formal acceptance decision and downstream
  authorization; and
- `procedural_writeup.md` containing the thesis-quality scientific narrative.

Use stable human-readable IDs, relative paths, byte sizes, UTC timestamps,
software/schema/analysis versions, branch or commit references, dirty-file lists,
device/configuration identities, and source records. Checksums may be recorded as
diagnostic provenance, but a repository-authored hash match must never be the sole
condition for loading, analysis, aggregation, reproduction, acceptance, closeout,
or promotion.

## 6. Procedural writeup

Every phase—including historical, failed, bypassed, analysis-only, validation,
and promotion phases—requires a distinct `procedural_writeup.md` following
`../../../docs/data_contract/procedural_writeup_standard.md` and the repository
template at `../../templates/phase_record/procedural_writeup.template.md`.

At minimum, the document must provide thesis-level treatment of:

1. **WHY:** the scientific or engineering purpose, thesis relevance, dependency
   or uncertainty addressed, predeclared questions and acceptance criteria,
   downstream consumers, tested validity envelope, and excluded scope.
2. **HOW:** a chronological step-by-step account of what was actually done,
   including entry state, equipment and configuration, controls and replication,
   actions and observations, settings and decision rules, evidence IDs, analysis
   and uncertainty methods, deviations, troubleshooting, stopping, and
   restoration.
3. **WHAT:** all relevant results, attempted and retained populations, exclusions,
   units, estimators, uncertainty or explicit limitations, configuration and
   reference-plane context, tables/figures, criterion-by-criterion outcomes, and
   scientific disposition.
4. **IMPLICATIONS, CAVEATS, AND CLAIMS:** supported claims with bounded validity,
   prohibited or unsupported extrapolations, limitations and systematic risks,
   consequences for software/configuration/later phases/thesis scope, and owned
   follow-up work.

The writeup explains the evidence; it does not replace machine-readable results,
raw records, or the final report. It must distinguish observations, derived
quantities, model-dependent inferences, decisions, and interpretations. It must
not invent missing details.

Before documentation closeout, index the writeup in `artifacts.csv`, link it from
`phase_manifest.json`, record document control and review metadata, resolve or
explain all placeholders, and obtain named human evidence-traceability and
thesis-readiness acceptance. An accepted narrative is immutable; corrections are
new indexed revisions that retain and supersede the prior version.

For phases already scientifically complete, follow
`procedural_writeup_backfill_register.md`. Backfill changes documentation state,
not the preserved scientific disposition. No reacquisition is required merely
because the narrative did not exist under the earlier standard.

## 7. Standing installed-system constraints

The following requirements carried by the former combined catalogs remain active
where applicable:

- Under `../../../instrument/default_wiring_state.md`, “default wiring restored”
  means T660-1 CHD and MIRcat DB9 pin 5 are disconnected, while MIRcat DB9 pins 6
  and 8 are unused and unwired. These are standing operator-confirmed conditions
  unless the operator reports a change.
- Hardwired room and door interlocks are external infrastructure. Repository
  software does not duplicate them as a substitute safety system.
- The retained OPO-540 path uses the permanent ATT-01-qualified electronic iris.
  Every applicable phase retains the iris device/configuration ID, service or
  driver/API version, command, readback, qualified aperture/tolerance, and fault
  state. Loss of ownership, communication, or accepted readback blocks OPO
  emission. The iris is not a personnel-safety shutter or finite-exposure device.
- Every applicable WaveMaster record retains the qualified working-reference
  bundle, device/adapter/probe identities, units, pulse/CW mode, autocalibration
  state, geometry, native time/value/status, quality state, thermal-stability
  classification, and uncertainty. `Multi-Line`, `Saturated`, and `No Signal` are
  measurement outcomes, not numeric wavelengths. A center wavelength neither
  assigns spectral-power fractions nor proves that no additional wavelength is
  present.
- A power meter is available but an energy meter is not. Do not claim direct
  pulse-energy distributions, pulse-to-pulse energy jitter, or calibrated peak
  power. Mean pulse energy may be derived from suitable average-power and verified
  repetition-rate evidence only when the derivation and limitation are explicit.

## 8. Acceptance, restoration, promotion, and handoff

Close a phase only after its plan-specific criteria and the common data-contract
requirements are evaluated against retained evidence. Record pass, fail,
conditional, bypassed, stopped, or incomplete outcomes explicitly; do not hide a
failed control, excluded record, unmet criterion, or unresolved dependency.

Where applicable, verify and record restoration to the declared safe idle or
baseline state. Closure of a calibration or characterization phase does not
automatically promote its result into control-software defaults. Promotion is a
separate registered phase with explicit review and authorization. The control
application consumes only the stable promoted-bundle interfaces in `instrument/`,
while campaign evidence and narratives preserve how those inputs were established.

PROM-01 requires the explicit authorization phrase
`APPROVE CALIBRATION PROMOTION`; PROM-CH requires
`APPROVE CHARACTERIZATION PROMOTION`. Neither phrase authorizes an unrelated phase
or retroactively changes historical evidence.

Characterization may be planned in parallel, but emitting or quantitative work
must wait for required calibration inputs to be promoted or explicitly accepted
as bounded provisional inputs in the phase plan and manifest. A discovered
calibration defect opens a separately approved, suffixed calibration investigation;
it is not repaired inside characterization evidence.

Biological campaigns reference promoted calibration and characterization bundle
IDs, operate inside the validated envelope, retain independent sample,
preparation, control, dose, and response evidence, and never mutate readiness
archives. At minimum they inherit the applicable sample-plane fluence/overlap
method, spectral-axis calibration, temporal-origin convention, acquisition
settings, normalization model, sensitivity limits, and revalidation triggers.
HRP-C–CO precedes MbCO. Both inherit the qualified permanent OPO-540 iris and
configuration-validity checks, but keep their biological evidence separate; a
different OPO wavelength cannot inherit the 540 nm qualification.
