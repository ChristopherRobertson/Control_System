# Daylight Solutions DB9 process-trigger correspondence

Source organization: Daylight Solutions  
Responding group: Engineering team  
Recorded in repository: 2026-07-23 (America/Los_Angeles)  
Record type: User-supplied transcription of manufacturer correspondence

The technical information below is preserved as supplied by the operator.

> Our engineering team has reviewed and you can use External Process Trigger
> mode to trigger each channel of the scan using pin 4 on the DB-9 connector.
> You would set the system to External Process Trigger mode and apply a short
> pulse (low) on pin 4 to apply the trigger. You should normally pull pin 4 high
> and only set it momentarily low (~1-100 ms is enough) to trigger the scan on
> the next channel.
>
> Below is a table that describes the pins on the DB-9 connector.
>
> | Pin | Direction | Name | Description |
> |---:|:---:|---|---|
> | 1 | Out | Scan Direction | During a scan, toggles high or low when the scan changes direction |
> | 2 | Out | Tuned / Sweep Active | In single tune or step scan modes, goes high when the system is at the target wavelength, and low when it is tuning to a wavelength. In sweep scan mode, this goes high when a channel is actively sweeping and goes low when the system is transitioning from one channel to the next. |
> | 3 | Out | Wavelength Trigger | In sweep scan mode, the system can generate a short digital pulse on this pin when the sweep crosses each wavelength trigger target wavelength. |
> | 4 | In | Process Trigger | Active low signal that triggers the system to go to the next step in a scan. |
> | 5 | In | Reserved | |
> | 6 | In | Interlock | Electronic interlock used for laser safety. This should be pulled low to allow firing and be set high to inhibit firing. Note: if using this signal the interlock terminal should be disconnected from the MIRcat interlock BNC connector. |
> | 7 | Out | Ground | |
> | 8 | In | On/Off Control | Active low signal to turn the system on or off. This should be momentarily pulled low to initiate a system power on or off. This can also be used to forcibly power the system off in the unlikely event of a system hang by holding low for approximately 5 seconds. |
> | 9 | Out | Ground | |
>
> You will want to use pins 1-3 to get wavelength information from the scan.
> The output will look something like this (scan direction may be inverted
> depending on the direction you are scanning). Scan direction indicates the
> start of each scan overall. Sweep Active is high when each individual channel
> is sweeping during its portion of the scan. WL triggers will be generated once
> the actual position of the motion system crosses each wavelength for which a
> trigger should be generated. Using these signals, you can synchronize the
> measured data with the wavelength of the laser.
>
> The laser trigger mode (in this case, you want to use External Trigger) is
> independent of the process trigger mode. So, you can also use External Trigger
> mode. In this case, the Trigger Out on the BNC connector is an electrical
> representation of the laser pulsing. So, the electrical signal you get out
> should look like the laser on/off pulsing.
>
> Please try this in the GUI first to make sure you can get it working. Once it
> is working, then you can try using the SDK. You do not need to use Advanced
> Sweep Scan for this (so should just use StartSweepScan()).

## Operational interpretation for this repository

- DB9 pin 4 is normally high and is triggered by a nominal 10 ms low pulse,
  within the manufacturer-provided 1–100 ms range.
- DB9 pin 5 is reserved for Laser Output On/Off in the installed board
  documentation and remains disconnected.
- Under the installed topology, DB9 pins 6 and 8 are unused and unwired.
- The repository phrase `default wiring restored` also includes T660-1 channel
  D disconnected and unused, plus DB9 pin 5 disconnected and pins 6/8
  unused/unwired. These standing conditions are not re-asked unless the
  operator explicitly reports a change; see `docs/default_wiring_state.md`.
- The room interlock remains authoritative; this campaign does not use DB9 pin
  6 and does not disconnect or replace the MIRcat interlock BNC.
- External Process Trigger must be qualified in the manufacturer GUI before SDK
  automation, using the campaign's bounded MC-01 procedure.
- Normal sweep control uses `StartSweepScan()`; Advanced Sweep Scan is not
  required.
