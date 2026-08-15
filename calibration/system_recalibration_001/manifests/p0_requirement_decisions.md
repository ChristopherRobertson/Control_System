# P0 requirement decision register

Campaign: `system_recalibration_001`

Status: **ALL 21 DECISIONS RECORDED — NO ACTIVE DECISION**

This register is the single current list of unresolved requirements inherited
from P0. The dated P0 inventory and blocker table remain historical evidence;
they do not independently create new requirements after this register is
approved.

For each item, the user selected `KEEP`, `NARROW`, or `DISCARD`.
`KEEP` retains the stated requirement and claim consequence. `NARROW` records
the exact reduced evidence and claim. `DISCARD` removes the requirement and
records the resulting limitation. The user accepted the complete recommended
set on 2026-08-15.

## Requirement decisions

| Order | Decision ID | Requirement still requested | Current reason | Consequence if discarded | Recommended disposition | Status |
|---:|---|---|---|---|---|---|
| 1 | P0-D001 | Record the installed replacement reference-detector SIP model/serial and detector model/serial after arrival. | Associates DET-01/02/03/04 and all dual-channel results with the actual installed hardware. | Detector-specific calibration and normalization cannot be tied to a physical reference channel; affected phases remain blocked. | KEEP | DECIDED: KEEP — 2026-08-15 |
| 2 | P0-D002 | Retrieve PicoScope certificate identity, issuer, dates, covered range, uncertainty, and association to serial `10261`. | Supports traceable timebase, voltage, and timing uncertainty claims. | Use manufacturer specifications and campaign measurements only; label results documented nontraceable. | NARROW to fields that affect used ranges | DECIDED: NARROW — 2026-08-15 |
| 3 | P0-D003 | Retrieve the T660-1 certificate/equipment record and associate it with serial `00369`. | Supports device-specific delay/amplitude traceability beyond campaign measurement. | Retain measured campaign performance without a traceable device certificate. | DISCARD certificate retrieval; retain identity/settings and direct results | DECIDED: DISCARD — 2026-08-15 |
| 4 | P0-D004 | Retrieve the T660-2 certificate/equipment record and associate it with serial `00431`. | Supports device-specific delay/amplitude traceability beyond campaign measurement. | Retain measured campaign performance without a traceable device certificate. | DISCARD certificate retrieval; retain identity/settings and direct results | DECIDED: DISCARD — 2026-08-15 |
| 5 | P0-D005 | Retrieve the MIRcat certificate/equipment record and associate it with serial `10524`. | May support source/readback claims not established by SP-02 and QB-01. | Limit claims to campaign-measured spectral and operational performance. | DISCARD certificate retrieval; use SP-02/QB-01 results | DECIDED: DISCARD — 2026-08-15 |
| 6 | P0-D006 | Retrieve the Nd:YAG certificate/equipment record and associate it with `SL EX` serial `24366-1`. | May support source parameters not measured in PB-01. | Limit claims to campaign measurements and identified manufacturer specifications. | DISCARD certificate retrieval; use PB-01 results | DECIDED: DISCARD — 2026-08-15 |
| 7 | P0-D007 | Retrieve the OPO certificate/equipment record and associate it with `SLOPO PLUS` serial `24366-2`. | May support wavelength/output parameters not measured in PB-02. | Limit claims to campaign measurements and identified manufacturer specifications. | DISCARD certificate retrieval; use PB-02 results | DECIDED: DISCARD — 2026-08-15 |
| 8 | P0-D008 | Retrieve the HF2LI certificate/equipment record and associate it with `dev18500` / `HF2-DEV18500`. | Supports range, clock, gain, and demodulator uncertainty where relevant. | Use HF-01/HF-02 measurements and manufacturer specifications without traceable instrument calibration. | DISCARD certificate retrieval; use installed-chain qualification | DECIDED: DISCARD — 2026-08-15 |
| 9 | P0-D009 | Retrieve certificate/equipment records for the installed sample detector, SIP electronics, and power supply. | Supports detector/electronics response claims and separates manufacturer from measured quantities. | DET-01/02/03 measurements remain usable but device traceability is limited. | DISCARD certificate retrieval; retain exact identity/settings and direct results | DECIDED: DISCARD — 2026-08-15 |
| 10 | P0-D010 | Retrieve certificate/equipment records for the replacement reference detector, SIP electronics, and power supply. | Supports reference-channel response claims and DET-04 normalization provenance. | DET-01/02/03/04 may proceed only as measured nontraceable channel calibration after P0-D001 is satisfied. | DISCARD certificate retrieval; retain P0-D001 identity and direct results | DECIDED: DISCARD — 2026-08-15 |
| 11 | P0-D011 | Record the active MIRcat SDK DLL/product version and manufacturer-GUI version used for MC-01 and later MIRcat phases. | External-mode behavior and API semantics can be version dependent. | The configuration cannot be reproduced or bounded after software changes. | KEEP | DECIDED: KEEP — 2026-08-15 |
| 12 | P0-D012 | Record the active LabOne/HF2LI software and driver versions used for HF-01 and later acquisition phases. | Node behavior, streaming, and demodulator configuration can be version dependent. | The acquisition configuration cannot be reproduced or bounded after software changes. | KEEP | DECIDED: KEEP — 2026-08-15 |
| 13 | P0-D013 | Establish authoritative polystyrene feature values and uncertainties for the SV-02 alignment function. | Polystyrene is the canonical alignment standard in the theoretical notebook and characterization plan. | SV-02 can report only internally defined or nontraceable alignment; absolute known-value alignment is unsupported. | KEEP | DECIDED: KEEP — 2026-08-15 |
| 14 | P0-D014 | Establish polystyrene thickness/path length if absolute film absorbance will be claimed. | Needed for absolute forward absorbance, not for peak-position alignment. | Peak-position alignment remains valid; absolute film-absorbance claims are omitted. | DISCARD; absolute film-absorbance claim excluded | DECIDED: DISCARD — 2026-08-15 |
| 15 | P0-D015 | Establish authoritative Mylar reference spectrum/feature values and uncertainty for independent validation. | Mylar must independently test the frozen polystyrene correction. | Mylar can be illustrative only and cannot serve as an independent known-value validation. | KEEP | DECIDED: KEEP — 2026-08-15 |
| 16 | P0-D016 | Establish Mylar thickness tolerance and refractive-index/geometry inputs if quantitative absorbance or etalon modeling will be claimed. | Needed for absolute film response and interference prediction. | Retain position/shape validation only and omit absolute film/etalon claims. | DISCARD; quantitative film/etalon claims excluded | DECIDED: DISCARD — 2026-08-15 |
| 17 | P0-D017 | Establish temperature accuracy/uncertainty for the Freshliance TagPlus-TN or replace it with a qualified instrument. | Supports temperature-dependent spectral/source claims. | Retain temperature readings as uncalibrated observations. | DISCARD calibration requirement; retain observational readings | DECIDED: DISCARD — 2026-08-15 |
| 18 | P0-D018 | Establish relative-humidity accuracy/uncertainty for the Freshliance TagPlus-TN or replace it with a qualified instrument. | Supports any humidity-dependent stability claim. | Retain humidity readings as uncalibrated observations and omit humidity-corrected claims. | DISCARD calibration requirement; retain observational readings | DECIDED: DISCARD — 2026-08-15 |
| 19 | P0-D019 | Obtain manufacturer/model/part identities for the generic MIRcat DB9 board, DB9 cable, breakout wiring, and BNC interface beyond their stable campaign IDs. | Could improve replacement and topology records. Electrical behavior is measured in PT-01/MD-01/MSW-01. | Stable campaign IDs, photographs, wiring, and measured behavior remain the authority. | DISCARD | DECIDED: DISCARD — 2026-08-15 |
| 20 | P0-D020 | Obtain manufacturer/model/part identities and manual revision for the generic Nd:YAG two-wire probe/BNC adapter and installed DB9/BNC assembly. | Could improve replacement records; relevant timing behavior is measured directly. | Stable campaign IDs, photographs, wiring, and measured corrections remain the authority. | NARROW to wiring authority stable IDs photographs and measured corrections | DECIDED: NARROW — 2026-08-15 |
| 21 | P0-D021 | Define an explicit control-application, schema, and analysis-version convention for new phase records. | P0 found no packaged application version; later results require reproducible software identity. | Branch/dirty-file records alone may not distinguish analysis or schema behavior. | KEEP lightweight existing convention | DECIDED: KEEP — 2026-08-15 |

## Recorded decisions

| Decision ID | Disposition | Decision date | Rationale and resulting requirement |
|---|---|---|---|
| P0-D001 | KEEP | 2026-08-15 | The installed replacement reference-detector SIP and detector identities are required to associate DET-01 through DET-04 and later dual-channel results with the physical reference channel. Record the SIP model/serial and detector model/serial after arrival; no claim limitation was accepted. |
| P0-D002 | NARROW | 2026-08-15 | Record PicoScope serial `10261`, actual timebases/ranges used, and applicable manufacturer timebase/voltage accuracy. A formal certificate is not required. Voltage accuracy is included only where voltage is a reported quantitative result rather than a threshold diagnostic. |
| P0-D003–P0-D004 | DISCARD | 2026-08-15 | Do not retrieve T660 certificates. Retain the existing serial/firmware/configuration records and directly measured T1-01/T2-01 performance and uncertainty. |
| P0-D005 | DISCARD | 2026-08-15 | Do not retrieve a MIRcat certificate. SP-02 and QB-01 define the measured spectral and operating performance used by the thesis. |
| P0-D006–P0-D007 | DISCARD | 2026-08-15 | Do not retrieve Nd:YAG/OPO certificates. PB-01/PB-02 will report only performance measured at conditions required by the experimental claim grid plus clearly identified manufacturer-only bounds. |
| P0-D008 | DISCARD | 2026-08-15 | Do not retrieve an HF2LI certificate. HF-01/HF-02 and the installed detector-chain phases define accepted performance; no separate traceable absolute HF2LI-gain claim is made. |
| P0-D009–P0-D010 | DISCARD | 2026-08-15 | Do not retrieve detector/SIP/power-supply certificates. Exact installed identities/settings and DET-01 through DET-04 direct measurements remain required. |
| P0-D011–P0-D012 | KEEP | 2026-08-15 | Record MIRcat and LabOne/HF2LI software versions once per accepted configuration. No separate release or certification process is required. |
| P0-D013 | KEEP | 2026-08-15 | Retain authoritative polystyrene feature values and uncertainties for the SV-02 alignment fit. |
| P0-D014 | DISCARD | 2026-08-15 | Polystyrene thickness/path length is not required because absolute film absorbance is outside the approved claim scope. |
| P0-D015 | KEEP | 2026-08-15 | Retain authoritative Mylar features/reference uncertainty for independent validation of the frozen correction. |
| P0-D016 | DISCARD | 2026-08-15 | Mylar thickness/index/geometry is not required because absolute Mylar absorbance and quantitative etalon prediction are outside the approved claim scope. |
| P0-D017–P0-D018 | DISCARD | 2026-08-15 | Record temperature and humidity as observational conditions only. Do not apply environmental corrections or make calibrated environmental claims. |
| P0-D019 | DISCARD | 2026-08-15 | Stable component IDs photographs wiring and direct PT-01/MD-01/MSW-01 results replace manufacturer-part research. A replacement receives a new ID and must be requalified where material. |
| P0-D020 | NARROW | 2026-08-15 | Retain applicable wiring authority stable IDs photographs and measured adapter corrections; do not research manufacturer/part identity that does not affect the measured result. |
| P0-D021 | KEEP | 2026-08-15 | Use the existing phase schema/configuration IDs plus recorded software and analysis versions. No hash-matching or formal package-release gate is introduced. |

## P0 items already closed or transferred

| Historical item | Current disposition |
|---|---|
| P0-B01 repository-state baseline | Closed by the preserved P0 snapshot. It is not a recurring clean-tree gate. |
| P0-B02 fixed SMB/bulkhead handling and CLOCK splitter restoration | Closed by the corrected procedure and completed MS-01/MS-02 evidence. |
| P0-B05 T660 firmware identity | Closed by `readbacks/S0/t660_identity_firmware.json`. |
| P0-B08 unmarked electrical splitter performance | Closed for timing use by MS-02 campaign measurements. Manufacturer specifications are not substituted. |
| P0-B09 cable-length uncertainty and propagation delay | Removed as a P0 metadata requirement. Completed routes use direct measurements; future routes measure their own applicable delay. |
| P0-B10 detector response and sample-plane placement | Transferred to DET-03 and OP-01 as planned measurements, not unresolved P0 paperwork. |
| Missing raw data from the prior DIO mapping side experiment | Transferred to MD-01 qualification. The side observation is not promoted as campaign measurement evidence. |
| Exact prehardware snapshot wall-clock time | Historical date and timezone are sufficient; no execution or scientific claim depends on recovering a more precise timestamp. |

## Implementation rules

1. Only retained or narrowed requirements may create later work.
2. A discarded certificate or metadata request cannot reappear as a phase
   closeout gate without a new user-approved claim requirement.
3. Directly measured installed performance is reported with its actual
   reference basis, uncertainty, configuration, and validity envelope; it is
   not relabeled as accredited traceability.
4. Do not reacquire completed measurements solely because this decision set
   changed administrative requirements.
