# Instrument readiness 001

This campaign is phase-primary. All 47 calibration, characterization, validation,
and promotion phases have one canonical home under `phases/<phase-id>/`, including
the phases that were previously only sections in combined sequence documents.
Each home is the complete phase package. It contains `phase.yaml`, `plan.md`, and
`README.md` plus every readback, raw acquisition, analysis input/output, command
log, artifact index, report, restoration record, photograph, and other retained
file produced by that phase.

```text
instrument_readiness_001/
├── phases/     # 47 complete plan + execution + evidence packages
└── shared/     # cross-phase requirements, methods, matrices, and history only
```

There are no separate calibration and characterization execution trees. Those
terms remain useful registry domains, but the unified dependency order is defined
only by `../phase_registry.yaml` and rendered for readers in
`../master_sequence.md`. Optional cryogenic MbCO work remains a separate campaign
and cannot block the instrument-readiness core path.

| Registry domain | Count | Canonical phase directories |
| --- | ---: | --- |
| Calibration | 28 | `P0`, `S0`, `MS-01`, `MS-02`, `T2-01`, `T1-01`, `PT-01`, `MC-01`, `TR-01`, `OM-01`, `HF-01`, `HF-01.1`, `WM-01`, `MD-01`, `MSW-01`, `HF-02`, `DET-01`, `SP-01`, `ATT-01`, `DET-02`, `DET-03`, `DET-04`, `SP-02`, `OP-01`, `FE-01`, `CL-01`, `E2E-01`, `RPT-01` |
| Characterization | 14 | `CH-00`, `QB-01`, `PB-02`, `SC-01`, `OG-01`, `OV-01`, `AR-01`, `PF-00`, `IR-01`, `PF-01`, `RP-01`, `E2E-CH`, `RPT-CH`, `PB-01` |
| Independent validation | 3 | `SV-01`, `SV-02A`, `SV-02B` |
| Promotion | 2 | `PROM-01`, `PROM-CH` |

Completed and in-progress evidence is stored directly in its phase directory and
registered there through the phase's `evidence_key`. There is no second calibration
or characterization evidence tree. Restructuring never represents a moved file as
a new acquisition or requires a measurement to be repeated. Historical manifests
retain contemporaneous path strings when those strings are provenance rather than
active lookup instructions.

All phases inherit `shared/phase_execution_requirements.md` and the thesis-quality
writeup standard at `../../docs/data_contract/procedural_writeup_standard.md`.
Missing narratives for historically completed work are tracked in
`shared/procedural_writeup_backfill_register.md`; documentation backfill preserves
the scientific disposition and never requires reacquisition.
