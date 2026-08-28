# HF-01.1 — experiment-specific HF2LI candidate optimization and targeted electrical confirmation

Status: **PLANNED; NOT EXECUTED**

This is the canonical phase plan. It does not authorize hardware, acquisition,
status changes, or promotion. Universal execution, retention, restoration, and
procedural-writeup requirements are in
`../../requirements.md`.

HF-01 remains PASS. Import its three accepted anchors, validated complex
filter/transfer model, supported-space readback, timing/reference and dual-input
equivalence, range/clipping/loss/reload/restoration evidence, uncertainties, and the
approximately 1 us uncooled-MbCO limitation by stable links. No imported evidence is
represented as a new acquisition.

Freeze separate requirement identities for continuous scanning, HRP fixed wavelength,
HRP phase-shifted scans, cryogenic MbCO fixed wavelength, and cryogenic MbCO
phase-shifted scans. Wavelength-by-wavelength reconstruction retains a distinct mode
identity even when it shares the fixed-wavelength numerical envelope. Detector noise,
signal range, duration, distortion tolerance, temporal resolution, throughput/loss,
clipping, settling, and robustness are explicit inputs. Missing optical, detector, or
cryostat inputs are `USER_INPUT_REQUIRED` and keep candidates provisional.

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

## Preserved procedure-catalog detail


### 12a. HF-01.1 — experiment-specific HF2LI candidate optimization and targeted electrical confirmation

Status: **PLANNED; NOT EXECUTED**. The canonical plan is
`campaigns/instrument_readiness_001/phases/HF-01.1/plan.md`. It imports completed
HF-01 evidence, freezes distinct acquisition-mode requirements, computes separate
Pareto frontiers over the complete supported space, and limits any later physical
confirmation to the winning configuration and nearest meaningful challenger. It
does not reopen HF-01 or alter its historical selection and decision.
