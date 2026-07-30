# Complete system recalibration run

Campaign: `system_recalibration_001`

Status: **S0 COMPLETE — MS-01 READY; LATER PHASES NOT APPROVED**

P0 completed without hardware access. S0 then passed on 2026-07-24 with
exclusive T660/MIRcat ownership, all eight T660 outputs verified disabled
before identity readback, the approved safe-idle recipe fully matched, MIRcat
emission/armed/scan states verified inactive, and the installed interlock
verified set. No cable was moved, neither laser was fired, and no measurement
was acquired. The evidence is in `readbacks/S0/`.

Historical calibration files are comparison-only. Canonical calibration files
must not be changed without the exact approval phrase
`APPROVE CALIBRATION PROMOTION` after all gates pass.

The active campaign is confined to
`C:\Users\Chris\Documents\GitHub\Control_System\calibration\system_recalibration_001`.
The former `Control_System_timing` worktree has been merged into `main` and removed.
References to that worktree in dated provenance snapshots describe the historical
capture environment only and are not active paths.

## Codex-led execution model

The campaign sequence and `docs/timing_calibration_procedure.md` define what is
measured and how. Codex orchestrates execution interactively; no complete
workflow runner is used.

For the active phase, Codex works only in `readbacks/<phase>/`, inspects
existing evidence, gives one physical action in plain language, and waits for
Christopher Robertson's response. Operator-confirmed facts remain distinct
from software readbacks. Focused utilities may perform ownership, safe idle,
capture, or analysis. Raw and rejected traces are preserved. Missing
information is recorded as `USER_INPUT_REQUIRED`. The same phase record is
updated across days, followed by guided restoration and a stop at the approved
phase boundary.

The complete timing runner is not a campaign entry point.

## Phase implementation map

| Phase | Codex orchestration |
|---|---|
| MS-01 | Guide normal and swapped S1/S2 routing; acquire raw PicoScope traces; record channel/path-skew inputs. |
| MS-02 | Analyze the MS-01 captures with swap algebra; add only sensitivity or reconnection captures required by the technical procedure. |
| T2-01 | Guide each T660-2 destination route and six-point electrical sweep. |
| T1-01 | Guide each T660-1 trigger/output route and six-point electrical sweep. |
| PT-01 | Guide the MIRcat Process Trigger electrical setup and polarity/timing acquisition. |
| MC-01 onward | Follow the existing phase procedure interactively using focused utilities and the same stable phase-record pattern. |

## Active MS-01 record

MS-01 evidence belongs in `readbacks/MS-01/`. Direct preflight has already
confirmed PicoScope ownership and a matching T660 safe-idle readback. Codex
continues from that evidence instead of restarting the campaign or launching
`check_complete_timing_calibration.py`.
