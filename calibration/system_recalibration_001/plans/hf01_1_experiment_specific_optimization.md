# HF-01.1 — experiment-specific HF2LI candidate optimization and targeted electrical confirmation

Status: **PLANNED; NOT EXECUTED**

Authority and preservation rules are in `docs/campaign_reconstruction_20260826.md`.
HF-01 remains PASS. This phase imports its three accepted anchors, validated complex
filter/transfer model, supported-parameter-space readback, timing/reference and dual-
input equivalence, range/clipping/loss/reload/restoration evidence, uncertainties,
and the approximately 1 us uncooled-MbCO limitation by stable links. Nothing is
copied into HF-01.1 as a new acquisition.

## Prospective inputs

Freeze a separate requirement record for: `SWEEP-CONTINUOUS`, `HRP-FIXED`,
`HRP-PHASE-SCAN`, `MBCO-CRYO-FIXED`, and `MBCO-CRYO-PHASE-SCAN`.
`HRP-WAVELENGTH-STEP` and `MBCO-CRYO-WAVELENGTH-STEP` retain distinct mode IDs but
use their fixed-wavelength numerical envelope unless a declared requirement differs.
Each record contains detector noise, signal range, duration, distortion tolerance,
temporal resolution, output/throughput and loss limits, clipping margin, settling,
and uncertainty/robustness criteria. Unknown optical, detector, or cryostat values
are `USER_INPUT_REQUIRED` and make results provisional.

## Deterministic computation

Enumerate the complete HF-01 supported space; do not embed an experiment selection
in code. Reject only settings violating installed constraints or a frozen numerical
requirement. Evaluate the validated HF-01 transfer model, effective noise bandwidth,
settling, output-rate/filter-bandwidth validity, sampling/loss, dynamic range,
distortion, and duration. Record code and data versions and deterministic tie-breaks:
feasibility, largest worst-case normalized margin, lowest distortion, shortest
duration, lowest data volume, then lexicographic setting tuple.

Produce a separate full table, Pareto frontier, shortlist, and sensitivity analysis
for every mode. Coincident numerical settings do not establish equivalent
requirements. Each row records requirement ID and configuration ID separately.

## Confirmation and closeout

After AR-01/PF/IRF inputs identify an eventual winner, physically confirm only that
winner and its nearest meaningful Pareto challenger for each distinct numerical
configuration. Reuse exact HF-01 confirmation when its configuration and validity
envelope cover the need and no physical trigger exists. Otherwise run a targeted
confirmation, not HF-01 wholesale repetition.

Issue stable `HF011-CFG-*` IDs and an explicit relationship to retained `HF01-CFG-*`
IDs: `supersedes_for_future_use`, `electrically_equivalent`, or
`distinct_requirement_same_settings`. Closeout includes requirements, supported-space
snapshot, selection logic, frontiers, shortlists, confirmation evidence, uncertainty,
configuration registry, supersession/equivalence registry, restoration, unresolved
inputs, and a completed-evidence reuse matrix mapping every result to HF-01 artifact
and acquisition IDs.
