# MC-01 uncertainty and ambiguity statement

The inhibited-control and three repeat decisions are categorical GUI/process
results. GUI observations and T660/HF2LI records are not synchronized to a
common instrument clock, so no cross-device absolute latency is claimed.

Raw DIO diagnostic `MC01-DIO-DIAGNOSTIC-002` captured 14,596 samples over
4.056576 s. DIO21 assertions were separated by 0.724319086 s. With an observed
sample interval of approximately 0.000277943 s, the conservative two-edge
discretization bound is 0.000555886 s. This interval is descriptive and is not
a universal permitted host delay.

DIO21/DB9 pin 2 appeared as two single-sample assertions rather than the
sustained high tuned-state described in manufacturer correspondence. It is
accepted only as correlated event evidence. The operational ambiguity is
resolved conservatively by requiring MIRcat state readback before each next
command. DIO20 is not used for point-process state, and DIO22 stayed low because
Wavelength Trigger Pulse Mode was not selected.

The `.mcfg` import/export test is specific to GUI `1.9.0.4` and firmware
`3.1.0`: serialized settings restored, while Process Trigger Mode did not.
Future use must explicitly set and read it back.

The GUI Emission/QCL indicators represented an enabled gate/process state.
Because the shutter was closed, Pulse Mode was External Trigger, and T660-2
sent no laser-trigger pulse, they are not evidence of optical pulses. MC-01
makes no optical power, detector, timing, or spectral-accuracy claim. The 1905
and 1934 cm^-1 values are qualification points, not promoted biological peak
centers.

