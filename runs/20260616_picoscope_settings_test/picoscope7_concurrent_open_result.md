# PicoScope 7 Concurrent Access Check

timestamp_local: 2026-06-16T06:21:57-07:00

## PicoScope 7 State

PicoScope 7 was open and held the connected unit:

```text
ProcessName: PicoScope
MainWindowTitle: PicoScope 7 T&M  - PicoScope 5244D [10261/0071] - 200 MHz 1 GS/s FlexRes
```

## SDK Test Result

Command:

```text
.venv/Scripts/python.exe tests/hardware_checks/check_picoscope_settings_apply.py --operator "Codex" --confirm-real-hardware
```

Result:

```text
ps5000aOpenUnit -> 3
ps5000aOpenUnit failed with Pico status 3 (PICO_NOT_FOUND)
```

No PicoScope setting commands were sent because the SDK could not open the unit
while PicoScope 7 had it open.

## Conclusion

The manufacturer UI and the current Python PicoSDK control path cannot use the
same PicoScope 5244D at the same time. The application will need its own scope
view if users must see live PicoScope data while workflow code controls the
instrument.
