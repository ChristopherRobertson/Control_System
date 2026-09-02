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
The normal Phase-Scan configuration additionally connects T660-1 CHD directly to
PicoScope EXT while MIRcat Sweep Active remains on HF2LI DIO21. Import the accepted
MS-02.1 electrical trigger-route result and MD-01 event semantics before using CHD
as the PicoScope record reference.

Measure actual wavenumber-versus-time and event timing for every CH-00.1-retained
slow-scan, repeated rapid-scan, single-scan phase-delay, fixed-wavelength transition,
and single-pump rapid/log scan-burst mode. Cover both directions and the longest
retained windows, including start, acceleration, constant-speed, turnaround, stop,
retune, settling, and gap behavior. Requested speeds, marker intervals, pulse widths,
windows, and delays are planning candidates until frozen and observed; no numeric
candidate is a final setting merely because it appears in a planning document.

For every retained Phase-Scan QCL, direction, window, speed, and start-condition
configuration, measure the falling-edge delay from T660-1 CHD to the rising edge of
MIRcat Sweep Active. In a safe, separately recorded temporary diagnostic topology,
keep CHD on PicoScope EXT and move Sweep Active from HF2LI DIO21 to PicoScope CHA;
the detector branch normally using CHA is disconnected only for this measurement.
Acquire at least 100 valid repeated captures per configuration with the returned
sample interval, trigger settings, both edge definitions, complete records, and all
rejected or anomalous captures retained. Restore Sweep Active to HF2LI DIO21 and the
sample detector to CHA before normal optical acquisition.

Report the median CHD-to-Sweep-Active delay, distribution, extrema, drift, direction/
history dependence, and a conservative uncertainty including repeatability,
PicoScope sampling, trigger and threshold sensitivity, imported MS-02.1 terms, and
any configuration effects. Reject or split a configuration when the relation is
multimodal, state-dependent without a usable model, or exceeds its predeclared
alignment budget. The Phase-Scan software exposes a configurable 0.25 us
maximum-uncertainty candidate; that value is not promoted by this plan and may be
tightened when the retained pulse period or reconstruction interval requires it.
Publish a stable human-readable qualification ID and machine-readable
`process_trigger_to_sweep_active_delay_us` and
`process_trigger_to_sweep_active_uncertainty_us` quantities for each accepted
configuration.

Mandatory closeout deliverables: repeated complete records per direction and retained
mode plus repeated point/process or scan-burst sequences per biological configuration;
raw MIRcat and HF2LI/DIO streams; actual wavenumber-versus-time traces; trigger/segment event
table, expected-versus-observed counts, measured spacing check, transition/gap
analysis; requested-versus-read-back settings; clock/reference conventions;
configuration-specific uncertainty; CHD-to-Sweep-Active capture set and qualification
record; restoration evidence; accepted/rejected index; and acceptance decision.

## `EXPERIMENTS.md` allocation and decision contract

This phase implements the scan-timing and actual-speed portions of `EXP-CAL-06`,
`EXP-CAL-07`, `EXP-CHAR-03`, `EXP-CHAR-04`, `EXP-OPT-06`, and `EXP-OPT-08`.
Acceptance requires bounded wavenumber/time residuals and complete marker
and transition accounting for each retained architecture; a mode is rejected or remains
provisional when its requested profile is not observed, turnaround/gaps are unsupported,
or timing uncertainty exceeds its frozen requirement. Changes to MIRcat mode or
firmware, scan profile/window/direction/start condition, CHC/CHD settings or cable,
PicoScope EXT settings, event output, clock mapping, DIO receiver, or analysis version
trigger revalidation. AR-01, SP-02, IR-01, E2E-01, and both biological
campaigns consume these records. This phase does not establish absolute wavenumber
accuracy, optical time zero, detector response, or biological kinetics.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
