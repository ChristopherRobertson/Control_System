# Retained inactive material

This directory preserves source documents that are no longer active repository
authorities. Files are retained intact under their original repository-relative
paths prefixed by `.archive/`. For example:

```text
docs/data_contract/measurement_campaign_data_contract.md
→ .archive/docs/data_contract/measurement_campaign_data_contract.md
```

The path mirroring allows a contemporaneous provenance reference to be resolved
without recreating a competing active hierarchy. Material here may be consulted
for traceability, audits, and retrospective phase procedural writeups. It must not
be used as a runtime input, current campaign instruction, completion gate, or
promotion authority.

Current authorities are:

- [`../README.md`](../README.md) and [`../docs/README.md`](../docs/README.md) for
  repository purpose, structure, and boundaries;
- [`../AGENTS.md`](../AGENTS.md) and [`../docs/AGENTS.md`](../docs/AGENTS.md) for
  repository and documentation maintenance instructions;
- [`../docs/phase_record_contract.md`](../docs/phase_record_contract.md) for phase
  data, evidence, and procedural writeups;
- [`../campaigns/master_sequence.md`](../campaigns/master_sequence.md) and
  [`../campaigns/phase_registry.yaml`](../campaigns/phase_registry.yaml) for phase
  instructions, status, and order; and
- [`../campaigns/instrument_readiness_001/requirements.md`](../campaigns/instrument_readiness_001/requirements.md)
  for instrument-readiness cross-phase requirements.

See [`documentation_consolidation_20260827.md`](documentation_consolidation_20260827.md)
for the complete source-to-authority coverage map.
