# MC-01 operator gate 2 - resume active GUI qualification

Authorization: `MC01-AUTH-002`  
Pre-transition T660 safe idle: `MC01-READBACK-006` — PASS

The active continuation preserves the standing default wiring exclusions and
uses only T660-1 channel C to MIRcat DB9 pin 4. GUI qualification precedes any
SDK control. The manual shutter remains closed for the initial active GUI test;
opening it is not requested at this gate.

## Current operator action

Set the installed MIRcat interlock control to **ON/allow**. Leave the MIRcat
powered down, leave the manual shutter closed, and do not change wiring or any
other control yet. Report when the interlock is ON.

Operator confirmed the interlock ON on 2026-08-17. The MIRcat remained powered
down, the manual shutter remained closed, and wiring was unchanged.

## Released GUI configuration batch

With the shutter still closed and without arming or enabling emission:

1. Power on the MIRcat and open only the manufacturer GUI.
2. On **Laser Settings**, set QCL1 to Pulsed mode with 2,000,000 Hz, 150 ns,
   1000 mA, 19.00 C, and 30% duty cycle. Enable parameter logging.
3. Select **Use External Step Mode** under Process Trigger Modes and **Use
   External Trigger Mode** under Pulse Modes. Do not select or use any other
   process/pulse mode.
4. Click **Save Settings**.
5. On **Scan**, select **Step and Measure Mode** with cm-1 units, Start 1905.0,
   Stop 1934.0, Step Size 29.0, Number of Scans 1, Infinite cleared, and **Keep
   Laser On Between Steps** cleared.
6. Do not click ARM LASER, TURN EMISSION ON, or START SCAN yet.

Capture and attach two native screenshots:

- the complete Laser Settings page showing the saved process/pulse mode and
  laser parameters plus the right-side status panel;
- the complete Step and Measure page showing all sequence fields plus the
  right-side status panel.

Also report whether the GUI says `Connected to MIRcat S/N 10524` and whether
the right-side action still reads `ARM LASER` and emission remains off.

## Configuration acceptance

Accepted UTC: `2026-08-17T21:59:00.1239986Z`.

- GUI connected to MIRcat S/N 10524; interlock and key switch indicators valid.
- QCL1 Pulsed at 2,000,000 Hz, 150 ns, 1000 mA, 19.00 C, 30% duty cycle.
- Parameter logging enabled; External Step Mode and External Trigger Mode set.
- Step and Measure set to 1905.0 to 1934.0 cm-1, 29.0 cm-1 step, one scan,
  Infinite cleared, Keep Laser On Between Steps cleared.
- Emission remained off, QCL inactive, and the action label remained ARM LASER.

Evidence: `MC01-ACTIVE-GUI-001` and `MC01-ACTIVE-GUI-002`.

## Released arming observation

With the manual shutter still closed and without clicking START SCAN, click
**ARM LASER** once. Capture the complete page with the right-side status panel
after the GUI settles. Report the resulting button/action labels, Emission
indicator, Current QCL, Mode, and any message or fault exactly as shown.

Arming accepted UTC `2026-08-17T21:59:51.8524143Z`: the action changed to
DISARM LASER, interlock/key switch remained valid, emission remained off,
Current QCL and Mode remained N/A, and no fault appeared. Evidence:
`MC01-ACTIVE-GUI-003`.

## Released process-start observation

With the manual shutter still closed and all T660 outputs still disabled, click
**START SCAN** once. Do not click Manual Step and do not change any T660 state.
Allow the GUI to settle at its waiting state, then capture the complete Step and
Measure page with the status panel. Report any message/fault and the visible
Start/Stop/Manual Step controls, Emission, Current QCL, Mode, and wavenumber.

Waiting state accepted UTC `2026-08-17T22:01:00.2259909Z`: QCL1 active at
1905.0 cm-1, Pulsed 2 MHz/150 ns/1000 mA, Light Valid, GUI Emission indicator
asserted, and
Stop Scan available. The operator reported that the process was waiting for
the signal to move to the next wavenumber. Evidence: `MC01-ACTIVE-GUI-004`.

One T660-1 CHC `TRIG:EXECute` command was issued after readback confirmed CHC
ON, negative polarity, 10 ms width, 50 ohm termination, and every other channel
OFF. CHC and trigger source were immediately returned OFF. The T660 elapsed
shot counter remained zero in REM mode, so it is not accepted as proof that the
output pulse occurred and no retry is permitted until the GUI state is checked.

## Required post-command observation

Without clicking any GUI control, capture the complete current Scan page and
report whether it advanced to 1934.0 cm-1, completed, remained at 1905.0 cm-1,
or displayed a message/fault.

Corrected attempt `MC01-ACTIVE-REPEAT-001-RETRY1` explicitly started the T660
engine, read back CHC ON/negative/10 ms/50 ohm with all other channels OFF,
and produced a T660 counter transition 0 to 1 before returning STOP/OFF. The
GUI advanced exactly once to 1934.0 cm-1 and remained active awaiting Stop Scan.
Evidence: `MC01-ACTIVE-GUI-005`.

The asserted GUI indicator is a process/emission-gate state. The shutter was
closed, Pulse Mode was External Trigger, and T660-2 issued no laser-trigger
pulse; it is not evidence that an optical pulse occurred.

## Released terminal-stop observation

Click **STOP SCAN** once. Do not disarm separately and do not change settings.
After the GUI settles, capture the complete page with the status panel and
report the resulting emission, armed/disarmed action label, QCL active state,
current wavenumber, and any message/fault.

Repeat 1 stop accepted UTC `2026-08-17T22:06:25.6865282Z`: emission off,
laser remains armed, QCL inactive, Current QCL/Mode/Wavenumber N/A, and no
message or fault. Evidence: `MC01-ACTIVE-GUI-006`.

## Released repeat 2 start

With settings unchanged and the shutter still closed, click **START SCAN** once
to begin repeat 2. Wait until the GUI is stable at 1905.0 cm-1 awaiting the
external process signal, then report that waiting state. Do not issue a manual
step or any other control. Codex will capture HF2LI DIO while issuing the one
bounded T660 process command.

After that confirmation, the next released batch will power the MIRcat, acquire
exclusive GUI ownership, restore the saved MC-01 settings, save them, and
capture the requested pre-arm screenshots. T660 outputs remain disabled until
the GUI waiting state is accepted.
