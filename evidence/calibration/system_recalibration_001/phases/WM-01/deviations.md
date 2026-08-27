# WM-01 deviations and authorized plan changes

## WM01-DEV-0001 - rear-panel photograph omitted

- Authorized UTC: `2026-08-21T16:17:35.308Z`
- Authorized by: operator
- Change: the WaveMaster rear-panel photograph is not required.
- Plan update: `plans/campaign_sequence.md` now treats the rear-panel image as
  optional when installed connections are otherwise identified.
- Measurement impact: none. Device, straight-through cable, FTDI adapter,
  power state, RS-232 behavior, and restoration evidence remain required.
- Safety impact: none; no connection was disturbed to obtain a photograph.

## WM01-DEV-0002 - cable and adapter photographs omitted

- Authorized UTC: `2026-08-21T16:23:50.764Z`
- Authorized by: operator
- Change: photographs of the USB-to-RS-232 cable and FTDI adapter are not
  required.
- Plan update: `plans/campaign_sequence.md` now treats these images as optional
  when configuration, installed-driver, registered-adapter, and live serial
  evidence identify the connection.
- Measurement impact: none. Straight-through behavior, RTS/CTS operation,
  registered FTDI identity, exclusive ownership, reconnect, and restoration
  evidence remain required.
