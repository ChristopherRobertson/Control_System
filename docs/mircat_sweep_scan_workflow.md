# MIRcat Segmented Sweep Workflow

Use [mircat_sweep_scan.yaml](../recipes/mircat_sweep_scan.yaml) for a continuous, unpumped spectral sweep with the installed wiring. It replaces neither the legacy rewired fast sweep nor the pump-probe recipes.

## Sequence

1. Before laser operation, record the empirically observed HF2LI bit numbers for DB9 pins 1, 2, and 3 in the recipe and set `experimentally_confirmed: true`. The application fails preflight otherwise; labels in older wiring documents are not accepted as evidence.
2. Apply the T660 recipe: T660-2 A and B run at 2 MHz; C and D are disabled. T660-1 is stopped and all of its outputs are disabled.
3. The control application initializes, arms, configures the MIRcat for external 2 MHz laser triggering, 5 cm^-1 wavelength-trigger markers with 500 us pulse width, and internal process-trigger mode. Both MIRcat settings are read back and verified before normal `StartSweepScan()`. DB9 pin 5 remains physically disconnected.
4. Apply the `myoglobin_co_spectrum` HF2LI preset and arm the DAQ before initiating the sweep. The preset configures LabOne Demodulator 3 (API index 2) at 5 kSa/s as the timing/DIO monitor; LabOne Demodulators 1 and 4 (API indices 0 and 3) remain the Sample and Reference detector channels. No manual LabOne settings are required.
5. Record Sample, Reference, and the complete DIO word continuously across the scan and its inter-channel gaps.
6. Split the record at DB9 pin 2 Sweep Active high intervals. Discard every detector sample in a low interval.
7. Pair rising DB9 pin 3 pulses with the ordered configured targets and interpolate time to wavenumber independently in each high interval. Every retained interval must contain at least two anchors; an edge-count mismatch or under-constrained interval aborts export rather than synthesizing an axis from host time.
8. Concatenate calibrated intervals in acquisition order. The Plotter holds exactly the three requested columns until the operator exports them.

The completed scan is retained in memory in the application's **Plotter** tab; no scan file is written automatically. Inspect both detector traces, select an output folder and filename, then press **Export** to write a CSV with exactly `Wavenumber (cm^-1)`, `Sample (V)`, and `Reference (V)` columns.

MIRcat BNC TRIG OUT is laser-pulse timing, not a sweep-valid gate, and is not used to construct the wavelength axis. T660-2 A remains the external lock-in reference.

## Required LabOne configuration

LabOne Demodulator 1 / API 0 records Sample, Demodulator 4 / API 3 records Reference, and Demodulator 3 / API 2 records the complete DIO word.

## External Process Trigger validation

Test this first in the MIRcat GUI with T660-1 CHC idling high and producing an approximately 10 ms low pulse. Record whether the first pulse starts the first channel and how many subsequent pulses are required. Automated external-process-trigger mode remains blocked in this workflow until that observed channel/pulse sequence is implemented. Do not drive DB9 pin 5, 6, or 8.
