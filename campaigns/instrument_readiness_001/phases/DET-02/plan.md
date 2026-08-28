# DET-02 — illuminated detector and electronics transfer performance

Campaign: `instrument-readiness-001`  
Domain: `calibration`  
Registry status: `planned`  
Required dependencies: `DET-01, ATT-01, HF-01.1`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### 17. DET-02 — illuminated detector/electronics transfer performance

Using OM-01/ATT-01-qualified metrology and separately authorized illumination,
measure each detector/amplifier/HF2LI channel's response against independently
measured incident power: gain or responsivity, linearity, saturation, SNR,
noise, and wavelength dependence over the unequal power ranges expected after
the installed splitter. Use a common calibrated transfer detector/source or an
approved branch/detector interchange where practical to separate detector-
electronics response from optical-path transmission. Do not repeat DET-01 dark
acquisitions; import their result bundle.

The minimum grid is the merged CH-00 probe-anchor set: one Mylar-carbonyl
anchor, the two HRP-C-CO band anchors, the MbCO A1/upper diagnostic anchor, and
only the off-band point needed by the biological controls. Merge coincident
anchors. At each retained wavelength use the lowest and highest expected
incident powers with three readings per channel and one revisit; add a midpoint
only if the predeclared fit-residual rule fails.

Mandatory closeout deliverables: frozen illumination budget and conditions,
raw detector and optical-meter data, incident-power reference planes,
attenuation/transfer IDs, per-channel response curves, fit residuals,
saturation and recommended operating margins, detector-gain ratio with
uncertainty, accepted/rejected ledger, and safe restoration. Identify which
part of the channel mismatch belongs to detector/electronics response rather
than optical splitting. Report installed-chain response to the qualified
available power meter; accredited absolute detector responsivity is outside
scope.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
