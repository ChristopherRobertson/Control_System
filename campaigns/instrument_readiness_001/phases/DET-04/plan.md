# DET-04 — installed sample-reference balance and normalization calibration

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `DET-02, ATT-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 19. DET-04 — installed sample/reference optical-balance and normalization calibration

Combine ATT-01's component/port measurements with DET-02's separate channel
response functions in the final installed sample/reference optical paths.
Measure power at the sample and reference detector planes separately under the
same source condition. Establish the end-to-end optical balance, detector-
electronics balance, and measured system baseline ratio without assuming the
splitter is 50/50.

Use the same merged probe anchors and low/high expected powers retained in
DET-02, with shared points measured once. Use only the polarization and
alignment states that survive CH-00, and include one controlled realignment/
revisit. If detector or branch exchange is safe and practical, use it once as
a separation/closure test; otherwise use the same qualified transfer detector
sequentially at both detector planes and retain the placement/repeatability
uncertainty.

Mandatory closeout deliverables:

- Stable identities for splitter input/output ports, all downstream optics,
  detector planes, detectors, amplifiers, HF2LI inputs, meter heads, mounts,
  polarization state, and alignment configuration.
- Synchronized incident, sample-plane detector-path, and reference-plane
  detector-path optical readings plus simultaneous electrical outputs where
  possible; native raw data, backgrounds, settings, and accepted/rejected
  ledger.
- Wavelength-dependent `P_sample`, `P_reference`, optical balance
  `B_opt = P_sample/P_reference`, detector/electronics balance
  `B_det = G_sample/G_reference`, and system baseline ratio
  `B_sys = V_sample/V_reference`, with the closure check
  `B_sys ~= B_opt * B_det` and defined acceptance limits.
- Linearity and saturation checks at both detector planes across the actual
  unequal-power range; split-ratio and balance dependence on power,
  polarization, alignment, and time; revisit/realignment drift; covariance and
  full uncertainty budgets.
- A machine-readable normalization table versus wavenumber with interpolation
  and extrapolation limits. It must support the background-normalized equation
  `A = -log10[(S/R)/(S0/R0)]` (and the separately defined transient estimator)
  without forcing the two raw powers or voltages to be equal.
- A stable `detector_balance_bundle.json` correction ID, recommended operating
  margins, revalidation triggers after splitter/optic movement, detector or
  amplifier replacement, gain/range changes, material realignment, or drift
  beyond the accepted limit, plus safe restoration.

DET-04 is a prerequisite for quantitative dual-detector spectral calibration,
normalization, platform sensitivity, and later biological absorbance claims.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
