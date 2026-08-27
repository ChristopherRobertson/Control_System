# Complete system recalibration run

Prospective order is defined only by `../../campaigns/phase_registry.yaml`.
This directory retains detailed procedures and completed evidence. Planned HF-01.1
is canonical under `../../campaigns/instrument_readiness_001/phases/HF-01.1/`.

Campaign: `system_recalibration_001`

Status: **WM-01 OPEN / DEFERRED PENDING REPLACEMENT SPECTROMETER; 540 NM / ATT-01 CHAIN DEFERRED; INDEPENDENT PHASES MAY PROCEED WITH SEPARATE AUTHORIZATION; PROMOTION BLOCKED**

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

The 2026-08-25 dependency amendment permits work that does not consume the
deferred wavelength/540 nm chain to proceed out of numerical phase order. This
is not a WM-01 bypass or pass. `HF-01`, `MD-01`, `MSW-01`, `HF-02`, `DET-01`,
and `SP-01` may be separately authorized and completed now. Any phase that
consumes WM-01, ATT-01, independent 540 nm identity, or the retained OPO-540
path remains deferred. `RPT-01` may receive provisional indexes but may not
close, and `PROM-01` may not begin, until the deferred chain is completed.

The active campaign is confined to
`C:\Users\Chris\Documents\GitHub\Control_System\calibration\system_recalibration_001`.
The former `Control_System_timing` worktree has been merged into `main` and removed.
References to that worktree in dated provenance snapshots describe the historical
capture environment only and are not active paths.

## Codex-led execution model

The canonical phase plans and `campaigns/instrument_readiness_001/shared/electrical_timing_method.md` define what is
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

`plans/campaign_sequence.md` preserves every completed phase as an immutable
dependency and contains the retained identity/reference basis, optical-
metrology, wavelength-metrology, attenuation/transfer, detector-latency,
reporting, and retention work needed
before quantitative pump/probe characterization. ATT-01 and DET-04 explicitly
measure the non-50/50 sample/reference optical balance, separate it from the
two detector/electronics responses, and produce the normalization correction.
The permanent OPO path contains the USB/API-controlled iris. ATT-01 qualifies
device control and readback, scientifically selects and
locks the far-field mount, optimizes the 540 nm aperture diameter against halo
rejection and core clipping, and produces the configuration/transfer bundle
used by every later OPO-540 phase and both the HRP-C–CO and MbCO experiments.
ATT-01 first performs the preliminary pre-iris FIRE-to-Q-SWITCH delay search;
PB-02 performs the final narrow search through the locked iris and freezes the
experiment operating delay. Supplemental direct-355 thesis characterization
is performed after characterization promotion and is outside every OPO-540,
completion, promotion, and biological-entry gate.
WM-01 provides the visible/near-IR wavelength working reference. The installed
Coherent WaveMaster candidate passed electronic checks but failed optical
qualification; a replacement spectrometer is pending. WM-01 must still close
with identity, communications, response states, settings, repeatability,
uncertainty, and validity before ATT-01 uses it.
HRP is executed first and MbCO inherits the unchanged promoted configuration.
The iris is not a safety shutter or finite-event limiter.
FE-01 qualifies finite admission and independent observation of rare post-iris
540 nm pump events without biological samples; it does not determine
biological dose, recovery, or photolysis. The remaining grids are limited to
the two spectral regions, two acquisition topologies, three experiment-specific
HF2LI configurations (sweep, HRP-C-CO fixed point, and MbCO fixed point), and source path in the
verified requirement briefs.
The non-duplication mapping is in `analysis/expansion_gap_map.md`.

The definitive P0 decision record is
`manifests/p0_requirement_decisions.md`. All 21 decisions were resolved on
2026-08-15. Discarded certificate and accessory research cannot reappear as a
phase gate without a new user-approved claim requirement.
The dated P0 blocker table remains historical evidence rather than a second
active requirements list.

Pump/probe beam performance is measured separately in
`evidence/characterization/system_characterization_001/`. That campaign imports
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
| WM-01 | Qualify WaveMaster identity, cable/adapter, RS-232 behavior, measurement states/settings, 540 nm repeatability, uncertainty, and working-reference validity. |
| ATT-01 | Perform the preliminary pre-iris 540 nm FIRE-to-Q-SWITCH delay search; qualify the electronic iris USB/API control; select and lock its far-field mount; optimize the diameter against halo rejection, beam walk, and core clipping; then measure the retained optical transfers. |
| HF-01 | With all lasers inhibited, use three monitored PicoScope-AWG anchor settings to validate the HF2LI response model, evaluate all supported settings computationally, and confirm only the selected sweep, HRP-C-CO, and MbCO configurations plus one ambiguity challenger when required. |
| MC-01 onward | Follow the existing phase procedure interactively using focused utilities and the same stable phase-record pattern. |

## Current phase boundary

The campaign-wide phrase `default wiring restored` follows
`instrument/default_wiring_state.md`: T660-1 channel D and MIRcat DB9 pin 5 are
disconnected, and MIRcat DB9 pins 6 and 8 are unused/unwired. These standing
conditions are not repeatedly reconfirmed unless the operator reports a
change.

MS-01, MS-02, T2-01, T1-01, PT-01, CH-00, MC-01, TR-01, and OM-01 are complete.
MC-01 qualified the retained one-command/one-process GUI behavior, preserved
all rejected and partial evidence, restored MIRcat and T660 safe state, and
made SDK automation eligible with mandatory runtime prerequisites. TR-01
closed the retained identity and measurement-resource register without
hardware access or reacquisition. OM-01 qualified the Newport 1918-R / 919P
average-power chain as a bounded campaign-local working reference without
canonical promotion. The 2026-08-20 query-only WaveMaster connection intake
recorded the electronic identity, firmware, COM port, USB-adapter identities,
installed driver, and native query responses without changing settings. The
operator confirms that the connected instrument works safely. All WM-01 entry
fields are resolved and its preflight is ready, but that does not replace
separate phase authorization. WM-01 began on 2026-08-21 but remains open and
deferred pending a replacement spectrometer. ATT-01 and every dependent 540 nm
phase remain deferred until WM-01 passes. Dependency-independent phases listed
above may proceed with their own authorization. OM-01 is not repeated: its
mixed-output reading remains bounded
pre-iris evidence, while post-iris power and transfer belong to ATT-01 and
downstream characterization. Codex resumes from
stable phase evidence rather than restarting the campaign or launching a
monolithic timing runner.
