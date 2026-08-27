# HF-01 three-anchor paired-demodulator validation design

Declaration version: `HF01-VALIDATION-DESIGN-v3`.

These are sparse instrument-model anchors, not experiment presets. Demodulator
0 is the filter under test; demodulator 1 is the minimum-time-constant reference
on the same input and HF2LI clock domain. Installed readbacks are authoritative.

| Anchor ID | Test order | Requested test time constant | Test offsets | Paired output rate | Role |
|---|---:|---:|---|---:|---|
| `HF01-ANCHOR-FAST-V3-001` | 1 | 4 us | +3,980; +39,800; +199,000 Hz | maximum supported for two active demodulators | Short-time and high-bandwidth anchor |
| `HF01-ANCHOR-INTERMEDIATE-V3-001` | 4 | 1 ms | +6.92; +69.2; +346; -69.2 Hz | approximately 2 kSa/s | Mid-bandwidth and positive/negative phase anchor |
| `HF01-ANCHOR-SLOW-V3-001` | 8 | 100 ms request; installed quantized readback retained | +0.0479; +0.479; +2.395 Hz | approximately 100 Sa/s | Long-time high-order and settling anchor |

Each record contains a connected-zero baseline, three rising and three falling
carrier steps, and every declared offset. T660-2 A supplies the continuous DIO0
reference while the installed 10 MHz distribution remains unchanged. A minimum
three-second locked interval precedes polling. PicoScope channel A retains
voltage authority and channel B monitors the T660 copy.

Analysis gates connected runs from the reference magnitude, retains only exact
common timestamps, divides simultaneous complex samples, explicitly restores
the reference transfer, and fits one bounded constant paired-pipeline delay per
anchor before phase and group-delay residuals are evaluated. Native step samples
are not temporally smoothed. AWG zero, T660 safe idle, HF2LI restoration, and
master-clock lock are verified after every acquisition.

No fourth model point, physical parameter grid, experiment identity, sample,
laser action, or optical measurement is part of this design.
