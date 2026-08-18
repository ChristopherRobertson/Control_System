# MC-01 SDK and automation eligibility decision

Decision: **ELIGIBLE WITH MANDATORY RUNTIME PREREQUISITES**.

MC-01 established one-command/one-process GUI behavior across three bounded
repeats and separately qualified SDK API `2.4.1` set/readback control of the
Process Trigger Mode. Eligibility is limited to the retained 1905-to-1934
cm^-1 point/process sequence and requires all of the following:

1. Acquire exclusive SDK ownership; the manufacturer GUI must be closed.
2. Explicitly set and read back Process Trigger Mode for every run. Do not
   infer it from an imported `.mcfg`, because that field is not serialized.
3. Confirm the MIRcat waiting/tuned state before every process command. Do not
   use a fixed host delay or interpret DIO21 as a sustained ready level.
4. Stage only T660-1 CHC as negative, 10 ms, 50 ohm; start the REM timing
   engine; issue exactly one command; verify the counter changes 0 to 1; then
   stop the engine, disable CHC, and read back safe state.
5. After the terminal point, issue explicit Stop Scan and verify scan/emission
   gate inactive and no system fault.
6. Do not use T660-1 CHD or MIRcat DB9 pins 5, 6, or 8. Their standing default
   state remains disconnected/unused.

This decision qualifies process control only. It does not qualify optical
output, detector response, spectral accuracy, biological use, or any later
campaign phase.

