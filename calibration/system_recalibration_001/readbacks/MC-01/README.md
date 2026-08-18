# MC-01 — MIRcat GUI process-trigger qualification

Campaign: `system_recalibration_001`  
Phase run: `system_recalibration_001_MC-01_001`  
Status: **PASS — COMPLETE**

MC-01 qualified manufacturer-GUI ownership and the single CH-00-retained
Step-and-Measure point/process sequence: 1905 to 1934 cm^-1, one 29 cm^-1
transition, External Step process mode, and External Trigger pulse mode.

One inhibited control and three bounded repeats passed. Each accepted repeat
used one T660-1 CHC 10 ms active-low process command, recorded counter 0 to 1,
and produced exactly one GUI transition to 1934 cm^-1 followed by explicit
Stop Scan. Raw DIO evidence supports event correlation but not a persistent
ready level; future automation must use MIRcat state readback rather than a
fixed delay.

The manual shutter remained closed and T660-2 sent no laser-trigger pulse, so
no optical pulses or delivered beam occurred. Initial configuration was
restored, Process Trigger Mode was explicitly restored to Internal through the
SDK, MIRcat was powered down, GUI and SDK ownership were released, interlock
was disabled/inhibiting, default wiring was restored, and final T660 safe idle
passed.

Completed predecessor evidence is imported only through `calibration_links.csv`.
All raw, rejected, partial, preview, control, operator-confirmed, and
superseded evidence is retained. No PT-01 evidence was overwritten. TR-01 is
the exact next phase and requires separate authorization.

