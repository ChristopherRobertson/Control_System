# Codex instructions for calibration campaigns

These instructions apply only inside `calibration/`.

## Operator-led phase execution

Treat each campaign sequence and technical calibration procedure as
authoritative for measurement content. Orchestrate execution conversationally:

1. Identify the single approved phase and its stable
   `readbacks/<phase>/` directory.
2. Read existing phase evidence before acting.
3. Give the operator one physical action at a time in plain language.
4. Wait for the operator's observation before recording a physical state.
5. Use focused code only for device ownership, readback, acquisition, or
   analysis.
6. Preserve raw, rejected, preview, control, excluded, and superseded
   acquisitions under `docs/measurement_campaign_data_contract.md` and follow
   the repository-level provenance restrictions.
7. Record unavailable information as `USER_INPUT_REQUIRED` and continue with
   unrelated valid calibration work.
8. Update the same phase record when work resumes on another day.
9. Guide restoration and record the final equipment state.
10. Require the campaign plan's complete mandatory closeout package before a
    phase closes or advances, then stop at the approved phase boundary.

Do not repeat a completed calibration measurement merely to change its format,
plot it, aggregate it, or satisfy a newer schema. Link existing evidence by
stable campaign, phase, acquisition, artifact, and calibration-bundle IDs.

Do not recreate or invoke a monolithic complete-calibration runner. Use only
the approved phase plan and focused phase utilities.

Do not create a new campaign plan or phase directory merely because a session
resumes. Keep canonical calibration outputs unchanged unless the user supplies
the exact phrase `APPROVE CALIBRATION PROMOTION`.
