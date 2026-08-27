# HF-01 reviewed temporary wiring plan

## Unchanged installed clock distribution

`T660-2 CLOCK OUT -> CLOCK-SPLITTER-01 input`

- existing splitter output -> `T660-1 CLOCK IN`
- existing splitter output -> `HF2LI CLOCK IN`
- remaining installed splitter state unchanged

HF-01 does not move, bypass, repurpose, or reterminate this splitter.

## Temporary monitored stimulus

`PicoScope AWG OUT -> HF01-STIMULUS-TEE-01 male`

- tee female -> `HF01-RG58-01` -> one HF2LI signal input
- tee female -> `HF01-RG58-02` -> PicoScope channel A, DC, high impedance

The same tee and cables are used sequentially for Signal Inputs 1 and 2. One
destination/cable exchange at the common-path screen measures arm/cable
asymmetry. The cables are supported so the tee does not strain the PicoScope
bulkhead. `HF01-SPARE-TEE-01` remains disconnected.

## Temporary timing copies

- T660-2 A remains directly connected to HF2LI DIO0.
- T660-2 B is disconnected from MIRcat, configured as a readback-verified copy
  of A, and connected to high-impedance PicoScope channel B.
- T660-2 C remains directly connected to HF2LI DIO1.
- T660-2 D is disconnected from T660-1, configured as a readback-verified copy
  of C, and connected to PicoScope EXT.

The one retained 10 Hz test is digital timing only. No timing output reaches
MIRcat, T660-1, or any laser controller while this topology is active.

## Preconditions for every move

1. Generator programmed to zero and recorded.
2. T660 outputs disabled and read back safe when a timing cable is moved.
3. Routine actions may be presented in an ordered batch under
   `HF01-AUTH-AMEND-001`; the resulting observations are recorded before
   nonzero output.
4. Ground/termination/source conflicts are checked before nonzero output.
5. A photograph is retained after the complete temporary topology and again
   after restoration.

## Default restoration target

- T660-2 A -> HF2LI DIO0
- T660-2 B -> MIRcat `TRIG IN`
- T660-2 C -> HF2LI DIO1
- T660-2 D -> T660-1 external trigger input
- PicoScope AWG stimulus tee and both temporary cables disconnected
- `HF01-SPARE-TEE-01` disconnected
- `CLOCK-SPLITTER-01` unchanged
- standing repository defaults preserved: T660-1 D disconnected; MIRcat DB9
  pin 5 disconnected; pins 6 and 8 unused/unwired

This is a reviewed plan, not evidence that any connection presently has the
listed state. Only operator observations establish physical state.
