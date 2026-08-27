# MC-01 optical-emission and DAQ clarification

Operator clarification recorded during restoration:

- The manual MIRcat shutter remained closed for the entire MC-01 continuation.
- MIRcat Pulse Mode was External Trigger.
- T660-2 issued no MIRcat laser-trigger pulse during MC-01.
- The only commanded timing output was T660-1 CHC to DB9 pin 4 Process Trigger.
- HF2LI acquisitions subscribed only to timing demodulator 2 `sample.dio`;
  detector X, Y, and R values were not requested or recorded.

Therefore the green GUI `Emission` indicator and QCL Active display establish
an enabled MIRcat process/emission-gate state, not optical pulse or delivered
beam evidence. No optical pulse or external beam emission is claimed for
MC-01. The active work qualified process-control and DIO timing behavior, not
detector response, optical power, or optical timing.

Authorization `MC01-AUTH-002` permitted emission if necessary, but that portion
of the authorization was not exercised.
