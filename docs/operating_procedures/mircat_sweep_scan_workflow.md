# MIRcat Segmented Sweep Workflow

The segmented-sweep implementation uses an engineering candidate recipe that is
currently non-executable. Execution requires an explicitly approved operating
configuration ID and `APPROVED_FOR_EXECUTION` in `operating_approval`. This setting
does not bypass physical readiness, instrument ownership or mode-specific checks.
All output must be under the configured research root.

## Detector wiring

The [default wiring](../../instrument/default_wiring_state.md) uses one
female-to-female BNC adapter -> male-to-two-female BNC tee per detector signal.
Sample feeds HF2LI Signal 1 In (+) and PicoScope CHA; reference feeds HF2LI
Signal 2 In (+) and PicoScope CHB. Both receivers stay connected throughout a
normal sweep, including when only HF2LI streams are recorded. The MUX remains
bypassed. Qualification and settings must cover this installed receiver load;
temporary timing/IRF wiring is a separate configuration restored afterward.

## Sequence

1. Complete the approved phase gate. The application fails before opening
   hardware while the recipe status remains `CANDIDATE_NOT_APPROVED_FOR_EXECUTION`.
2. Verify the accepted HF2LI bit numbers for DB9 pins 1, 2, and 3 by measured mapping; physical connector labels alone do not establish captured DIO bit indices.
3. Apply the T660 recipe: T660-1 A/B supply the qualified probe/reference rate. Its C output clocks T660-2 only for an explicitly configured process-frame sequence. T660-2 A/B and both D outputs remain disabled for an unpumped sweep; C issues only the qualified process events.
4. Configure the MIRcat for external 2 MHz laser triggering, 5 cm^-1 wavelength-trigger markers with 500 us pulse width, and the process-trigger mode approved for the installed configuration. Read back every setting. DB9 pin 5 remains physically disconnected.
   The standing default-wiring exclusions are defined once in
   `instrument/default_wiring_state.md` and are not recurring operator questions
   unless the operator reports a change.
5. Apply the accepted detector configuration that replaces `sweep_qualification_candidate`. That candidate is for qualification only and is not a scientific-validation or biological preset.
6. Record Sample, Reference, and the complete DIO word continuously across the scan and its inter-channel gaps.
7. Split the record at DB9 pin 2 Sweep Active high intervals. Exclude every detector sample in a low interval while retaining it in the native raw stream.
8. Pair rising DB9 pin 3 pulses with the ordered configured targets and interpolate time to wavenumber independently in each high interval. Every retained interval must contain at least two anchors; an edge-count mismatch or under-constrained interval aborts export rather than synthesizing an axis from host time.
9. Concatenate marker-reconstructed test intervals in acquisition order and retain the native acquisition and analysis records.

Plotter exports are convenience products only. Native Sample, Reference, and
complete DIO streams, run metadata, settings/readbacks and relative native-file references are required to interpret functionality-test outputs. These outputs support no scientific claims.

MIRcat BNC TRIG OUT is laser-pulse timing, not a sweep-valid gate, and is not used to construct the wavelength axis. T660-1 A remains the external lock-in reference.

## Required LabOne configuration

LabOne Demodulator 1 / API 0 records Sample, Demodulator 4 / API 3 records Reference, and Demodulator 3 / API 2 records the complete DIO word.

## External Process Trigger validation

Use accepted GUI process-trigger state semantics for the applicable mode. Installed
T660-2 CHC receiver/frame behavior requires qualification with CHC idling high and
the selected active-low pulse. Reconcile the first channel and subsequent process
commands with observed Sweep Active. Automated external-process-trigger mode
remains blocked until that observed sequence is implemented. Do not drive reserved
DB9 pin 5 (Laser Output On/Off), unused pin 6, or unused pin 8. See
`instrument/default_wiring_state.md` for standing connections.
