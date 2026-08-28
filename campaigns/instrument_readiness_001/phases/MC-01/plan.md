# MC-01 — MIRcat GUI process-trigger qualification

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `complete`
Required dependencies: `PT-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 7. MC-01 — MIRcat GUI process-trigger qualification — COMPLETE / PASS

Under manufacturer-GUI ownership, qualify only the discrete point/process
sequence selected in CH-00 for the biological fixed-wavenumber workflow. Verify
external laser/process-trigger state transitions, one-command/one-process
behavior, the first and subsequent bounded repeats, and the permitted delay
after Sweep Active falls. Do not exercise unused multispectral/channel modes.
SDK use before GUI qualification was prohibited; bounded SDK control
qualification was performed only after the GUI repeats passed.

Mandatory closeout deliverables:

- GUI/version/firmware provenance, selected operating modes, screenshots or
  exported logs, T660 readbacks, DIO evidence, and a timestamped action ledger.
- Expected-versus-observed state/pulse table for one inhibited control and
  three bounded repeats of the retained point/process sequence, including
  exceptions and failure behavior.
- Ownership release, safe shutdown, restoration record, uncertainty/ambiguity
  statement, and explicit SDK-automation eligibility decision.

The inhibited control and three bounded repeats passed. Each accepted repeat
used one started-engine 10 ms active-low T660-1 CHC command and produced one
1905-to-1934 cm^-1 transition followed by explicit Stop Scan. Raw DIO evidence
supports event correlation but not a persistent ready level; automation must
use MIRcat waiting/tuned state readback rather than a fixed delay. SDK control
qualification set/read External process mode and restored/read Internal mode.
Initial configuration import, power-down, GUI/SDK ownership release, interlock
inhibition, default-wiring restoration, and final T660 safe idle all passed.

The shutter remained closed and T660-2 sent no external laser-trigger pulse,
so no optical pulses occurred. Authorization `MC01-AUTH-002` permitted the
bounded continuation but did not authorize any later phase. See
`final_report.md` and `continuation_authorization.md` in this phase directory.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
