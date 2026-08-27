# MS-01 phase record

Operator: Christopher Robertson

Status: **PREFLIGHT COMPLETE — READY FOR CODEX-GUIDED NORMAL ORIENTATION**

## Existing evidence

- `preflight_status.json`: PicoScope ownership passed.
- `safe_idle_initial_readback.json`: T660 safe-idle recipe matched.
- `preflight_command_log.txt`: direct preflight command evidence.
- `run_manual_preflight.py`: focused ownership and safe-idle utility, not a
  complete calibration runner.

## Codex continuation point

Codex guides one action at a time:

1. Identify and park the normal CLOCK-SPLITTER-01 clock connections.
2. Keep the fixed T660-2 CHA SMB-to-BNC bulkhead installed.
3. Park the downstream EXT REF BNC cable.
4. Connect the splitter input directly to the CHA bulkhead.
5. Connect S1 directly to PicoScope CHA and S2 directly to PicoScope CHB.
6. Confirm the third branch is open.
7. Acquire and preserve the normal-orientation traces.
8. Exchange only S1 and S2 at the PicoScope.
9. Acquire and preserve the swapped-orientation traces.
10. Guide restoration, record final safe idle, and stop.

MS-02 analysis is not started automatically. Missing information is recorded
as `USER_INPUT_REQUIRED`.
