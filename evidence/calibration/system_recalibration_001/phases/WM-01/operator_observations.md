# WM-01 operator observations

Physical states are appended only after the operator reports each observation.

## WM01-OBS-0001 - initial laser state

- Recorded UTC: `2026-08-21T16:09:01.126Z`
- Observation source: operator
- Operator report: "All lasers are shuttered"
- Recorded state: all lasers shuttered
- Scope note: no claim is made here about electrical trigger inhibition,
  shutter integrity, beam absence at a reference plane, or WaveMaster probe
  placement; those require their own evidence.

## WM01-OBS-0002 - installed label identity

- Recorded UTC: `2026-08-21T16:13:14.707Z`
- Observation source: operator report plus image inspection
- Operator report: "Its W0 339"
- Visible catalog number: `33-2650`
- Visible label serial: `W0 339` (the middle character is recorded as the
  digit zero)
- Electronic serial expected from prerequisite intake: `W0339`
- Disposition: label and electronic identities remain separate native
  observations; spacing is not normalized and identity agreement will be
  assessed after the WM-01 electronic query.
- Image: `docs/WaveMaster/WaveMaster_Serial.jpg`

## WM01-OBS-0003 - front panel

- Recorded UTC: `2026-08-21T16:16:42.230Z`
- Observation source: image inspection
- Visible equipment: Coherent WaveMaster laser wavelength meter front panel
- Visible controls: ON/OFF, backlight, contrast, AUTOCAL, UNITS, MODE, and
  pulse-received control/indicator; intensity meter and fibre connector are
  visible.
- Display: energized, with a visually apparent non-numeric status field; the
  exact status and settings are not transcribed from this low-contrast image
  and will be established through native serial readbacks.
- Image: `docs/WaveMaster/WaveMaster_Front_Panel.jpg`

## WM01-OBS-0004 - authorized rear-panel-photo omission

- Recorded UTC: `2026-08-21T16:17:35.308Z`
- Authorization source: direct operator instruction
- Operator instruction: "skip this, it is not necessary. I am authorizing
  this change and any update to the phase documentation necessary to remove
  this requirement."
- Disposition: rear-panel photograph omitted and removed as a mandatory WM-01
  deliverable. Installed RS-232 and power connection identity remains subject
  to cable/adapter, configuration, and electronic evidence.

## WM01-OBS-0005 - sampling probe and acceptance setting

- Recorded UTC: `2026-08-21T16:21:40.222Z`
- Observation source: operator report plus image inspection
- Operator report: acceptance switch is set to `wide`
- Visible configuration: Coherent sampling probe body, selector, captive orange
  fibre, sampling nose, and post mount
- Current placement classification: photographed on its mount; not yet recorded
  as placed in a laser beam or at the retained WM-01 reference plane
- Image: `docs/WaveMaster/WaveMaster_Probe.jpg`

## WM01-OBS-0006 - authorized cable/adapter-photo omission

- Recorded UTC: `2026-08-21T16:23:50.764Z`
- Authorization source: direct operator instruction
- Operator observation: the connection is one USB-to-RS-232 cable and has
  already been confirmed working
- Disposition: cable and adapter photographs omitted and removed as mandatory
  WM-01 deliverables. Registered FTDI adapter/driver identity and live WM-01
  communication evidence remain required.

## WM01-OBS-0007 - retained optical placement

- Recorded UTC: `2026-08-21T16:44:21.293Z`
- Observation source: operator
- Operator report: "Probe has been positioned and beam dump/block has been
  installed downstream of the beamline."
- Reference plane: temporary OPO-output reference plane immediately after the
  OPO output shutter and before retained attenuation or splitting optics
- Probe geometry: approximately normal to intended 540 nm beam, acceptance
  setting `wide`, installed on the photographed mount
- Downstream containment: beam dump/block installed downstream
- Qualification scope: placement evidence only; no emission or wavelength
  result is inferred from this observation

## WM01-OBS-0008 - local front-panel control

- Recorded UTC: `2026-08-21T16:46:03.595Z`
- Observation source: operator
- Action: operator pressed the front-panel BACKLIGHT button once after the
  native `LOC$` acknowledgement
- Operator observation: "yes it changes"
- Result: PASS - local front-panel control responds
- Restoration status: backlight differs from its prior state; return action
  pending

## WM01-OBS-0009 - backlight restoration

- Recorded UTC: `2026-08-21T16:46:23.272Z`
- Observation source: operator
- Action: operator pressed BACKLIGHT a second time
- Operator observation: "its back on now"
- Result: prior illuminated backlight state restored; no measurement-setting
  control was pressed

## WM01-OBS-0010 - thermal-stability interval

- Recorded UTC: `2026-08-21T16:46:45.477Z`
- Observation source: operator
- Operator report: "it was left on overnight"
- Classification: `THERMALLY_STABILIZED_GE_4H_OPERATOR_REPORTED`
- Basis: continuous overnight operation exceeds the manufacturer guidance of
  approximately four hours for best thermal stability

## WM01-OBS-0011 - source prepared at 540 nm while shuttered

- Recorded UTC: `2026-08-21T16:48:49.251Z`
- Observation source: operator
- OPO commanded/displayed output wavelength: `540 nm`
- OPO state: stable; no errors or faults reported
- Nd:YAG state: ready and warmed up
- Optical state: output remains shuttered; this is a source setpoint/status
  observation and not a WaveMaster wavelength measurement

## WM01-OBS-0012 - 10 Hz source timing active while shuttered

- Recorded UTC: `2026-08-21T16:51:39.463Z`
- Observation source: operator
- Workflow: `Nd:YAG 10 Hz Alignment`
- Firing state: continuous at `10 Hz`
- FIRE-to-Q-SWITCH delay: fixed provisional `250 us`
- Optical state: Nd:YAG and OPO output shutters remain closed
- Scope limitation: no delay scan or optimization was performed; ATT-01 delay
  qualification remains unauthorized

## WM01-OBS-0013 - Nd:YAG shutter opened

- Recorded UTC: `2026-08-21T16:52:10.353Z`
- Observation source: operator
- Nd:YAG shutter: open
- Nd:YAG firing: continuous `10 Hz`
- Operator result: no issue reported
- OPO output shutter: remains closed

## WM01-OBS-0014 - first illuminated attempt and no response

- Observation source: operator plus native WaveMaster capture
- OPO output shutter: opened for the first bounded WM-01 attempt
- Operator observation: intensity indicator showed no movement and appeared to
  receive no probe signal
- Additional operator action: intensity control rotated from the furthest `-`
  position through its full range to the furthest `+` position; no indicator
  change was observed
- Native result: five of five `VAL$` replies were `NO SIGNAL`
- Configuration departure: `UNI?` returned `W` rather than required air-nm
  `A`; acquisition `WM01-ACQ-0005` is rejected for quantitative use
- Operator-reported cause, recorded `2026-08-21T16:59:05.808Z`: the UNITS
  button was pressed accidentally
- Recovery: air-nanometre units `A` restored and verified electronically while
  all shutters were closed

## WM01-OBS-0015 - shutter recovery after no-signal attempt

- Recorded UTC: `2026-08-21T16:58:33.055Z`
- Observation source: operator
- Operator report: "shutters are closed"
- Recorded safe state: all laser shutters closed

## WM01-OBS-0016 - safe idle after probe-assembly discovery

- Recorded UTC: `2026-08-21T17:10:36.559Z`
- Observation source: operator
- Nd:YAG workflow: safe idle
- Laser shutters: all closed
- Probe assembly history: probe was found dismantled before WM-01
- Present component: 45-degree glass sampling plate
- Absent components: 12.7 mm filter/diffuser and plastic retaining washer
- Manual interpretation: the filter/diffuser is optional and not supplied;
  absence does not by itself fail the probe when no optional filter/diffuser is
  installed. Plate seating and nosepiece orientation require verification
  before further emission.

## WM01-OBS-0017 - sampling plate condition

- Recorded UTC: `2026-08-21T17:11:16.668Z`
- Observation source: operator
- Glass sampling plate: secure
- Damage/looseness: none reported
- Required next state: orient the 90-degree sampling geometry so the small
  plate reflection enters the probe body and the transmitted main beam reaches
  the downstream dump

## WM01-OBS-0018 - unplanned red-source probe/connector diagnostic

- Recorded UTC: `2026-08-21T17:56:43.878Z`
- Observation source: operator
- Source: MIRcat red alignment laser; exact commanded wavelength/readback and
  native serial transcript not captured
- Probe-orientation result: operator visually confirmed the nose directs light
  into the probe and through the fibre; light was observed exiting the
  disconnected instrument end
- Wide acceptance: `MULTI-LINE` at all tried intensity-control positions
- Narrow acceptance: fluctuated between `635.549 nm` and `MULTI-LINE`
- Narrow/low-indication condition: a visually solid numeric display was
  observed when intensity was reduced until the beam just registered
- Mechanical sensitivity: jostling the fibre or slightly rotating the
  connector returned `MULTI-LINE`
- Operator hypothesis: WaveMaster connection port may be loose or damaged
- Disposition: diagnostic only and rejected for quantitative use. `MULTI-LINE`
  is non-numeric; `635.549 nm` is not retained as an accepted wavelength
  because it lacks native time-tag capture and is connector-position dependent.
  This does not qualify the 540 nm path or infer spectral-power fractions.
- Safety note: the fibre output was visually observed while disconnected;
  source emission must be off before any further connector inspection.

## WM01-OBS-0019 - connector inspection and 540 nm failure

- Recorded UTC: `2026-08-21T18:12:38.181Z`
- Observation source: operator
- Fibre end and receptacle: no noticeable visible damage
- Receptacle body: slight motion relative to front panel
- OPO commanded condition: 540 nm, pulsed WaveMaster mode
- WaveMaster response: zero intensity for all tried receptacle orientations
- Fibre continuity observation: light again visually observed at the
  disconnected probe-fibre end
- Service availability: operator reports Coherent no longer services this model
- Disposition: STOP further installed-WaveMaster illumination trials. Gross
  fibre continuity does not qualify instrument coupling. The moving receptacle,
  mechanically dependent red diagnostic, and absent 540 nm response prevent
  installed working-reference qualification.
- Safety limitation: direct visual observation of an emitting fibre end must
  not be repeated.
