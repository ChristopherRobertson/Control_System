# MC-01 operator gate 1 - physical inhibits, ownership, and GUI provenance

Do not click **Arm**, **Laser Output On**, **Start**, **Scan**, **Step**,
**Process**, or any similar action control at this gate.

## Complete gate sequence

With both T660 units left in their current disabled state:

1. Confirm the MIRcat optical output is physically inhibited by the installed
   normal safety control and that no optical emission is possible.
2. Confirm the MIRcat is not armed and its GUI reports laser output off.
3. Apply the standing `docs/default_wiring_state.md` convention: T660-1
   channel D and MIRcat DB9 pin 5 are disconnected; pins 6 and 8 are
   unused/unwired. Do not ask for reconfirmation unless the operator explicitly
   reports a change, and do not touch those conductors.
4. Confirm default wiring is present: T660-1 CHC to MIRcat DB9 pin 4 Process
   Trigger; MIRcat DB9 pin 2 Tuned/Sweep Active to HF2LI DIO 21; pin 1 to DIO
   20; pin 3 to DIO 22; grounds remain on pins 7/9.
5. Close every MIRcat SDK, control application, or other client. Open only the
   manufacturer GUI and allow it to become the exclusive MIRcat owner.
6. Without changing settings, record or screenshot the GUI About/version view,
   controller firmware view, connected model/serial, current configuration or
   Favorite name, operating mode, process-trigger mode, laser-trigger mode,
   laser-output/armed/interlock state, and the point/process sequence shown.

Preserve each screenshot or exported log with its original filename. Do not
crop, overwrite, rename in place, or discard a partial/failed capture.

The operator is the graduate student who designed the system. After the
initial safety/ownership observations, routine GUI configuration may be issued
as one ordered batch with a compact screenshot/export checklist. Separate
stops remain only for configuration acceptance, inhibited control, bounded
active electrical repeats, and restoration/readback decisions.

## Required response

For each released batch, perform the listed actions in order, then attach the
requested native screenshots/logs. Report `NOT SHOWN` for any unavailable GUI
item with the exact visible label/message. Do not advance into a later test
batch without its explicit release.

## Later gates

After gate 1 evidence is recorded, Codex will apply and verify T660 safe idle,
then issue one gate at a time for: configuration review; inhibited control;
three bounded 10 ms active-low pin-4 repeats; exception/failure observation;
and final ownership release, shutdown, default-wiring restoration, and safe-idle
readback. Authorization `MC01-AUTH-002` now permits the minimum controlled
emission and SDK controls needed for those bounded MC-01 gates.
