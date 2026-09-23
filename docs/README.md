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
