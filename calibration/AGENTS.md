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
6. Preserve raw and rejected acquisitions.
7. Record unavailable information as `USER_INPUT_REQUIRED` and continue with
   unrelated valid calibration work.
8. Update the same phase record when work resumes on another day.
9. Guide restoration and record the final equipment state.
10. Stop at the approved phase boundary.

Do not invoke `tests/hardware_checks/check_complete_timing_calibration.py` as
the calibration operator interface. Its implementation may be reused in
focused utilities and tests.

Do not create a new campaign plan or phase directory merely because a session
resumes. Keep canonical calibration outputs unchanged unless the user supplies
the exact phrase `APPROVE CALIBRATION PROMOTION`.
