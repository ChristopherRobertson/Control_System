# OM-01 Newport 1918-R / 919P-010-16 method - qualified bounded

Method ID: `OM01-POWER-NEWPORT-v1`

## Applicable configuration

- Meter: Newport 1918-R serial `15879`, firmware `v1.0.2 04/06/12`.
- Sensor: Newport 919P-010-16 serial `161791`, broadband thermopile,
  16 mm active diameter, 2.01 cm2 active area.
- Interface: Newport USB driver DLL 5.0.8 and
  `NEWPORT1918-PY3-QUERY-v1`.
- Intended quantity: average optical power in W. Direct pulse-energy
  distributions and calibrated peak power are excluded.

## Pre-use and placement rules

1. Confirm identity, connector integrity, absorber condition, and exclusive
   USB ownership. Shield the thermopile from airflow and nearby heat sources.
2. Define the measurement plane and mount position before exposure. Center the
   complete beam within the active area; do not focus on the absorber.
3. Review total-power and power-density bounds before placement. Use the
   manufacturer's Gaussian factor of 2 or hot-spot factor of 3 for damage-limit
   comparisons when applicable.
4. Allow meter/head thermal stabilization and freeze the wait criterion before
   collecting accepted data. The manufacturer's nominal rise time is 0.8 s,
   but accepted dwell must be established from observed stability rather than
   using 0.8 s alone.

## Background and zero

- Record an uncovered ambient/background reading with the source inhibited.
- Cover the detector with opaque non-contact material; never use a hand.
- Record the covered dark reading before changing the stored zero.
- Store/enable zero only after the covered reading is stable, then query and
  record the resulting zero value and status.
- Repeat background/zero after a material thermal, airflow, placement, range,
  or session change and at the final revisit.

## Wavelength, range, and sampling

- Set the actual retained wavelength in nm so the meter uses the sensor EEPROM
  responsivity table. Record setpoint, readback, and queried responsivity.
- Use DC Continuous for average power unless a documented failure requires a
  different mode. Freeze analog/digital filtering and sampling before the
  first accepted endpoint.
- The Surelite Nd:YAG drives the Horizon OPO at 355 nm. Treat 532 nm as an OPO
  signal-output wavelength, not as the direct Nd:YAG pump path used in this
  apparatus.
- Surelite and Horizon values stated in mJ or as `Energy` are per-pulse
  quantities. At a verified repetition rate, derive mean pulse energy only as
  `E_mean = P_average / f_rep`; this is not a pulse-energy distribution or a
  calibrated peak-power measurement.
- Select one manual range per endpoint after an autorange preview, then freeze
  it for its three accepted repeats and revisit. Status-aware `PM:PWS?` reads
  must show detector present, no ranging transition, and no overrange.
- Query `PM:MIN:Power?` and `PM:MAX:Power?` for every actually used range.

## Endpoint series

OM-01 qualifies the measurement chain; it does not select or characterize
laser operating points. The experiment requirements/CH-00 grid determine the
wavelength families and expected power envelope. PB-01/PB-02 and QB-01 later
select and characterize the exact Nd:YAG/OPO delays, MIRcat currents, pulse
parameters, and delivered powers. Do not repeat a dense source-control sweep
merely to qualify the meter.

- Each accepted reading is an automated fixed-duration window after a frozen
  settling interval; retain all samples and report mean, standard deviation,
  range, and coefficient of variation rather than a visual midpoint estimate.
- Any emitted OM-01 range/linearity check uses only a bounded representative
  low/high meter reading within the requirement-derived envelope. Its purpose
  is meter behavior, not selection or validation of a laser control setting.
- The known approximately 245 us Nd:YAG/OPO maximum and the prior 632 nm sweep
  may guide safe range selection, but they are not OM-01 operating points.
- MIRcat low-current instability is a QB-01 source-envelope issue. OM-01 must
  preserve observed variability in any representative check, but it does not
  determine the minimum usable current.
- A midpoint or additional control setting is permitted only after a
  predeclared repeatability, stability, or interpolation criterion fails.
  Rejected acquisitions remain preserved and do not authorize unbounded extra
  exposures.

The meter residual, repeatability, and revisit tolerances must be frozen after
the expected reading envelope is bounded and before any representative
emission. Saturation, status, background, placement, and safe-idle failures
stop the series immediately.

The operator's earlier 632 nm, 200--300 us delay assessment is reconnaissance
only: it located an approximate maximum near 245 us at about 75 mW and a value
below 35 mW at 300 us, but it used unfiltered display extrema and an estimated
visual midpoint over about 10 s. It is not accepted quantitative OM-01 data and
need not be repeated unless 632 nm or that delay-response relationship supports
a retained thesis claim.

For an OPO output, the wavelength entered in the power meter is a detector-
responsivity correction, not a spectral filter. Unless spectral purity is
independently established, report the result as total incident OPO-output power
indicated at the selected meter wavelength. Do not label it as power solely in
that wavelength component. Any visible halo must be included in the spatial-
containment observation, and wavelength-specific power or dose claims require
spectral characterization or qualified wavelength-selective optics downstream.
