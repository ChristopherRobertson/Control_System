# IR spectroscope control system and thesis campaigns

This repository is a single, structured workspace for instrument-control software,
campaign procedure development, acquisition evidence, runtime configuration, and
the scientific references needed to connect them. The boundaries are physical, but
Git versions them together so the control system can consume promoted results
without copying data between repositories.

## Repository map

| Directory | Responsibility |
| --- | --- |
| `software/` | GUI application, device services, tests, tools, dependencies, and packaging |
| `instrument/` | Installed hardware/wiring authority, runtime recipes, schemas, and explicitly promoted bundles |
| `campaigns/` | Unified phase registry plus self-contained phase packages containing plans, readbacks, raw data, analysis, reports, and promotion work |
| `evidence/` | Generic GUI/operational experiment runs and cross-campaign catalogs that do not belong to a registered campaign phase |
| `references/` | Manufacturer manuals, SDKs/drivers, certificates, and their registry |
| `theory/` | Versioned model/notebook derivatives and validation fixtures |
| `docs/` | Repository architecture, operating procedures, and the phase-record contract |
| `.archive/` | Inactive source documents retained intact under their original relative paths |

`campaigns/master_sequence.md` is the authoritative human instruction set.
`campaigns/phase_registry.yaml` is its machine-readable ordering, status, and
hard-dependency companion. Calibration and characterization remain useful
scientific domains, but they are phases in one instrument-readiness graph.

Completed evidence is stored directly in the matching canonical phase package under
`campaigns/<campaign>/phases/<phase-id>/`, beside the plan and phase metadata. The
relocation did not create new acquisitions, change measurement values, or change
phase status.
`campaigns/registries/evidence_locations.yaml` is the stable lookup authority. The
archived historical record at
`.archive/campaigns/migration/self_contained_phase_packages_20260827.md` documents
the phase-package relocation and preservation audit. Archived migration and
experiment-overview documents are historical only; current campaign authority
remains in the master sequence, phase registry, campaign requirements, methods,
and phase packages.

## Control application

For the existing local environment:

```powershell
.venv\Scripts\python.exe -m pip install -e software
.\run_gui.ps1
```

After the editable install, the original module command also works from the
repository root:

```powershell
.venv\Scripts\python.exe -m control_app.ui.app
```

The GUI reads `instrument/hardware_configuration.yaml`,
`instrument/wiring_map.yaml`, and `instrument/recipes/`; it writes ordinary runs and
logs below `evidence/experiments/`. Runtime scientific values may come only from a
bundle explicitly marked `PROMOTED` in both the promoted-bundle registry and its
manifest. A plan, recipe, directory, or registry row never authorizes hardware or
changes scientific status.

The [default wiring diagram](instrument/default_wiring_state.md) shows the
detector split connections: each signal passes through a female-to-female BNC
adapter and a male-to-two-female BNC tee. Sample feeds HF2LI Signal 1 In (+)
and PicoScope CHA; reference feeds HF2LI Signal 2 In (+) and PicoScope CHB.

The repository boundary and authority rules are in `docs/README.md`, and the
shared acquisition/evidence rules are in `docs/phase_record_contract.md`.

Every phase also requires a separate thesis-quality `procedural_writeup.md` before
documentation closeout. The governing standard and reusable template are
`docs/phase_record_contract.md` and
`campaigns/templates/phase_record/procedural_writeup.template.md`. The writeup
explains WHY, HOW, WHAT, and the defensible implications/caveats/claims; it does not
replace machine-readable evidence or the formal `final_report.md` decision record.
