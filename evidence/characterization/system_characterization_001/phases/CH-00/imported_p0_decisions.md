# Imported final P0 decisions affecting characterization

Source: `calibration/system_recalibration_001/manifests/p0_requirement_decisions.md`

- `P0-D001 KEEP`, satisfied 2026-08-17: installed replacement reference chain
  recorded as VIGO `SIP-DC-250M` serial `445161066` with `PVM-10.6-1x1`
  detector serial `21834`. DET-01 through DET-04 performance remains pending.
- `P0-D002 NARROW`: retain PicoScope serial 10261, actual ranges/timebases, and
  applicable manufacturer accuracy; no formal certificate gate.
- `P0-D003`–`D010 DISCARD/NARROW`: do not reintroduce discarded device,
  detector, or accessory certificate research; use exact identity, settings,
  direct results, and applicable manufacturer specifications.
- `P0-D011`–`D012 KEEP`: record MIRcat GUI/SDK and LabOne/HF2LI versions for
  accepted configurations.
- `P0-D013 KEEP`: authoritative polystyrene features and uncertainty are
  required for the SV-02 alignment fit.
- `P0-D014 DISCARD`: no absolute polystyrene film-absorbance claim.
- `P0-D015 KEEP`: authoritative Mylar features/reference uncertainty are
  required for independent validation.
- `P0-D016 DISCARD`: no absolute Mylar absorbance or quantitative etalon claim.
- `P0-D017`–`D018 DISCARD`: temperature and humidity remain observational.
- `P0-D019 DISCARD`: stable MIRcat board/cable IDs, wiring, photographs, and
  measured behavior replace manufacturer-part research.
- `P0-D020 NARROW`: retain Nd:YAG wiring authority, stable IDs, photographs,
  and measured adapter corrections only.
- `P0-D021 KEEP`: use existing schema/configuration IDs and explicit software
  and analysis versions, with no hash-matching gate.

All discarded requirements stay excluded unless a new claim requirement is
separately approved.
