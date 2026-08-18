# Complete system recalibration run

Campaign: `system_recalibration_001`

Status: **TR-01 PASS - COMPLETE; STOPPED AT OM-01 AUTHORIZATION BOUNDARY**

P0 completed without hardware access. S0 then passed on 2026-07-24 with
exclusive T660/MIRcat ownership, all eight T660 outputs verified disabled
before identity readback, the approved safe-idle recipe fully matched, MIRcat
emission/armed/scan states verified inactive, and the installed interlock
verified set. No cable was moved, neither laser was fired, and no measurement
was acquired. The evidence is in `readbacks/S0/`.

Historical calibration files are comparison-only. Canonical calibration files
must not be changed without the exact approval phrase
`APPROVE CALIBRATION PROMOTION` after all gates pass.

Campaign advancement is controlled only by the documented phase order,
dependencies, mandatory deliverables, acceptance decisions, and explicit
authorizations. Calendar deadlines do not waive or shorten a phase. Recorded
dates and timestamps remain provenance for work that actually occurred.

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

The retired monolithic timing runner is not a campaign entry point.

## Expanded scope and downstream characterization

`plans/campaign_sequence.md` now preserves every completed phase as an
immutable dependency and adds only the retained identity/reference basis, optical-metrology,
attenuation/transfer, detector-latency, reporting, and retention work needed
before quantitative pump/probe characterization. ATT-01 and DET-04 explicitly
measure the non-50/50 sample/reference optical balance, separate it from the
two detector/electronics responses, and produce the normalization correction.
FE-01 qualifies finite admission and independent observation of the rare 532
nm and 540 nm pump events without biological samples; it does not determine
biological dose, recovery, or photolysis. The remaining grids are limited to
the two spectral regions, two acquisition topologies, and source paths in the
verified requirement briefs.
The non-duplication mapping is in `analysis/expansion_gap_map.md`.

The definitive P0 decision record is
`manifests/p0_requirement_decisions.md`. All 21 decisions were resolved on
2026-08-15. Discarded certificate and accessory research cannot reappear as a
phase gate without a new user-approved claim requirement.
The dated P0 blocker table remains historical evidence rather than a second
active requirements list.

Pump/probe beam performance is measured separately in
`characterization/system_characterization_001/`. That campaign imports
promoted calibration quantities through stable bundle/artifact identifiers and
must not reacquire completed calibration work merely to change format or make
plots.

## Phase implementation map

| Phase | Codex orchestration |
|---|---|
| MS-01 | Guide normal and swapped S1/S2 routing; acquire raw PicoScope traces; record channel/path-skew inputs. |
| MS-02 | Analyze the MS-01 captures with swap algebra; add only sensitivity or reconnection captures required by the technical procedure. |
| T2-01 | Guide each T660-2 destination route and six-point electrical sweep. |
| T1-01 | Guide each T660-1 trigger/output route and six-point electrical sweep. |
| PT-01 | Guide the MIRcat Process Trigger electrical setup and polarity/timing acquisition. |
| MC-01 onward | Follow the existing phase procedure interactively using focused utilities and the same stable phase-record pattern. |

## Current phase boundary

The campaign-wide phrase `default wiring restored` follows
`docs/default_wiring_state.md`: T660-1 channel D and MIRcat DB9 pin 5 are
disconnected, and MIRcat DB9 pins 6 and 8 are unused/unwired. These standing
conditions are not repeatedly reconfirmed unless the operator reports a
change.

MS-01, MS-02, T2-01, T1-01, PT-01, CH-00, MC-01, and TR-01 are complete and immutable.
MC-01 qualified the retained one-command/one-process GUI behavior, preserved
all rejected and partial evidence, restored MIRcat and T660 safe state, and
made SDK automation eligible with mandatory runtime prerequisites. TR-01
closed the retained identity and measurement-resource register without
hardware access or reacquisition. OM-01 is the exact next phase and requires
separate authorization. Codex resumes from
stable phase evidence rather than restarting the campaign or launching a
monolithic timing runner.
