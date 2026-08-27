# HF-01 source/load and safe-voltage envelope

## Network model

- Source: PicoScope 5244D generator, nominal `50 ohm` output resistance.
- Tee: passive, DC-coupled, no termination.
- Load 1: one HF2LI signal input in high impedance, manufacturer typical
  `1 Mohm` and minimum `500 kohm`.
- Load 2: PicoScope channel A in high impedance, nominal `1 Mohm`.
- Cable characteristic impedance: `50 ohm`; the electrically short tee/cable
  assembly is treated as a lumped load for the 2 MHz carrier, with any measured
  arm difference retained rather than assumed away.

Using two nominal `1 Mohm` parallel loads gives `R_load = 500 kohm` and the
Thevenin divider

`V_connected / V_open = 500000 / (500000 + 50) = 0.99990001`.

Using the conservative HF2 minimum `500 kohm` in parallel with the PicoScope
`1 Mohm` gives `R_load = 333.333 kohm` and

`V_connected / V_open = 333333.3 / (333333.3 + 50) = 0.99985002`.

No separate 50-ohm termination is selected. If either input is observed or
read back as 50 ohm, nonzero output is prohibited until the calculation is
reviewed again. Grounds must share the intended instrument reference only; a
second source on the selected HF2LI input is prohibited.

## First-enable declaration

The first requested nonzero output, after complete wiring/readback approval,
will be:

- waveform: sine
- programmed frequency: `2,000,000.000 Hz`
- programmed amplitude: `0.050000 V peak-to-peak`
- programmed offset: `0.000000 V`
- generator trigger: none/continuous
- HF2LI selected signal input: DC coupled, high impedance
- PicoScope channel A: DC coupled, high impedance

Under the explicit Thevenin-open-voltage interpretation, expected connected
amplitude is `0.0499925 to 0.0499950 Vpp`. Because the SDK documentation does
not itself establish whether its amplitude argument is expressed as an
open-load or matched-load calibration value, the first capture also guards the
alternative factor-of-two case: nonzero operation stops unless measured
channel-A amplitude is within `0.040 to 0.110 Vpp`, offset magnitude is at most
`0.005 V`, and no overflow occurs. The measured connected value, not either
calculated convention, becomes the stimulus authority.

## Electrical test interval and hard limits

- Planned connected low endpoint: approximately `0.010 Vpp`.
- Planned connected high endpoint: no more than `0.100 Vpp`.
- Hard stop: measured connected amplitude above `0.120 Vpp`, absolute peak
  above `0.070 V`, absolute DC offset above `0.010 V`, PicoScope overflow,
  HF2LI overload, unexpected 50-ohm termination, or evidence of another source.
- Initial HF2LI range: `1 V`; the range screen may consider the supported
  immediately smaller/larger ranges only under the frozen clipping margin.

These are conservative HF-01 electrical values, not an asserted operational
detector-output interval and not a detector calibration.
