# Operating documentation

All acquisitions are **functionality tests**, with no runtime calibration or scientific claims until explicit operator release. Current priority is end-to-end app workflows. See [result status](result_status.md). MUX work is deferred; current experiments use direct detector and marker connections.

The [repository README](../README.md) describes installation, storage configuration,
software boundaries and instrument ownership. The [module API](../software/control_app/measurement_host/README.md)
describes extensible single/dual measurement pages.

- [Slow Scan](operating_procedures/steady_state_slow_scan.md)
- [Fixed Wavenumber](operating_procedures/fixed_wavenumber_kinetics.md)
- [Nanosecond Stroboscopy](operating_procedures/nanosecond_stroboscopy.md)
- [Microsecond Stroboscopy](operating_procedures/microsecond_stroboscopy.md)
- [Rapid Scan Phase Delay](operating_procedures/repeated_rapid_scan.md)
- [Phase Scan](operating_procedures/phase_scan_tab.md)
- [Dual-detector Phase Scan](operating_procedures/dual_detector_phase_scan_tab.md)
- [Optional Single Scan Phase Delay module](operating_procedures/single_pump_scan_burst.md)
- [Device controls](operating_procedures/ui_hardware_control_reference.md)
- [MIRcat detector alignment](operating_procedures/mircat_detector_alignment_workflow.md)
- [Segmented sweep](operating_procedures/mircat_sweep_scan_workflow.md)

## MIRcat repetition rate across experiment tabs

Each single/dual tab owns its MIRcat **Repetition Rate** request. **Auto is
2 MHz**, independent of the T660 setting left by another experiment. For
externally triggered continuous-probe experiments, T660 uses that rate and
MIRcat's internal acceptance rate is 5% higher (2 MHz → 2.1 MHz). Existing optical
width, duty, trigger-acceptance, timing-grid and connected-device limits still
apply; an invalid combination is rejected rather than silently reducing the rate.
Internal optical duty uses the **internal** rate: `rate_hz * width_ns / 1e9 <= 0.30`.
Automatically selected widths keep the 142 ns default where valid and shorten to
whole nanoseconds rounded down when a higher internal rate requires it. Thus
2.1 MHz uses 142 ns (29.82%); 3.15 MHz uses 95 ns (29.925%). Explicit widths in
Slow Scan and Single Pump Scan Burst are validated rather than silently clipped.
Stricter device limits and actual SDK readbacks are still checked before emission.
Prior device settings are preserved for restoration, not selected as Auto values.

Slow Scan uses internally generated optical pulses at the selected rate and
sets its electrical reference/frame clock from the same field; its external
laser-trigger output remains OFF. CW mode uses the field only for electrical
timing. Nanosecond Stroboscopy preserves its separated probe-event schedule;
its field sets the internal MIRcat rate (Auto: 2 MHz), which must exceed the
actual sparse trigger cadence. These are operational settings for functionality
tests, not optical timing qualification.

Scientific output, including readbacks and analysis, uses the central research-root
setting. Browse selects a subdirectory of that root for the current page. Native
records remain immutable inputs; derived results identify their source. A write
failure must be resolved before the operation can claim successful preservation.

Use [Phase Scan preview settings](../instrument/phase_scan_preview.md) to interpret
disconnected plans and [optical pump constraints](../instrument/optical_pump_constraints.md)
for current OPO limitations. Nominal command delays do not establish optical timing.

Read [default wiring](../instrument/default_wiring_state.md) and the applicable
operating procedure before an authorized hardware session. Missing qualification,
unsafe device state, unresolved ownership and failed restoration are not resolved
by creating files or changing directories.
