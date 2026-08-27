# OM-01 saturation and beam-handling rules

Rule set: `OM01-SATURATION-v1`

- The 919P-010-16 manufacturer maximum average power is 10 W. This is a hard
  outer equipment limit, not the planned campaign operating point.
- The documented maximum average power density is 28 kW/cm2. Pulse-duration
  dependent energy-density limits also apply; OM-01 will not infer compliance
  from average power alone for an unknown focused or pulsed beam.
- For damage-threshold comparison, multiply Gaussian-beam power/energy density
  by 2 and hot-spot beams by 3 as directed by the sensor datasheet.
- The full beam must be centered within the 16 mm active diameter with a
  documented clipping margin. Never intentionally focus on the absorber.
- For the representative 540 nm OM-01 check, the operator confirmed that the
  complete visible beam fit within the 8 mm sensor radius. This supports binary
  total-power capture only; it is not a quantitative diameter or fluence
  measurement.
- `PM:PWS?` status must report detector present, no range transition, and no
  overrange. Any overrange, saturation indication, unstable thermal response,
  unexpected output, or ambiguous beam size stops acquisition.
- At 355 nm, the source path must also pass its wavelength-specific beam and
  residual-harmonic safety review before any exposure. The 355 nm condition is
  OPO drive only and is never treated as a sample pump claim.
- No attenuator is currently qualified. Introducing one belongs to ATT-01 and
  requires separate authorization; it cannot be used silently to rescue an
  OM-01 range or saturation failure.
