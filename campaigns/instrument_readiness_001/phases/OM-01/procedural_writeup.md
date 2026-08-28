# OM-01 — optical metrology readiness and transfer standards: procedural writeup

## Document control

| Field | Value |
| --- | --- |
| Canonical campaign ID | `instrument-readiness-001` |
| Retained execution campaign | `system_recalibration_001` |
| Phase ID | `OM-01` |
| Phase run ID | `system_recalibration_001_OM-01_001` |
| Domain | Calibration/optical metrology |
| Scientific disposition | `PASS — COMPLETE, QUALIFIED BOUNDED` |
| Documentation status | `DRAFT_RECONSTRUCTION_REVIEW_PENDING` |
| Preparation mode | `RETROSPECTIVE_EVIDENCE_RECONSTRUCTION` |
| Operator | Christopher Robertson |
| Draft author | Codex, from retained repository evidence |
| Reviewer | Not assigned; review remains pending. |
| Document version | `0.1.0` |
| Execution interval | Exact UTC start/end remain in the acquisition and operator records and were not inferred here. |
| Draft date | 2026-08-27 |
| Governing records | `plan.md`; `run_record.md`; `phase_manifest.json`; `final_report.md` |
| Output bundle | `CAL-system_recalibration_001-OM01-v1` (phase-local; not canonically promoted) |

## Executive synopsis

OM-01 qualified a Newport 1918-R power meter, serial `15879`, with a Newport
919P-010-16 sensor, serial `161791`, as a bounded working reference for average-
power measurements. The procedure combined identity and USB checks, sensor
inspection, a documented temporary dark cover, stored-zero and ambient checks,
manual range/wavelength control, shutter response, repeated illuminated windows,
and restoration.

At a representative OPO condition with the meter set to 540 nm, three 30-reading
means were 83.053, 84.414, and 85.478 mW. Their mean was 84.315 mW and their
between-window coefficient of variation was 1.44%. The provisional expanded
uncertainty was 4.34% at coverage factor 2, excluding unknown mixed-spectrum
bias. The value is total incident OPO-output power indicated using the meter's
540 nm responsivity setting—not spectrally isolated 540 nm power.

## 1. Purpose — WHY

Later source, attenuation, detector, geometry, and overlap phases require a
repeatable average-power reference and explicit rules for dark correction,
wavelength setting, saturation, and spatial containment. TR-01 identified the
available meter/sensor chain but did not qualify its installed behavior. OM-01
tested that chain while bounding what it could and could not support.

The acceptance objective was communication and identity agreement, acceptable
sensor condition, stable dark/zero behavior, valid range/status, an installed
repeatability demonstration, shutter discrimination, explicit wavelength and
saturation rules, bounded spatial/polarization applicability, and safe
restoration. Pulse-energy distribution, peak power, quantitative beam geometry,
spectral purity, and final sample-plane transfer were excluded.

## 2. Procedure performed — HOW

### 2.1 Equipment and configuration

The meter/sensor identity was compared with retained documentary evidence and
live device readback through the Python USB interface. Manual range 0 and the
540 nm wavelength setting were used for the representative OPO measurement. The
sensor plane and applicability limits are defined in
`reference_planes_and_applicability.md`; saturation and handling rules are in
`saturation_rules.md` and `power_meter_method.md`.

### 2.2 Chronological reconstruction

| Step | Action actually performed | Purpose and decision rule | Evidence | Outcome |
| ---: | --- | --- | --- | --- |
| 1 | The sensor head, housing, cable, and connector were visually inspected outside all beam paths. | Reject visible damage or contamination before quantitative use. | `OM01-INSP-001`; `operator_confirmations.md` | No visible defect was reported; inspection passed. |
| 2 | Meter/sensor USB communication and live identity were checked. | Confirm software control and that the connected sensor matched the retained identity. | `OM01-USB-DIAG-001`; `measurements.csv` | Open/query/close and identity match passed; EEPROM range was 190–11000 nm. |
| 3 | Because no dedicated cap existed, a clean opaque non-contact cover was installed and photographed. | Create a reproducible covered-dark condition without touching the absorber. | `OM01-INSP-002`; `OM01-INSP-003`; operator photographs | The temporary cover geometry was accepted for dark checks. |
| 4 | Covered pre-zero readings were acquired, then Zero was pressed once and covered post-zero readings were acquired. | Quantify dark repeatability and verify the stored-zero response. | `OM01-DARK-PREZERO-001`; `OM01-DARK-POSTZERO-001` | Pre-zero mean and noise were stable enough; post-zero response was near zero. |
| 5 | The wavelength/range configuration was set for the representative 540 nm OPO condition; a second covered pre-zero/zero/post-zero sequence was acquired. | Establish the local background immediately relevant to the illuminated series. | `OM01-DARK540-PREZERO-001`; `OM01-DARK540-POSTZERO-001` | Stored zero and residual dark response passed. |
| 6 | The sensor was uncovered with the source shuttered and ambient/background readings were acquired. | Distinguish uncovered ambient response from illuminated signal. | `OM01-AMBIENT540-001` | Shuttered ambient mean was retained and accepted within the bounded method. |
| 7 | Three accepted illuminated windows of 30 readings were acquired at the temporary OPO output plane. | Demonstrate installed average-power repeatability and normal status. | `OM01-ILLUM540-REPEAT-001`; raw readings; analysis | Three window means were retained; status words were normal. |
| 8 | The source was shuttered again, then the nominal setting was revisited. | Confirm that the illuminated signal disappeared and expose return-to-setting evolution. | `OM01-SHUTTER540-RETURN-001`; `OM01-ILLUM540-REVISIT-001` | Shutter response passed; revisit stabilized 49.5% above the initial mean and was classified as source evolution. |
| 9 | The operator confirmed the full visible footprint, including halos, fit within the sensor's 8 mm active radius. | Bound total-beam capture without claiming a quantitative beam diameter. | `OM01-OBS-004`; spatial-containment record | Binary containment passed for the visible representative condition. |
| 10 | Sources, T660s, MIRcat, sensor, and zero state were placed in the recorded final condition. | Close safely and leave no hidden meter correction active. | `restoration_confirmation.json`; final report | T660 safe idle passed; sensor was removed/covered with zero inactive; shutters and source states were recorded. |

### 2.3 Analysis and uncertainty workflow

The representative result is the mean of three 30-reading window means. The
between-window coefficient of variation describes installed repeatability.
The provisional relative standard uncertainty is 2.17%, expanded to 4.34% with
`k=2`, using the contributions documented in
`provisional_uncertainty_budget.md`. The analysis preserved dark/zero,
wavelength/range, meter basis, repeatability, and bounded spatial terms. It did
not assign zero uncertainty to the OPO's mixed spectral composition.

### 2.4 Deviations and limitations

A dedicated sensor cap was unavailable; the photographed temporary non-contact
cover was accepted for this phase. Unfiltered preview readings were retained as
superseded previews rather than used as the final dark basis. The OPO output was
known not to be spectrally pure. The 126.073 mW revisit was therefore treated as
source evolution for PB-02, not meter drift or an uncertainty contribution.

## 3. Results — WHAT

| Quantity | Result | Qualification |
| --- | ---: | --- |
| Three illuminated window means | `83.053`, `84.414`, `85.478 mW` | 30 readings per window |
| Representative indicated total power | `84.3148 mW` | Mean of three window means; meter set to 540 nm |
| Between-window coefficient of variation | `1.4415%` | Installed repeatability |
| Provisional expanded uncertainty | `4.34%` | `k=2`; excludes mixed-spectrum bias |
| Shuttered return mean | `1.3209 mW` | Corrected shuttered response |
| Revisit stable-tail mean | `126.073 mW` | `SOURCE_EVOLUTION`; 49.5% above initial mean |
| Visible-footprint containment | PASS | Binary observation within 8 mm active radius |

Identity, communication, condition, dark/zero, range/status, shutter response,
repeatability, bounded containment, and restoration criteria passed. The phase-
local bundle is qualified bounded and was not canonically promoted.

## 4. Implications, caveats, and claims

OM-01 supports use of the identified meter/sensor chain for bounded average-power
work under the recorded wavelength/range, zero/background, placement, status,
and validity rules. The representative value demonstrates installed procedure
performance and total visible-footprint capture at that condition.

The phase does not support spectrally isolated 540 nm power, pulse-energy
distributions, peak power, invisible-beam or quantitative beam diameter/fluence,
polarization-dependent transfer, source stability, or final sample-plane power.
The 4.34% expanded uncertainty omits unquantified spectral-composition bias and
must not be applied outside the stated configuration. Exact source envelopes and
transfer remain downstream work.

## 5. Reproducibility and source map

| Narrative item | Primary retained source | Reproduction note |
| --- | --- | --- |
| Device/configuration identity | `optical_metrology_configuration_manifest.json`; `measurement_resource_register.csv` | Match meter/sensor IDs, range, wavelength, and method versions. |
| Dark/zero and illuminated population | `acquisition_index.csv`; raw acquisition files | Preserve previews/supersessions and eligibility. |
| Numerical results | `measurements.csv`; `analysis/om01_540nm_analysis.json` | Machine-readable values are authoritative. |
| Uncertainty | `provisional_uncertainty_budget.md` | Keep spectral-composition bias explicitly unquantified. |
| Spatial/spectral limitation | `spatial_containment_method.md`; `operator_confirmations.md` | Interpret containment as binary and visible-only. |
| Restoration | `restoration_confirmation.json` | Verify zero inactive, sensor covered, and source/shutter state. |

Minimal reproduction is to read the indexed dark, ambient, illuminated, shutter,
and revisit records; run the retained 540 nm analysis; and compare with
`measurements.csv` and the phase-local bundle without altering native files.

## 6. Review record

| Review | Reviewer | UTC date | Outcome | Comment |
| --- | --- | --- | --- | --- |
| Evidence traceability | Not assigned | Pending | `PENDING` | Verify acquisition classes and method sources. |
| Technical/scientific | Not assigned | Pending | `PENDING` | Review mixed-spectrum and uncertainty limitations. |
| Thesis readiness | Not assigned | Pending | `PENDING` | Editorial integration remains outstanding. |
