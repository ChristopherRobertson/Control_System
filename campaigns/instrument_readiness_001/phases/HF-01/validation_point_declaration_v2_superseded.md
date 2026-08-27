# HF-01 three-anchor dual-demodulator validation design (superseded v2)

Declaration version: `HF01-VALIDATION-DESIGN-v2`.

The three points below are instrument-model anchors, not experiment presets.
They span the installed order, time-constant, bandwidth, sampling, and settling
envelope required before any experiment configuration is selected.

Demodulator 0 is the filter under test. Demodulator 1 is a wideband phase and
transition reference on the same input and HF2LI clock domain. Both are sampled
at equal installed rates. The actual readback of every quantized node is the
analysis authority.

| Anchor ID | Test order | Requested test time constant | Test offsets | Paired output rate | Role |
|---|---:|---:|---|---:|---|
| `HF01-ANCHOR-FAST-V2-001` | 1 | 4 us | +3,980; +39,800; +199,000 Hz | maximum supported for two active demodulators | Short-time and high-bandwidth anchor |
| `HF01-ANCHOR-INTERMEDIATE-V2-001` | 4 | 1 ms | +6.92; +69.2; +346; -69.2 Hz | approximately 2 kSa/s | Mid-bandwidth and positive/negative phase anchor |
| `HF01-ANCHOR-SLOW-V2-001` | 8 | 100 ms request; installed quantized readback retained | +0.0479; +0.479; +2.395 Hz | approximately 100 Sa/s | Long-time high-order and settling anchor |

For each anchor:

1. T660-2 A supplies the continuous 2 MHz-class DIO0 reference while the
   installed 10 MHz clock distribution remains unchanged.
2. The PLL is allowed a minimum three-second locked stabilization interval
   before response polling begins.
3. Demodulator 1 is set to order 1 and the installed minimum time constant; its
   oscillator, harmonic, ADC input, trigger, and output rate match demodulator 0.
4. The record contains a connected-zero baseline, three rising carrier steps,
   three falling carrier steps, and every declared offset-carrier condition.
5. PicoScope channel A measures the connected stimulus. Channel B continues to
   monitor the T660 reference copy; no physical wiring change is required.
6. Analysis uses timestamp-matched `Z_test/Z_reference` samples for complex
   magnitude, phase, cutoff, group delay, step timing, and sign reversal.
7. AWG zero, T660 safe idle, HF2LI configuration restoration, and master-clock
   lock are verified after every acquisition.

No fourth model point, physical parameter grid, experiment identity, sample,
laser action, or optical measurement is part of this design.
