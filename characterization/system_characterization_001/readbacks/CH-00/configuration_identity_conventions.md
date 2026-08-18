# Configuration and identity conventions

- Complete configurations use `CHCFG-<topology>-<source>-<probe>-vN`, for
  example `CHCFG-POINT-532-HRPLOW-v1`. A change to wiring, device, range,
  filter, geometry, or correction bundle creates a new version.
- Devices and components retain stable campaign IDs from P0/TR-01. Replacement
  hardware receives a new ID and is requalified where material.
- Acquisitions use `system_characterization_001_<phase>_<condition>_<attempt>`;
  artifacts use stable phase-scoped IDs and relative paths.
- Software identity is explicit version text: schema, control application or
  script path/version, analysis version, driver, firmware, MIRcat GUI/SDK, and
  LabOne/HF2LI version as applicable. Branch and dirty-file lists are recorded.
- No hash or checksum match is required to load, analyze, accept, aggregate,
  close, or promote work.
- `P0-D001` is satisfied: the installed reference chain is VIGO
  `SIP-DC-250M` serial `445161066` with `PVM-10.6-1x1` detector serial `21834`.
  DET-01 through DET-04 must still qualify its performance.
- Generic MIRcat board/cable and Nd:YAG adapter provenance uses stable IDs,
  wiring authority, photographs, and measured corrections; discarded part or
  certificate research is not restored as a gate.
- Temperature and humidity are observational only. They are not calibrated
  environmental corrections or quantitative environmental claims.
- Sample IDs are prohibited in CH-00 because it is analysis-only. Biological
  identities, CO, preparation, and state verification remain experiment work.
