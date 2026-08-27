# Codex instructions for characterization campaigns

These instructions apply to characterization procedures and
characterization-domain phase work in the unified campaign/evidence hierarchy.

## Operator-led phased execution

Treat the approved characterization sequence and its calibration dependencies
as authoritative.

Before CH-00 freezes scope, use requirements-level experiment designs to select
only the claims and operating conditions that characterization must support.
Do not finalize executable biological recipes or numeric settings before their
required promoted results exist. The lab has a power meter but no energy
meter; do not add direct pulse-energy or calibrated peak-power deliverables
unless new metrology is explicitly approved.

1. Work only on the single approved phase and its canonical evidence record from
   `campaigns/registries/evidence_locations.yaml` or the future-location rule.
2. Read existing evidence and imported calibration links before acting.
3. Never repeat a completed calibration or characterization measurement merely
   to change format, plotting, or aggregation.
4. Give the operator one physical action at a time and wait for the actual
   observation before recording physical state.
5. Preserve every native raw, rejected, preview, control, excluded, and
   superseded acquisition under the shared measurement-campaign data contract
   and follow the repository-level provenance restrictions.
6. Maintain `procedural_writeup.md` from the contemporaneous record and require
   its indexed, manifest-linked, reviewer-accepted state under
   `docs/data_contract/procedural_writeup_standard.md`, together with every other
   mandatory deliverable, before phase closure or advance.
7. Record unavailable information as `USER_INPUT_REQUIRED`; do not encode it as
   zero or silently narrow the uncertainty budget.
8. Apply the phase-specific safe-idle, emission, shot-budget, restoration, and
   ownership gates. Stop at the approved phase boundary.
9. Resume the same phase directory on another day; do not create a replacement
   record unless the approved plan explicitly defines a new phase run.
10. Do not modify promoted calibration evidence. Link it by campaign, phase,
    artifact, and calibration-bundle identifiers.

No canonical characterization summary is promoted without the exact phrase
`APPROVE CHARACTERIZATION PROMOTION`.

Historical writeups are retrospective evidence reconstructions. Preserve the
recorded scientific disposition, identify unknowns and later interpretation, and
never repeat a completed measurement solely to improve the narrative.
