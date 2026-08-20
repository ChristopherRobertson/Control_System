# OM-01 operator confirmations

## OM01-INSP-001 - sensor-head visual inspection

Recorded UTC: `2026-08-18T21:38:14.7565917Z`  
Operator: Christopher Robertson

The operator inspected Newport 919P-010-16 sensor serial `161791` outside all
beam paths and reported:

- no dust, residue, fingerprints, discoloration, scratches, dents, or burn
  marks;
- no loose or damaged housing;
- DB15 connector in good condition, with no bent pins or strained cable; and
- the sensor is essentially brand new.

Decision: **PASS** for visible sensor/head/connector condition. This inspection
does not establish zero, background, responsivity, range, saturation, or
measurement performance.

## OM01-INSP-002 - sensor photograph and dark-cover inventory

Recorded UTC: `2026-08-18T21:43:00.2266989Z`  
Operator: Christopher Robertson

The operator supplied `docs/Power_Meter/Sensor.jpg` and reported that no
dedicated opaque, clean, non-contact cap or cover is available. The photograph
shows the sensor head mounted on an adjustable base with an unobstructed
protruding front housing; the absorber face is not visible from the photograph's
angle. No beam or emission was involved.

Decision: **DEDICATED CAP UNAVAILABLE; QUALIFIED TEMPORARY ENCLOSURE REQUIRED**.
An improvised enclosure is permitted only if it is opaque, clean, room
temperature, mechanically stable, supported independently, provides clearance
from the sensor front/absorber, and cannot shed material into the aperture.

## OM01-INSP-003 - temporary dark cover installed

Recorded UTC: `2026-08-18T21:45:21.4408163Z`  
Operator: Christopher Robertson

The operator placed an opaque plastic piece over the end of the sensor tube and
secured it with tape. The operator reports that the cover does not contact the
sensor area in any way and that light does not enter around the edges.

Decision: **PROVISIONALLY ACCEPTED AS DARK-COVER CONFIGURATION**. A photograph
of the installed cover is required before a meter reading or stored-zero
command so the non-contact geometry, external tape placement, and reproducible
configuration can be indexed.

### Placement-photo review

`docs/Power_Meter/CoveredSensor.jpg` was reviewed after installation. The
opaque plastic appears to close the tube opening without visible intrusion into
the sensor cavity. Together with the operator's no-contact/no-edge-light
observation, configuration `OM01-DARK-COVER-PLASTIC-v1` is **ACCEPTED** for
covered dark/background checks. Tape remains an external fixture only and may
not be moved into the cavity.

## OM01-OBS-004 - OPO spectral-content limitation

Recorded: post-acquisition closeout clarification  
Operator: Christopher Robertson

The operator reports that the OPO output is never purely the wavelength
selected in the OPO GUI and that visible halos surround the central beam,
consistent with unwanted wavelength content and/or additional spatial
structure. The operator confirms that the entire visible footprint, including
these halos, fit within the sensor radius during the representative acquisition.

Decision: **ACCEPTED AS A BOUNDED APPLICABILITY LIMITATION**. The power-meter
result is total incident OPO-output power indicated with the meter set to
540 nm, not spectrally isolated 540 nm power. Spectral composition remains a
PB-02/downstream transfer input.
