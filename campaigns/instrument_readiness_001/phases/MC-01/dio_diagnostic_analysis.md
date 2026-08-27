# MC-01 raw DIO diagnostic analysis

Acquisition: `MC01-DIO-DIAGNOSTIC-002`  
Source: `raw_dio_process_diagnostic_raw.csv`  
HF2LI: `dev18500`, clockbase `210000000 Hz`  
T660 command: one CHC active-low 10 ms command, counter 0 to 1

The uninterpolated raw subscription contains 14,596 samples across
4.056576 s. The GUI independently confirmed that the same command advanced
exactly once from 1905.0 to 1934.0 cm-1.

Observed mapped bits:

- DIO21 / DB9 pin 2 produced two single-sample asserted intervals. Rising
  edges occurred at capture offsets 3.193841371 s and 3.918160457 s.
- Separation between those rising edges was 0.724319086 s.
- Each observed assertion occupied one sample interval, approximately
  0.000277943 s at the acquired sample cadence.
- DIO22 / DB9 pin 3 remained low with no edges, consistent with Wavelength
  Trigger Pulse Mode being unselected.
- DIO20 toggled continuously and is not used to infer point-process state.

The pin-2 waveform does not match a sustained high tuned-state level described
by manufacturer correspondence. It is accepted as correlated event evidence,
not as a reliable persistent level. A fixed host delay after a nominal
Sweep-Active fall is therefore not promoted. The operational rule for later
automation is state-based: do not issue another process command until the
MIRcat reports the next waiting/tuned state; the observed transition interval
of 0.724319086 s is descriptive, not a universal bound.

Uncertainty is at least one sample interval on each detected edge; edge-to-edge
separation has a conservative two-sample discretization bound of
0.000555886 s. Only one raw-DIO diagnostic was acquired because the three
required GUI repeats had already completed and two earlier DIO payloads were
preserved as rejected export attempts.
