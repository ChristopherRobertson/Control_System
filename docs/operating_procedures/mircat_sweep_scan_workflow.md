# MIRcat Segmented Sweep Workflow

The generic segmented-sweep implementation is retained for future MD-01 and
MSW-01 qualification. Its current recipe is a non-executable candidate. It may
run only after the campaign gate names an approved phase, phase-run ID, and the
stable phase directory under `campaigns/instrument_readiness_001/phases/`.

The manufacturer correspondence defining the DB9 signals and required
GUI-first process-trigger qualification is preserved in
[daylight_db9_process_trigger_correspondence.md](../../references/manuals/MIRcat/daylight_db9_process_trigger_correspondence.md).

## Sequence

1. Complete the approved phase gate. The application fails before opening
   hardware while the recipe status remains `CANDIDATE_NOT_APPROVED_FOR_EXECUTION`.
2. Verify the accepted HF2LI bit numbers for DB9 pins 1, 2, and 3 through MD-01; labels in older wiring documents are not accepted as campaign evidence.
3. Apply the T660 recipe: T660-2 A and B run at 2 MHz; C and D are disabled. T660-1 is stopped and all of its outputs are disabled.
4. Configure the MIRcat for external 2 MHz laser triggering, 5 cm^-1 wavelength-trigger markers with 500 us pulse width, and the process-trigger mode approved by MC-01. Read back every setting. DB9 pin 5 remains physically disconnected.
   The standing default-wiring exclusions are defined once in
   `instrument/default_wiring_state.md` and are not recurring operator questions
   unless the operator reports a change.
5. Apply the HF-01-accepted configuration that replaces `campaign_sweep_qualification_candidate`. That candidate is for qualification only and is not an SV-02 or biological preset.
6. Record Sample, Reference, and the complete DIO word continuously across the scan and its inter-channel gaps.
7. Split the record at DB9 pin 2 Sweep Active high intervals. Exclude every detector sample in a low interval while retaining it in the native raw stream.
8. Pair rising DB9 pin 3 pulses with the ordered configured targets and interpolate time to wavenumber independently in each high interval. Every retained interval must contain at least two anchors; an edge-count mismatch or under-constrained interval aborts export rather than synthesizing an axis from host time.
9. Concatenate calibrated intervals in acquisition order and retain the required campaign artifacts.

Plotter exports are convenience products only. Native Sample, Reference, and
complete-DIO streams plus the phase manifest and artifact indexes are required
for campaign evidence.

MIRcat BNC TRIG OUT is laser-pulse timing, not a sweep-valid gate, and is not used to construct the wavelength axis. T660-2 A remains the external lock-in reference.

## Required LabOne configuration

LabOne Demodulator 1 / API 0 records Sample, Demodulator 4 / API 3 records Reference, and Demodulator 3 / API 2 records the complete DIO word.

## External Process Trigger validation

Test this first in the MIRcat GUI with T660-1 CHC idling high and producing an approximately 10 ms low pulse. Record whether the first pulse starts the first channel and how many subsequent pulses are required. Automated external-process-trigger mode remains blocked in this workflow until that observed channel/pulse sequence is implemented. Do not drive reserved DB9 pin 5 (Laser Output On/Off), unused pin 6, or unused pin 8. Their standing state is imported from `instrument/default_wiring_state.md`, not repeatedly re-asked.
