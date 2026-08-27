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
| `campaigns/` | Unified phase registry, dependency sequence, plans, procedures, reports, and promotion work |
| `evidence/` | Completed/in-progress calibration and characterization phase packages plus generic experimental runs |
| `references/` | Manufacturer manuals, SDKs/drivers, certificates, and their registry |
| `theory/` | Versioned model/notebook derivatives and validation fixtures |
| `docs/` | Architecture, operating procedures, and data contracts shared across boundaries |

`campaigns/phase_registry.yaml` is the sole prospective ordering and hard-dependency
authority. Calibration and characterization remain useful scientific domains, but
they are phases in one instrument-readiness graph rather than competing schedules.
`campaigns/master_sequence.md` is the human-readable view.

Completed evidence was moved intact into canonical phase packages under
`evidence/calibration/system_recalibration_001/phases/` and
`evidence/characterization/system_characterization_001/phases/`. The relocation did
not create new acquisitions, change measurement values, or change phase status.
`campaigns/registries/evidence_locations.yaml` is the stable lookup authority, and
`campaigns/migration/physical_restructure_20260827.md` records the old-to-new map.

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

The detailed boundary rules are in `docs/architecture/repository_scope.md`, and the
shared acquisition/evidence rules are in
`docs/data_contract/measurement_campaign_data_contract.md`.

Every phase also requires a separate thesis-quality `procedural_writeup.md` before
documentation closeout. The governing standard and reusable template are
`docs/data_contract/procedural_writeup_standard.md` and
`campaigns/templates/phase_record/procedural_writeup.template.md`. The writeup
explains WHY, HOW, WHAT, and the defensible implications/caveats/claims; it does not
replace machine-readable evidence or the formal `final_report.md` decision record.
