# Default wiring state convention

This repository uses the phrase **default wiring restored** as a stable
operator-confirmed state. Unless Christopher Robertson explicitly reports a
change, the phrase includes the detector connections and standing exclusions below.

## Default detector connections

The current setup was reported on **2026-08-31**. Each detector signal has its
own **female-to-female BNC adapter -> male-to-two-female BNC tee** assembly.
The two female tee branches connect by cable to the corresponding HF2LI signal
input and PicoScope channel; sample and reference remain separate signals.
**Detector 1 is the sample detector; detector 2 is the reference detector.**

| Detector signal | Connection sequence before branching | HF2LI destination | PicoScope destination |
| --- | --- | --- | --- |
| Detector 1 (sample) | Female-to-female BNC adapter -> male-to-two-female BNC tee | Signal 1 In (+) | CHA (channel A) |
| Detector 2 (reference) | Female-to-female BNC adapter -> male-to-two-female BNC tee | Signal 2 In (+) | CHB (channel B) |

```text
Detector 1 (sample) -> female-to-female BNC adapter -> male-to-two-female BNC tee
                                                     +-> HF2LI Signal 1 In (+)
                                                     +-> PicoScope CHA

Detector 2 (reference) -> female-to-female BNC adapter -> male-to-two-female BNC tee
                                                        +-> HF2LI Signal 2 In (+)
                                                        +-> PicoScope CHB
```

Both receivers are connected in the default state, including when the PicoScope
is not recording. These detector branches bypass the inactive Arduino MUX.
The HF2LI remains the primary sample/reference spectral recorder; the PicoScope
provides waveform and timing diagnostics. In this default wiring, PicoScope
CHA and CHB both carry detector signals; neither carries a T660 trigger signal.
This update does not select a
PicoScope EXT trigger source or change any clock, T660, or MIRcat route.

The matching connection records are in [wiring_map.yaml](wiring_map.yaml) and
[wiring_table.xlsx](wiring_table.xlsx). Adapter/tee identities, branch cable
identities and lengths, receiver coupling/termination, and electrical transfer
values not supplied by the operator remain `USER_INPUT_REQUIRED` in prospective
configuration records. Do not infer equal amplitudes, a 50/50 electrical split,
or equal branch delay. The installed loading, attenuation, reflections,
bandwidth, and skew must be qualified in
[MS-02.1](../campaigns/instrument_readiness_001/phases/MS-02.1/plan.md).

Temporary sample-plane timing/IRF wiring uses PicoScope CHA for the sample IR
detector and CHB for the pump detector under a separate configuration record.
Record any disconnected detector branch and resulting change in receiver load;
restore both default detector split paths after that temporary work.

## Standing exclusions

- T660-1 channel D is disconnected and unused.
- MIRcat process-control DB9 pin 5 is disconnected.
- MIRcat process-control DB9 pin 6 is unused and unwired.
- MIRcat process-control DB9 pin 8 is unused and unwired.

These are standing conditions, not recurring operator gates. Calibration,
characterization, and experiment workflows must not ask the operator to
reconfirm them after default wiring restoration unless the operator reports a
change affecting one of these connections. A reported change requires the
applicable safe-idle review before further physical transition or active
electrical testing.

The convention does not make a disabled-channel readback equivalent to a
physical disconnection where a phase-specific temporary electrical test
explicitly requires another destination to be isolated. It defines only the
default detector paths and four standing exclusions above.

## Historical evidence

Earlier inventories, phase acquisitions, reports, and restoration confirmations
retain the wiring recorded at the time. In particular, the P0 clock-splitter-only
inventory and HF-01 temporary AWG tee records do not describe or qualify the new
default detector split paths. This documentation update does not rewrite those
records, change a phase disposition, promote a calibration, or authorize hardware.

