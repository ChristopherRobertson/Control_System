# MSW-01 — MIRcat sweep timing

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `MC-01, MD-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 14. MSW-01 — MIRcat sweep timing

Normal detector acquisition uses the
[default adapter/tee split paths](../../../../instrument/default_wiring_state.md):
sample to HF2LI Signal 1 In (+)/PicoScope CHA and reference to HF2LI Signal 2
In (+)/PicoScope CHB. Leave both receivers connected for the normal-state
records and distinguish any temporary diagnostic rewiring in its configuration.

Measure actual wavenumber-versus-time and event timing for every CH-00.1-retained
slow-scan, repeated rapid-scan, single-scan phase-delay, fixed-wavelength transition,
and single-pump rapid/log scan-burst mode. Cover both directions and the longest
retained windows, including start, acceleration, constant-speed, turnaround, stop,
retune, settling, and gap behavior. Requested speeds, marker intervals, pulse widths,
windows, and delays are planning candidates until frozen and observed; no numeric
candidate is a final setting merely because it appears in a planning document.

Mandatory closeout deliverables: repeated complete records per direction and retained
mode plus repeated point/process or scan-burst sequences per biological configuration;
raw MIRcat and HF2LI/DIO streams; actual wavenumber-versus-time traces; trigger/segment event
table, expected-versus-observed counts, measured spacing check, transition/gap
analysis; requested-versus-read-back settings; clock/reference conventions;
configuration-specific uncertainty; accepted/rejected index; and acceptance decision.

## `EXPERIMENTS.md` allocation and decision contract

This phase implements the scan-timing and actual-speed portions of `EXP-CAL-06`,
`EXP-CAL-07`, `EXP-CHAR-03`, `EXP-CHAR-04`, `EXP-OPT-06`, and `EXP-OPT-08`.
Acceptance requires bounded wavenumber/time residuals and complete marker
and transition accounting for each retained architecture; a mode is rejected or remains
provisional when its requested profile is not observed, turnaround/gaps are unsupported,
or timing uncertainty exceeds its frozen requirement. Changes to MIRcat mode or
firmware, scan profile/window/direction, event output, clock mapping, DIO receiver, or
analysis version trigger revalidation. AR-01, SP-02, IR-01, E2E-01, and both biological
campaigns consume these records. This phase does not establish absolute wavenumber
accuracy, optical time zero, detector response, or biological kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
