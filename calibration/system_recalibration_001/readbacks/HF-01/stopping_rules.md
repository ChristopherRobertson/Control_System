# HF-01 stop and restoration rules

Immediately program the generator to zero, disable all temporary T660 outputs,
preserve evidence, and stop on any of these conditions:

- laser inhibit or shutter state is not affirmatively observed as required;
- an instruction would arm/fire a laser, open a shutter, move optics, touch a
  sample, continue WM-01/ATT-01/later work, or promote calibration;
- unexpected source, ground conflict, 50-ohm termination, overload, voltage
  envelope violation, missing timestamp/segment, competing device owner, or
  settings loss;
- `CLOCK-SPLITTER-01` would need to be moved or reterminated;
- a primary v3 anchor still fails after one same-setting integrity repeat, or
  the dual-demodulator timestamps cannot be matched exactly;
- a physical observation disagrees with the reviewed wiring plan;
- the operator requests stop.

An abnormal stop does not discard or overwrite any record. It logs the actual
state, rejection reason, and required restoration. Restoration itself remains
operator-led one physical action at a time. Final closure requires generator
zero, T660 safe-idle readback, HF2 settings restoration/reload comparison,
default wiring observation, unchanged clock splitter observation, tee/cable
removal, final inhibited/shuttered laser observations, retention audit, and a
completed `restoration_confirmation.json`.
