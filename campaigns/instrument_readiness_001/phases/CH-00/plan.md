# CH-00 — claim scope and calibration-import freeze

Campaign: `instrument-readiness-001`  
Domain: `characterization`  
Registry status: `complete`
Required dependencies: `P0, TR-01`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
`../../requirements.md`.

## Phase-specific procedure and deliverables


### CH-00 — claim, scope, and calibration-import freeze

Status: **COMPLETE — PASS; ANALYSIS-ONLY CLOSEOUT; PB-02 NOT AUTHORIZED**

Define the claims the thesis and downstream experiments will make, the tested operating
envelope needed to support them, and the calibration dependencies for every
reported quantity. This phase is analysis-only.

The mandatory grid is the smallest union of the three verified briefs:

- one probe-only continuous-sweep window around the specimen-matched Mylar PET
  carbonyl feature and the polystyrene features needed to freeze its correction;
- the combined 1885-1980 cm^-1 biological probe region, reduced to the two
  HRP-C-CO bands, the MbCO A1/upper diagnostic band, and only the off-band
  anchors required by the controls;
- direct 532 nm pumping for HRP-C-CO;
- 355 nm only as the drive required to produce the 540 nm OPO pump for MbCO;
- 540 nm OPO pumping for MbCO; and
- exactly two acquisition topologies: probe-only continuous sweep and finite
  rare-pump fixed-wavenumber/recovery acquisition.

Shared anchors and settings are characterized once. The broad 1650-2050 cm^-1
probe survey, direct 1064 nm sample-path claims, broad OPO tuning, pulse-energy
distributions, peak power, and optional mechanistic/quantum-yield extensions
are excluded unless CH-00 is formally reopened before hardware begins.

Mandatory deliverables before CH-00 closes:

- Claim-to-measurement matrix distinguishing manufacturer specification,
  measured result, derived result, and unvalidated capability.
- Frozen wavelength/power/scan/delay test grid with rationale covering every
  retained condition in the three-brief union. Broader-range claims and their
  representative points remain excluded unless CH-00 is formally reopened.
- Calibration dependency graph and `calibration_links.csv` populated with the
  required bundle/quantity IDs and validity states.
- Imported final P0 requirement decisions that affect reference bases,
  spectral standards, observational environmental records, or installed
  detector identity.
- Equipment/sample/component registries, configuration-ID method, acceptance
  criteria, uncertainty plan, and exposure/shot-budget policy.

#### Retained permanent OPO-iris configuration boundary

CH-00 remains complete and is not reacquired or rewritten. The iris does not
change its wavelength, claim, biological-sample, or acquisition-topology
evidence. All unexecuted phases treat the ATT-01-qualified iris and the
WM-01-qualified wavelength working reference as required parts of the final
OPO-540 configuration. The characterized wavelength remains 540 nm only.
Observed X/Y beam-center motion elsewhere in the OPO tuning range is a reason
not to extrapolate this configuration: any future OPO wavelength requires a
separately approved wavelength-specific iris/centroid qualification.

Every unexecuted downstream phase uses one biological pump path:
permanent-iris OPO 540 nm, used by HRP-C-CO first and MbCO second. Completed
CH-00 evidence remains unchanged and is not repeated. The shared instrument
configuration is characterized once; HRP and MbCO retain separate sample-
specific dose, absorbance, overlap, photolysis, damage, and kinetics pilots.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
