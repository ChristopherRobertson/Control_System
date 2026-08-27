# HF-01 supported-configuration analysis

Analysis ID: `HF01-ANALYSIS-SUPPORTED-CONFIGURATIONS-001`  
Status: **SELECTED WITH MBCO LIMITATION**

The candidate table covers all 11 installed ranges, eight input modes, three readout modes, eight filter orders, 21 dual-channel rates, and the complete writable time-constant interval. The continuous interval is retained analytically rather than replaced by an arbitrary finite time-constant grid.

## Selections

| ID | Order | Time constant readback | Rate | Key envelope |
|---|---:|---:|---:|---|
| `HF01-SWEEP-SELECTED-001` | 4 | 0.00100188870788 s | 899.465460526 Sa/s | 0.1603 cm-1 kernel mean shift and 0.08015 cm-1 kernel sigma at 40 cm-1/s; AR-01 retains final feature-tolerance authority. |
| `HF01-HRP-SELECTED-001` | 4 | 0.00100188870788 s | 899.465460526 Sa/s | 0.01002 s 99% memory, 89.9 samples per provisional 100 ms interval. |
| `HF01-MBCO-SELECTED-001` | 1 | 5.60001746759e-06 s | 230263.157895 Sa/s | Boundary setting only: 0.23 sample per 1 us and 82.421% attenuation at the 1 us characteristic scale; mandatory 1 us preservation fails. |

The sweep and HRP IDs are explicit numeric aliases but retain separate applicability envelopes. No challenger is invoked. The 1 V nominal, DC, high-impedance, single-ended input mode is selected because it is the smallest installed range above twice the prior 0.4651 V detector maximum and matches the established one-coax detector topology.

## Limits

Sweep feature width and final distortion tolerances, HRP's fastest accepted early feature and precision target, and installed-detector noise remain downstream measurements. The table therefore reports their Pareto coefficients and validity envelopes rather than inventing thresholds. MbCO is a hard negative result: with two analog streams the maximum rate supplies only 0.230 sample per mandatory 1 us feature, so no HF2LI filter configuration can preserve that claim.
