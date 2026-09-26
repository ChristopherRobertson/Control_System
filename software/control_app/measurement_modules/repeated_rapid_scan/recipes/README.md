# Repeated rapid-scan timing resources

`timing_contract.json` describes the installed channel topology and finite-table
compiler invariants. It is a technical schedule contract, not a biological
operating prescription or an approval workflow.

Routine acquisition resolves editable settings against installed capabilities
and current readbacks. Optional instrument-calibration and sample-selection
records contribute axis, timing or uncertainty provenance. Neither promotion,
review flags, descriptive temperature records nor preparation acknowledgements
are prerequisites for recording native/relative data.

Only MIRcat **QCL1** is addressed. **Repetition rate** sets the emitted T660
external-trigger cadence (`probe_frequency_hz`) for MIRcat mode 2. Auto selects
2 MHz independently of prior device readbacks. Internal MIRcat acceptance is
set 5% higher (2.1 MHz at 2 MHz), with an automatic optical width capped at 142 ns and shortened as needed for 30% internal duty.
The visible pulse-width control sets the T660 TTL width independently. Both
external cadence and internal MIRcat rate must satisfy
`rate_hz * actual_mircat_width_ns * 1e-9 <= 0.30`, together with stricter installed
vendor limits. Device readbacks, the applied pair and restoration of the original
parameters remain in the run. Invalid combinations are rejected without reducing
the requested rate.
Saved UI settings migrate removed engineering controls into
`historical_ui_settings`; only currently visible overrides and analysis windows
are reused. Native run loading does not perform this settings migration.

Each pumped movie has one Fire/Q-switch pair, every declared pre-pump scan,
the pump-crossing scan, all post-pump scans and a final all-disabled terminal.
The terminal has no scan index or spectral trigger but counts against physical
frame capacity and elapsed duration. No separate qualification train or manual
approval is inserted before it. The unpumped baseline needed for relative
normalization is reused when compatible or acquired automatically.

T660 timing uses the maintained pending-field uploader with STORE acknowledgements,
progress and cancellation. Process pulses fit their selected frames with the
uploader margin. Hardware limits and quantization remain explicit. A complete
movie is never silently split, slowed or cycled through a circular buffer.
Missing observations remain missing and no pump event is automatically retried.

Physical pump-blocked/dark controls require actual supported hardware or separately
recorded control data; the standard unattended movie sequence does not invent a
shutter or infer that an acknowledgement created the physical condition. Native
recovery evidence still controls whether a subsequent equivalent pump is possible.

Memory estimates include native detector/timing data, quality/uncertainty inputs
and derived arrays. Dual channels increase throughput and memory, not the elapsed
duration of simultaneous recording. All device access and restoration stay under
host instrument ownership, through preservation of complete or partial records.
