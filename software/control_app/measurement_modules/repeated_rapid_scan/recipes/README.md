# Repeated rapid-scan timing resources

`timing_contract.json` records the installed channel topology and compiler
invariants. It contains no accepted biological operating values. The default
settings are **EXAMPLE ONLY** hardware-free planning inputs; neither copying a
recipe nor saving a plan promotes evidence or authorizes a pump.

An applicable bundle is loaded through the host's promoted-bundle loader. Its
`manifest.yaml` must contain `status: PROMOTED`, `bundle_id`, and the experiment
section below. The root promoted registry must also authorize it. Current
repository commissioning status remains whatever that registry reports.

```yaml
repeated_rapid_scan:
  calibration:
    calibration_ids: [explicit-stable-record-identities]
    condition_id: accepted-condition-identity
    trajectory_id: accepted-trajectory-record
    electrical_timing_id: accepted-clock-and-latency-record
    response_id: measured-native-scan-filter-response-record
    detector_id: accepted-detector-linearity-record
    topology_id: accepted-installed-tee-receiver-record
    reset_equivalence_id: accepted-condition-reset-record
    optical_time_zero_id: '' # optional: absent means electrical-sync time basis
    applicable_settings: {} # exact supported scan/probe/pump/filter/rate fields
    operating_values: {} # explicit supported editable settings; never a sample ID
  device_configuration: {} # module adapter's maintained-device configuration
```

The `CalibrationEvidence` and `HardwareCapabilities` dataclasses document all
accepted keys. Connected capability/readback records are separate from promoted
calibration: record actual sample/reference rates, measured scan period,
aggregate timing-stream throughput and the capability identity under ownership.
No hash-matching acceptance gates are used.

Every movie is a finite complete table with a measured period, a selected pump
phase and all channel states. Each scan frame has a scan index; the additional
final `terminal_inhibit` frame has `scan_index: null` and all outputs disabled.
The physical frame count includes this terminal, the expected spectral scan
count does not, and elapsed duration includes its period. Qualification trains
have their own terminal. External process pulses
must fit their frame with the maintained uploader's 1 microsecond margin. The
compiler refuses unsupported tables and unrequested timing quantization. It does
not adjust sample cadence to the source maximum. A movie reaching its duration
limit can be retained as incomplete recovery; it never authorizes the next pump.

The memory estimate includes detector native values and timestamps, timing words,
quality/uncertainty inputs and processing arrays. Dual detectors increase
aggregate data rate, never the elapsed duration of simultaneous recording.
