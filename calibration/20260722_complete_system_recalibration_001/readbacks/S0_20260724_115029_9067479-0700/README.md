# S0 safe-idle, ownership, identity, and interlock record

Campaign: `20260722_complete_system_recalibration_001`
Operator: `Christopher Robertson`
Execution: `2026-07-24T18:52:27+00:00` through `2026-07-24T18:52:41+00:00`
Git commit: `11b870cbf5ee2a921a43003cb353bbf473dfe738`
Result: **PASS**

## Scope

S0 only was executed through Windows PowerShell and the repository Windows
virtual environment. Normal wiring was untouched. No cable was moved, no
Arduino MUX command was sent, no T660 channel was enabled, no trigger source
was started, no MIRcat process-trigger pulse was generated, neither laser was
armed or fired, and no canonical calibration output was created or modified.

Christopher Robertson independently confirmed the physical laser inhibits,
room interlock and installed safety controls, normal CLOCK-SPLITTER-01
distribution, untouched fixed DDG bulkhead assemblies, T660-1 CH D
disconnected/unmapped state, MIRcat DB9 pin 5 disconnection, MIRcat DB9 pins 6
and 8 unwired state, disabled Arduino MUX, and closure of competing hardware
clients before access.

## Ownership and identity

- T660-1: exclusive Windows serial ownership on `COM3`; identity
  `HTI,T660-1,00369,28E660-1-1.7`.
- T660-2: exclusive Windows serial ownership on `COM7`; identity
  `HTI,T660-2,00431,28E660-1-1.7`.
- MIRcat: single-client `MIRcatSDK_Initialize` ownership; configured identity
  `MIRcat-QT-Z-2100`, serial `10524`; SDK API readback `2.4.1`.
- Nd:YAG: P0 physical identity `SL EX`, serial `24366-1`; no S0 command
  interface was used.

T660 identity and firmware queries occurred only after both units had accepted
STOP, trigger-source OFF, all four channel OFF commands, and all eight channels
plus both trigger sources had read back OFF.

## Verified safe state

- The approved `recipes/safe_idle.yaml` resolved and matched every required
  T660 readback with no mismatch.
- T660-1 channels A/B/C/D: `OFF`; T660-2 channels A/B/C/D: `OFF`.
- T660-1 CH C retained the disabled, inactive-high/active-low Process Trigger
  configuration: negative polarity and nominal `10 ms` width. It was not
  pulsed.
- T660-1 CH D remained disabled, disconnected, and unmapped.
- MIRcat: connected `true`, emission `false`, armed `false`, interlock `true`,
  key switch `true`, scan in progress `false`, scan active `false`, status-mask
  scanning `false`, and no readback error.
- Final cleanup readbacks passed independently for T660-1, T660-2, and MIRcat.
  All three exclusive ownership sessions were released.

There were no blockers. S0 is complete. MS-01 and every later phase remain
unauthorized pending separate explicit user approval. Canonical promotion
still requires the exact phrase `APPROVE CALIBRATION PROMOTION`.
