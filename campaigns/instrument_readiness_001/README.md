# Instrument readiness 001

This campaign is the single, dependency-ordered route from installed-system
inventory through calibration, characterization, independent validation,
reporting, and promotion. Its 47 phases are scientific domains in one campaign;
there are no separate calibration and characterization execution trees.

## Active organization

```text
instrument_readiness_001/
├── AGENTS.md
├── README.md
├── requirements.md
└── phases/
    └── <phase-id>/
        ├── phase.yaml
        ├── plan.md
        ├── README.md
        ├── procedural_writeup.md       # required at documentation closeout
        └── phase-specific evidence and reports
```

Every phase has one canonical directory. It contains its plan and all retained
readbacks, raw acquisitions, analysis inputs/outputs, command logs, indexes,
reports, restoration records, photographs, and other phase artifacts. The phase
directory is also the evidence root identified by its registry `evidence_key`.

## Authorities

- [`../master_sequence.md`](../master_sequence.md) is the authoritative
  human-readable instruction set and ordered phase catalog.
- [`../phase_registry.yaml`](../phase_registry.yaml) is the machine-readable
  phase, status, dependency, plan, evidence-key, and documentation-state record.
- [`requirements.md`](requirements.md) contains requirements and methods shared by
  multiple instrument-readiness phases.
- `phases/<phase-id>/plan.md` is the complete phase-specific procedure,
  acceptance logic, and deliverables.
- [`../../docs/phase_record_contract.md`](../../docs/phase_record_contract.md)
  defines the evidence package and procedural writeup required for closeout.

## Campaign state

The completed phases are P0, S0, MS-01, MS-02, T2-01, T1-01, PT-01, MC-01,
TR-01, OM-01, CH-00, and HF-01. Their scientific evidence remains valid and is
not reacquired to satisfy documentation changes. Any missing
`procedural_writeup.md` is reconstructed from the retained phase evidence, with
unknowns and claim limits stated explicitly.

WM-01 is in progress. Its entry/preflight evidence is retained, but its remaining
measurement and closeout work is blocked until a qualified replacement
spectrometer is available. HF-01.1 and MD-01 are the currently dependency-eligible
planned phases. DET-01, SP-01, and SC-01 are also dependency-eligible; SV-01 waits
for SP-01. HRP phase R0 is eligible for planning from CH-00 but remains a separate
experiment campaign. Schedule work only when its resources and downstream sequence
are ready. Always use the registry and master sequence at the time of
authorization; eligibility is not execution authority.

## Phase inventory

| Registry domain | Count | Phase IDs |
| --- | ---: | --- |
| Calibration | 28 | P0, S0, MS-01, MS-02, T2-01, T1-01, PT-01, MC-01, TR-01, OM-01, HF-01, HF-01.1, WM-01, MD-01, MSW-01, HF-02, DET-01, SP-01, ATT-01, DET-02, DET-03, DET-04, SP-02, OP-01, FE-01, CL-01, E2E-01, RPT-01 |
| Characterization | 14 | CH-00, QB-01, PB-02, SC-01, OG-01, OV-01, AR-01, PF-00, IR-01, PF-01, RP-01, E2E-CH, RPT-CH, PB-01 |
| Independent validation | 3 | SV-01, SV-02A, SV-02B |
| Promotion | 2 | PROM-01, PROM-CH |

Optional cryogenic MbCO work is a separate downstream experiment campaign and
does not block the instrument-readiness core path.

## Preservation rule

Repository reorganization does not create a new acquisition, change a scientific
disposition, or require a completed measurement to be repeated. Contemporaneous
path strings inside accepted evidence remain provenance. Active paths are defined
by the current registry and documentation; inactive source documents are retained
under the path-mirrored repository `.archive` for traceability and retrospective
writeup work.
