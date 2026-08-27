# HF-01 safe-state checklists

Each checkbox is satisfied only by a timestamped readback or operator
observation in the action ledger. This file is a checklist, not state evidence.

## Before the first cable action

- [x] Nd:YAG/OPO nonemitting inhibit implementation observed: lasers powered
  off and firing interlock disconnected; operator confirms no separate
  electronic-inhibit control exists (`HF01-OPCONF-001`).
- [x] Nd:YAG/OPO shutter closed under the operator's standing closed-shutter
  convention (`HF01-OPCONF-002`).
- [x] Lasers reported turned off; operator authorized advancement past the
  remaining repetitive laser-state checks (`HF01-OPCONF-002`).
- [x] MIRcat shutter closed under the operator's standing closed-shutter
  convention (`HF01-OPCONF-002`).
- [x] PicoScope generator programmed zero through the exclusive SDK owner.
- [x] T660-2 outputs disabled and read back safe.
- [x] HF2LI `dev18500` exclusive access and identity read back.
- [x] PicoScope 5244D serial `10261` exclusive access and identity read back.
- [x] Pico capture plus generator controls qualified on one handle.
- [x] `CLOCK-SPLITTER-01` normal distribution observed and unchanged.

## Before first nonzero generator output

- [x] Temporary topology observed against `temporary_wiring_plan.md`.
- [x] Tee/cable IDs retained; photograph deviation `HF01-DEV-001` recorded;
  spare tee confirmed disconnected at final default restoration.
- [x] Selected HF2 input has no other source.
- [x] HF2 selected input is DC/high-Z and Pico A is DC/high-Z.
- [x] Ground review complete; no ground conflict observed.
- [x] HF2 external-clock selection/lock read back.
- [x] Exact first-enable settings and source/load calculation presented.
- [x] Operator explicitly confirms the presented settings.
- [x] Pico A capture is armed before nonzero enable.

## Before every cable exchange/restoration move

- [x] Generator programmed zero.
- [x] When a timing cable is involved, all T660 temporary outputs disabled and
  read back safe.
- [x] Physical restoration moves presented and confirmed in sequence.
- [x] Observations recorded before restoration acceptance.

## Final restoration

- [x] Generator programmed zero and SDK owner closed.
- [x] T660 safe-idle applied and verified.
- [x] HF2 prechange settings reloaded and compared.
- [x] T660-2 B reconnected to MIRcat `TRIG IN`.
- [x] T660-2 D reconnected to T660-1 external trigger.
- [x] T660-2 A->HF2 DIO0 and C->HF2 DIO1 observed unchanged/restored.
- [x] Temporary stimulus tee/cables removed; spare tee disconnected.
- [x] `CLOCK-SPLITTER-01` normal wiring observed unchanged.
- [x] Standing default exclusions observed/preserved where applicable.
- [x] Both laser systems remain in the accepted nonemitting state.
- [x] Both laser shutters closed under the operator's standing convention.
- [x] Photograph deviation and final readbacks retained; retention audit passed.
- [x] No later phase or promotion performed.
