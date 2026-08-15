# PT-01 Setup 1 operator gate

Status: **OPERATOR ACTION REQUIRED**

The 2026-08-13 initial preflight passed. Both T660s are in verified safe idle
and all outputs are disabled.

With power/interlocks handled under the laboratory procedure:

1. Keep the temporary OP-01 splitter absent and keep the normal T660-1 CHB
   Q-switch source cable restored.
2. Disconnect the complete Nd:YAG timing DB9 from the laser. At the
   disconnected harness, connect FIRE pin 7 to PicoScope CHA using the same
   characterized measurement path used by T1-01.
3. Disconnect the complete MIRcat process-control DB9 from the MIRcat. At the
   disconnected harness, connect Process Trigger pin 4 to PicoScope CHB using
   the approved pin-only breakout.
4. Confirm reserved MIRcat DB9 pin 5 is disconnected, and pins 6 and 8 are
   unused and unwired. Do not probe or connect them.
5. Keep T660-1 CHD disconnected. Keep T660-2 CHB and CHC on their normal final
   routes but disabled; keep T660-2 CHD connected to T660-1 TRIG IN.
6. Confirm neither the Nd:YAG nor MIRcat receives any T660-1 measured line;
   only the two disconnected breakout conductors reach the PicoScope.

No output may be enabled until the operator reports that all six conditions
are satisfied and the post-connection safe-idle readback passes.
