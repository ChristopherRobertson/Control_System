# MC-01 final report

Campaign: `system_recalibration_001`  
Phase run: `system_recalibration_001_MC-01_001`  
Decision: **PASS — COMPLETE**

MC-01 qualified manufacturer-GUI ownership and the single CH-00-retained
discrete point/process sequence. No later phase was started.

## Provenance and retained sequence

The MIRcat was identified as model `MIRcat-QT-Z-2100`, serial `10524`, with
GUI/software `1.9.0.4`, firmware `3.1.0`, and SDK API `2.4.1`. The qualified
runtime configuration was QCL1, Pulsed, 2 MHz, 150 ns, 1000 mA, 19 C;
External Step process mode; External Trigger pulse mode; and Step and Measure
from 1905 to 1934 cm^-1 in one 29 cm^-1 transition, one scan, Infinite off,
and Keep Laser On Between Steps off. GUI screenshots, native configuration
exports, T660 readbacks, DIO captures, and the timestamped action ledger are
retained by stable identifiers in the phase indexes.

The initial `.mcfg` export was captured before changes. Candidate laser
settings were explicitly saved before export. Import testing established that
serialized settings restore, including Wavelength Trigger Start/Stop at
2049.18 cm^-1, but Process Trigger Mode is not serialized. It must be set and
read back explicitly for every run.

## Qualification results

The inhibited control passed: with the interlock inhibiting and the MIRcat
unarmed, Start Scan returned `Please ARM the laser prior to trying this
operation.` Attempting to arm returned the interlock/keyswitch requirement. No
process command or scan occurred.

Three bounded accepted repeats passed. In each, exactly one started-engine
T660-1 CHC command (negative, 10 ms, 50 ohm) increased the command counter from
0 to 1 and advanced the GUI exactly once from 1905 to 1934 cm^-1. The terminal
point waited for explicit Stop Scan. Stop Scan ended the GUI emission-gate
state, returned QCL and current wavenumber to N/A, left the laser armed until
the operator disarmed it, and produced no fault. The first engine-stopped
attempt and two failed HF2 export attempts remain preserved as rejected or
partial evidence; they were not substituted for accepted repeats.

Raw HF2LI DIO diagnostic `MC01-DIO-DIAGNOSTIC-002` retained 14,596 samples
over 4.056576 s. DIO21/DB9 pin 2 produced two correlated one-sample assertions
separated by 0.724319086 s; DIO22/DB9 pin 3 stayed low, as expected because
Wavelength Trigger Pulse Mode was not selected. DIO21 did not behave as a
sustained tuned-state level. Consequently, no universal host delay after a
nominal Sweep Active fall is promoted. The permitted control rule is
state-based: issue no subsequent process command until the MIRcat reports the
next waiting/tuned state. The observed interval is descriptive only.

The manual shutter remained closed, Pulse Mode was External Trigger, T660-2
sent no laser-trigger pulse, and the HF2LI acquired DIO only. The green GUI
Emission/QCL indicators therefore document the enabled process/emission-gate
state, not optical pulses. No optical pulse, delivered beam, detector response,
power, or spectral-performance claim is made.

## Exception behavior and restoration

Sending `TRIG:EXEC` while the T660 engine remained stopped produced no counter
increment and no MIRcat transition; that acquisition was correctly rejected
as an invalid command setup, not a MIRcat failure. GUI interlock and unarmed
refusals were deterministic. A terminal process does not auto-close and
requires explicit Stop Scan.

SDK qualification under exclusive ownership passed without any SDK arm,
emission, tune, or scan command. The SDK set/read External process mode and
then restored/read Internal process mode. Initial configuration import then
powered down the MIRcat and closed the GUI. Ownership was released, SDK
deinitialized, the shutter remained closed, the interlock was disabled and
inhibiting, and default wiring was restored. Final T660 safe idle passed with
zero mismatches.

## Decisions

- MC-01 closeout: **PASS — COMPLETE**.
- SDK automation: **ELIGIBLE WITH MANDATORY RUNTIME PREREQUISITES**, as defined
  in `sdk_automation_decision.md`.
- Canonical calibration promotion: not performed.
- Exact next phase: **TR-01**, requiring separate authorization.

