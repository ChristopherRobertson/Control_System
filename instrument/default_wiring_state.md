# Default instrument wiring

“Default wiring restored” denotes the connections below and both spare channel D
outputs disconnected. These are standing conditions unless Christopher Robertson
reports a change. Recipes define the settings for a measurement within this wiring.

## Shared clock and pulse timing

T660-2 **CLOCK OUT** supplies the shared **10 MHz** reference through
**CLOCK-SPLITTER-01** to T660-1 **CLOCK IN** and HF2LI **Clock In**. T660-1 uses
external clock locking and the HF2LI selects its external reference clock.
T660-2 remains the clock source. Verify clock modes and receiving-device lock
readbacks before timing qualification; this wiring alone does not establish
absolute frequency accuracy or calibrated timing uncertainty.

The 10 MHz reference and the pulse-trigger chain have different functions.
T660-1 synthesizes probe/reference pulses and sends frame-input pulses to T660-2.
T660-2 divides those trigger events and executes the selected trains/frames recipe.
Receiving T660-1 trigger pulses does not make T660-2 a clock input or create a
clock feedback loop. T660-1 TRIG IN is unconnected.

| Output | Destination | Function |
| --- | --- | --- |
| T660-1 A | HF2LI DIO0 / Ext Ref BNC | Continuous demodulation reference |
| T660-1 B | MIRcat TRIG IN BNC | Probe pulse trigger |
| T660-1 C | T660-2 TRIG IN | Trigger input for pump/process timing |
| T660-1 D | SPARE, disconnected | Disabled |
| T660-2 A | Surelite EXT DB9 pin 7 | Fire command |
| T660-2 B | Surelite EXT DB9 pin 6 | Q-switch command |
| T660-2 C | MIRcat process DB9 pin 4 | Process Trigger |
| T660-2 D | SPARE, disconnected | Disabled |

Trains repeat pulses within an accepted event; frames provide successive channel
timing configurations. The finite Phase Scan workflow uses a 2 MHz trigger input,
a 600,000 predivider and a 300 ms frame cadence, with zero additional train pulses.
These values belong to that measurement method. Other experiment types must
define their own input rate, divider, pulse/train settings, finite frame count,
receiver coverage and termination behavior. Nd:YAG alignment uses a 10 Hz
T660-1 C input and divider 1. Standalone detector alignment enables T660-1 A/B
and leaves the pump/process outputs and T660-1 C disabled.

## Observed timing signals

| Signal source | Recorded destination |
| --- | --- |
| Surelite Fixed Sync OUT | HF2LI DIO16 |
| Surelite Variable Sync OUT | HF2LI DIO17 |
| Surelite Flashlamp Sync OUT | HF2LI DIO18 |
| MIRcat TRIG OUT | HF2LI DIO19 |
| MIRcat DB9 pin 1, Scan Direction | HF2LI DIO20 |
| MIRcat DB9 pin 2, Tuned / Sweep Active | HF2LI DIO21 and PicoScope EXT |
| MIRcat DB9 pin 3, Wavelength Trigger | HF2LI DIO22 |

DIO numbers identify **logical HF2LI bits**, not physical connector pin numbers.
MIRcat DB9 pin 2 is split directly to both receivers. In the configured sweep
mode its high interval marks sweep activity; its meaning in a stationary tuning
mode follows the MIRcat mode. Use the DB9 ground reference (pin 7), and retain
high-impedance receiving inputs. Do not add a 50 ohm load to this marker branch.
The routing is corroborated by the P0 DIO mapping side experiment; loading,
thresholds and edge transfer through both branches still need MS-02.1 and MD-01 qualification.

Sweep Active can delimit the observed acquisition interval. Electrical markers
alone do not prove optical pulse arrival, an optical time zero, or complete sample
coverage. Those claims require the relevant timing and acquisition qualification.

## Optional acquisition-window input

HF2LI DIO1 remains an **unconnected optional acquisition-window input**. A future
measurement that needs an independently positioned hardware gate may assign
T660-2 D to it, because that output shares the pump/process frame timing. That
assignment requires an explicit wiring/configuration update and gate qualification.
For now both D channels remain spare, disconnected and disabled. Continuous
demodulator acquisition and recorded Sweep Active events do not require DIO1.

## Detector connections

Each detector signal passes through its own female-to-female BNC adapter and
male-to-two-female BNC tee. Sample and reference remain separate signals.

| Detector | HF2LI destination | PicoScope destination |
| --- | --- | --- |
| Detector 1, sample | Signal 1 In (+) | CHA |
| Detector 2, reference | Signal 2 In (+) | CHB |

Both receivers stay connected, including when the PicoScope is not recording.
The detector branches bypass the inactive Arduino MUX. The HF2LI is the primary
sample/reference spectral recorder; the PicoScope provides waveform and timing
diagnostics. Its analog channels carry the two detector signals and its EXT input
receives MIRcat Sweep Active.

Adapter/tee identities, branch cable identities and lengths, receiver coupling and
termination, and unmeasured electrical transfer values remain explicit prospective
configuration inputs. Do not infer equal amplitudes, an equal electrical split,
or equal branch delay. [MS-02.1](../campaigns/instrument_readiness_001/phases/MS-02.1/plan.md)
qualifies the installed loading, attenuation, reflections, bandwidth and skew.

Temporary sample-plane timing/IRF wiring uses PicoScope CHA for the sample IR
detector and CHB for the pump detector under a separate configuration record.
Record any disconnected detector branch and change in receiver load, then restore
both default detector paths after that work.

## Restoration and standing exclusions

- Both T660 D outputs are spare, disconnected and disabled.
- T660-1 TRIG IN and HF2LI DIO1 are unconnected.
- MIRcat process-control DB9 pins 5, 6 and 8 are disconnected and unused.
- Safe idle inhibits both trigger sources, disables all channel outputs, stops the
  T660-2 frames engine and clears additional train pulses in its staging banks.
  MIRcat Process Trigger has negative pulse polarity with its inactive level high.

These standing connections do not require recurring confirmation after default
wiring restoration unless a reported change affects them. A disabled-channel
readback does not establish physical disconnection during a temporary electrical
test that explicitly requires isolation.

[hardware_configuration.yaml](hardware_configuration.yaml),
[wiring_map.yaml](wiring_map.yaml) and [wiring_table.xlsx](wiring_table.xlsx)
record this topology. Campaign phases qualify its electrical and optical behavior;
configuration metadata alone does not confer readiness or promote a calibration.
