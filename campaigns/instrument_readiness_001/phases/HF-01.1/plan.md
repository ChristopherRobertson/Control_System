# HF-01.1 — experiment-specific HF2LI candidate optimization and targeted electrical confirmation

Status: **PLANNED; NOT EXECUTED**

Required dependencies: `HF-01, CH-00.1, MS-02.1`

This is the canonical phase plan. It does not authorize hardware, acquisition,
status changes, or promotion. Universal execution, retention, restoration, and
procedural-writeup requirements are in
`../../requirements.md`.

HF-01 remains PASS and immutable. Import its three accepted anchors, validated complex
filter/transfer model, supported-space readback, timing/reference and dual-input
equivalence, range/clipping/loss/reload/restoration evidence, uncertainties, and the
approximately 1 us uncooled-MbCO limitation by stable links. No imported evidence is
represented as a new acquisition.

Freeze separate requirement identities for slow scanning and for each of the five
time-resolved reconstruction methods: wavelength-by-wavelength, repeated rapid scan,
nanosecond fixed-wavelength, microsecond fixed-wavelength, and single-pump
phase-shifted rapid/log scan-burst acquisition. Room-temperature HRP,
room-temperature MbCO, 77 K HRP, and 77 K MbCO are separate configuration families;
nanosecond and microsecond acquisitions remain distinct even when they share hardware
or a numerical envelope. Detector noise, signal range, duration, distortion tolerance,
temporal resolution, throughput/loss, clipping, settling, trigger rate, event spacing,
and robustness are explicit inputs. Missing optical, detector, cryostat, or architecture
inputs are `USER_INPUT_REQUIRED` and keep candidates provisional.

Enumerate the complete retained HF-01 supported space without hard-coded experiment
selections. Reject only installed-constraint or frozen-requirement failures. Produce
separate full tables, Pareto frontiers, shortlists, and sensitivity results. Apply
deterministic tie-breaks: feasibility, worst-case normalized margin, distortion,
duration, data volume, then lexicographic setting tuple.

After AR/PF/IRF inputs establish an eventual winner, confirm only that winner and the
nearest meaningful Pareto challenger for each distinct numerical configuration.
Reuse exact HF-01 support where the validity envelope covers the requirement and no
physical trigger exists. Issue stable `HF011-CFG-*` IDs with explicit
`supersedes_for_future_use`, `electrically_equivalent`, or
`distinct_requirement_same_settings` relationships. Closeout includes a complete
HF-01 evidence-reuse matrix and never changes HF-01 history. It also requires an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md` under
`docs/phase_record_contract.md`, covering the optimization
rationale, actual candidate-generation and targeted-confirmation steps, complete
candidate/result accounting, selection uncertainty, reuse boundaries, caveats,
supported/unsupported claims, and downstream configuration supersession.

## `EXPERIMENTS.md` allocation and decision contract

This phase implements the HF2LI candidate-selection portion of `EXP-CAL-13`,
`EXP-CHAR-02`, `EXP-CHAR-07`, `EXP-OPT-02`, and `EXP-OPT-05` through the canonical
CH-00.1 traceability matrix. It consumes accepted HF-01 electrical evidence plus
MS-02.1 branch-transfer evidence, CH-00.1 requirement identities, and later
architecture/noise/IRF measurements. Reference planes, input path, coupling, range,
filter, sampling, trigger, demodulation, recorder, overflow handling, and software
schema are configuration identity rather than hard-coded campaign constants.

Native settings/readbacks, raw targeted-confirmation streams, candidate tables,
rejection reasons, uncertainty propagation, and restoration evidence are retained.
Acceptance requires an auditable feasible-set decision for every retained configuration
family; missing inputs, clipping, unsupported transfer correction, or unmet resolution
and uncertainty bounds reject or leave a family provisional. Revalidation is triggered
by changes to detector/branch topology, HF2LI firmware or settings semantics, recorder
path, trigger source, timing reference, analysis version, or the frozen experiment
requirements. Consumers include AR-01, PF-00, IR-01, E2E-01, both biological campaigns,
and promoted configuration bundles. This phase does not establish optical alignment,
detector linearity, cryogenic sample readiness, a chemical time zero, or biological
kinetics.

## Preserved procedure-catalog detail


### 12a. HF-01.1 — experiment-specific HF2LI candidate optimization and targeted electrical confirmation

Status: **PLANNED; NOT EXECUTED**. The canonical plan is
`campaigns/instrument_readiness_001/phases/HF-01.1/plan.md`. It imports completed
HF-01 evidence, freezes distinct acquisition-mode requirements, computes separate
Pareto frontiers over the complete supported space, and limits any later physical
confirmation to the winning configuration and nearest meaningful challenger. It
does not reopen HF-01 or alter its historical selection and decision.
