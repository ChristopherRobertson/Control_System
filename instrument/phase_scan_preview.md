# Phase Scan preview settings

These built-in settings let the single- and dual-detector Phase Scan tabs construct
plans while disconnected. They are an unverified preview (`verified: false`), not a
calibration or permission to operate. They require no experimental data files.
Connected device checks supply supported choices and readbacks for acquisition.

## Single-detector profile

The profile is defined by `HF2Capabilities` in
[regular_phase_scan.py](../software/control_app/measurement_modules/phase_scan/regular_phase_scan.py).

| Parameter | Preview value |
| --- | --- |
| HF2LI device identity | `dev18500` |
| Sample demodulator / input | API index 0 / Signal 1 In (+) |
| Filter order | 4 |
| Time constant | 4.999538607626059e-5 s |
| Detector sample rate | 28782.894736842107 Sa/s |
| Timing/DIO demodulator / rate | API index 2 / 230263.15789473685 Sa/s |
| Enabled streams | 0, 2 |
| QCL / indicated tuning range | 1 / 1638.8068850219217–2077.2745597378685 cm⁻¹ |
| Timing-table capacity | 8192 frames |
| Retained-data memory advisory | 536870912 bytes |

## Dual-detector profile

[dual_detector_phase_scan.py](../software/control_app/measurement_modules/phase_scan/dual_detector_phase_scan.py)
uses the same numerical preview for each detector. Sample uses demodulator 0 and
input 0; reference uses demodulator 3 and input 1. Demodulator 2 carries timing/DIO,
so enabled streams are 0, 2, 3. Detector roles follow the
[wiring map](wiring_map.yaml) and [detector connections](default_wiring_state.md#detector-connections).
Each detector's connected capabilities and actual readbacks are checked separately.

## Interpretation

The default Phase Scan FIRE-to-Q-switch command interval is 250 µs. The Nd:YAG
alignment recipe uses a separate nominal 179830 ns interval. Neither is a measured
sample-plane optical correction. Do not substitute one workflow's interval for
another. Filter group delay is estimated as order × time constant; effective
response estimates also include sampling. These models do not establish optical
arrival time, detector latency, or an instrument response measurement.

Scientific corrections must be explicitly supplied with applicable identities,
units and validity conditions. No runtime bundle is selected by this preview.
