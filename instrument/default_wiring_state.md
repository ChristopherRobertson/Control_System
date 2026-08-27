# Default wiring state convention

This repository uses the phrase **default wiring restored** as a stable
operator-confirmed state. Unless Christopher Robertson explicitly reports a
change, the phrase includes all of the following:

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
four standing default-wiring exclusions above.

