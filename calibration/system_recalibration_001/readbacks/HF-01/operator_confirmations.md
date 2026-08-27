# HF-01 operator confirmations

## HF01-OPCONF-001 — Nd:YAG/OPO nonemitting state

- Timestamp: `2026-08-26T19:28:34.5846785Z`
- Operator: Christopher Robertson
- Observation: there is no separate electronic-inhibit control for the
  Nd:YAG. The lasers are currently turned off and the interlock is disconnected,
  so they cannot fire.
- Disposition: accepted as the installed Nd:YAG/OPO nonemitting/inhibit
  implementation for HF-01.
- Claim limit: this observation does not establish shutter state and does not
  apply to the MIRcat state, which are recorded separately.

## HF01-OPCONF-002 — closed-shutter standing state and advance authorization

- Timestamp: `2026-08-26T19:29:37.8679451Z`
- Operator: Christopher Robertson
- Observation/convention: shutters are closed unless the operator explicitly
  reports that they are open.
- Direction: advance past remaining repetitive safety checks to the next step.
- Disposition: current shutters accepted closed; together with the immediately
  preceding statement that the lasers are turned off, HF-01 safety intake is
  complete and component inspection may begin.
- Scope limit: no laser arming, firing, emission, shutter opening, optical work,
  or later phase is authorized. One-action-at-a-time cable handling remains in
  force.

## HF01-OPCONF-003 — component labels and stimulus wiring

- Timestamp: `2026-08-26T19:36:09.2395061Z`
- Operator: Christopher Robertson
- Labels: operator confirms the requested HF-01 labels have been set.
- Connected route 1: `PicoScope SIGNAL OUT -> HF01-STIMULUS-TEE-01 ->
  HF01-RG58-01 -> HF2LI Signal Input 1`.
- Connected route 2: `PicoScope SIGNAL OUT -> HF01-STIMULUS-TEE-01 ->
  HF01-RG58-02 -> PicoScope channel A`.
- Photo disposition: operator declines photographs; recorded as
  `HF01-DEV-001` rather than treated as an operational block.
- Claim limit: exact tee markings, cable length, spare-tee physical state, and
  timing-copy wiring were not reported in this confirmation.

## HF01-OPCONF-004 — temporary timing-copy topology

- Timestamp: `2026-08-26T19:44:51.2824370Z`
- Operator: Christopher Robertson
- Confirmation: temporary re-wiring completed as instructed.
- Accepted topology: T660-2 A remains at HF2LI DIO0; B is disconnected from
  MIRcat and connected to PicoScope B; C remains at HF2LI DIO1; D is
  disconnected from T660-1 and connected to PicoScope EXT.
- Disposition: one bounded 10 Hz digital timing check is permitted. PicoScope
  generator remains programmed zero.

## HF01-OPCONF-005 — first nonzero PicoScope AWG enable

- Timestamp: `2026-08-26T20:05:01.7544193Z`
- Operator: Christopher Robertson
- Confirmation: authorization given after presentation of the exact first
  enable settings and source/load calculation.
- Authorized output: continuous sine, `2,000,000.000 Hz`, `0.050000 Vpp`
  programmed amplitude, `0.000000 V` offset, nominal 50-ohm source into HF2LI
  Signal Input 1 and PicoScope channel A in DC-coupled high impedance.
- Expected connected amplitude: `0.0499925` to `0.0499950 Vpp` under the
  open-voltage interpretation, with measured acceptance guard `0.040` to
  `0.110 Vpp`, offset magnitude no greater than `0.005 V`, and no overflow or
  HF2 clipping.
- Disposition: execute `HF01-AWG-FIRST-ENABLE-001`; subsequent bounded HF-01
  acquisitions remain covered by `HF01-AUTH-AMEND-004`.

## HF01-OPCONF-006 — common stimulus moved to Signal Input 2

- Recorded timestamp: `2026-08-26T22:59:42.3040771Z`
- Operator: Christopher Robertson
- Observation: `HF01-RG58-01` was moved from HF2LI Signal Input 1 to HF2LI
  Signal Input 2. The other temporary stimulus route remained
  `HF01-STIMULUS-TEE-01 -> HF01-RG58-02 -> PicoScope channel A`.
- Disposition: accepted as the physical topology for the Signal Input 2
  selected-configuration confirmations and declared range-endpoint checks.
- Restoration state: this remains a temporary HF-01 connection and does not
  establish default wiring restoration.

## HF01-OPCONF-007 — HF2LI stimulus branch disconnected

- Recorded timestamp: `2026-08-26T23:34:58.7512426Z`
- Operator: Christopher Robertson
- Observation: `HF01-RG58-01` is disconnected from HF2LI Signal Input 2 and
  remains connected to `HF01-STIMULUS-TEE-01`.
- Disposition: accepted as the first default-restoration move. Both HF2LI
  signal inputs are free of the temporary HF-01 stimulus.
- Remaining temporary monitored-stimulus path:
  `PicoScope AWG OUT -> HF01-STIMULUS-TEE-01 -> HF01-RG58-02 -> PicoScope A`,
  with the disconnected `HF01-RG58-01` branch still attached to the tee.

## HF01-OPCONF-008 — stimulus tee disconnected from generator

- Recorded timestamp: `2026-08-26T23:36:01.9094099Z`
- Operator: Christopher Robertson
- Observation: `HF01-STIMULUS-TEE-01` is disconnected from PicoScope
  `SIGNAL OUT`; `HF01-RG58-01` and `HF01-RG58-02` remain attached to the tee.
- Disposition: accepted as the second default-restoration move. The temporary
  stimulus assembly is physically isolated from both the PicoScope generator
  and the HF2LI.
- Remaining temporary connection: `HF01-RG58-02 -> PicoScope channel A`.

## HF01-OPCONF-009 — PicoScope measurement branch disconnected

- Recorded timestamp: `2026-08-26T23:39:55.9999470Z`
- Operator: Christopher Robertson
- Clarification: the operator's initial reference to `HF01-RG58-01` at
  PicoScope channel A was a typographical error; the cable removed from that
  connection was `HF01-RG58-02`.
- Observation: `HF01-RG58-01` and `HF01-RG58-02` are disconnected from all
  instruments and both remain attached to the isolated
  `HF01-STIMULUS-TEE-01`.
- Disposition: the temporary monitored-stimulus assembly is fully isolated
  from the HF2LI and PicoScope. Removal of the cables from the tee remains.

## HF01-OPCONF-010 — T660-2 channel B monitor disconnected

- Recorded timestamp: `2026-08-26T23:43:00.0037601Z`
- Operator: Christopher Robertson
- Observation: the cable from T660-2 channel B is disconnected from
  PicoScope channel B and remains connected to T660-2 channel B.
- Electronic precondition: `HF01-PRE-RESTORATION-SAFE-STATE-001` passed with
  all T660 outputs disabled and no safe-idle mismatches before this move.
- Disposition: the cable's free destination end is ready for reconnection to
  MIRcat `TRIG IN`.

## HF01-OPCONF-011 — T660-2 channel B default route restored

- Recorded timestamp: `2026-08-26T23:43:21.6217601Z`
- Operator: Christopher Robertson
- Observation: the free destination end of the T660-2 channel B cable is
  connected to MIRcat `TRIG IN`.
- Electronic state: T660-2 remains in the readback-verified safe-idle state;
  this connection does not authorize MIRcat emission or a trigger output.
- Disposition: default route `T660-2 B -> MIRcat TRIG IN` is restored.

## HF01-OPCONF-012 — T660-2 channel D monitor disconnected

- Recorded timestamp: `2026-08-26T23:47:27.8326649Z`
- Operator: Christopher Robertson
- Observation: the cable from T660-2 channel D is disconnected from the
  PicoScope `EXT` input and remains connected to T660-2 channel D.
- Electronic precondition: T660-2 remains in the readback-verified safe-idle
  state established by `HF01-PRE-RESTORATION-SAFE-STATE-001`.
- Disposition: the cable's free destination end is ready for reconnection to
  T660-1 `TRIG IN`.

## HF01-OPCONF-013 — T660-2 channel D default route restored

- Recorded timestamp: `2026-08-26T23:47:50.4799516Z`
- Operator: Christopher Robertson
- Observation: the free destination end of the T660-2 channel D cable is
  connected to T660-1 `TRIG IN`.
- Electronic state: both T660 units remain in the readback-verified safe-idle
  state; this connection does not authorize an external-trigger event or any
  output enable.
- Disposition: default route `T660-2 D -> T660-1 TRIG IN` is restored.

## HF01-OPCONF-014 — default wiring restoration accepted

- Recorded timestamp: `2026-08-26T23:48:22.5562080Z`
- Operator: Christopher Robertson
- Observation: the wiring is back in the default configuration.
- Imported standing conditions: under `docs/default_wiring_state.md`, this
  includes T660-1 channel D disconnected, MIRcat DB9 pin 5 disconnected, and
  MIRcat DB9 pins 6 and 8 unused/unwired; no repetitive reconfirmation was
  requested.
- HF-01 route disposition: T660-2 A remains at HF2LI DIO0; T660-2 B is at
  MIRcat `TRIG IN`; T660-2 C remains at HF2LI DIO1; T660-2 D is at T660-1
  `TRIG IN`; `CLOCK-SPLITTER-01` remains in its normal distribution; the
  temporary stimulus assembly and spare tee are disconnected from instruments.
- Photo disposition: the operator previously declined photographs; restoration
  is established by the sequential operator confirmations and this final
  default-state confirmation.
- Scope limit: this confirmation does not authorize output enable, laser
  emission, shutter opening, a later calibration phase, or calibration
  promotion.
