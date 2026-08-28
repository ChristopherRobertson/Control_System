# Repository architecture and documentation map

This repository is one versioned workspace for instrument-control software,
installed configuration, campaign procedure development, acquisition evidence,
scientific references, and thesis-facing analysis. The directories separate
authority and responsibility without requiring separate repositories.

## Authority flow

1. `campaigns/master_sequence.md` defines the human-readable instructions for
   completing calibration, characterization, validation, reporting, and promotion.
2. `campaigns/phase_registry.yaml` carries the matching machine-readable phase
   identities, statuses, dependencies, plan paths, and execution constraints.
3. A phase's `plan.md` supplies its detailed implementation procedure without
   changing the master order or common completion requirements.
4. The phase package under `campaigns/<campaign>/phases/<phase-id>/` retains the
   plan, observations, native data, analysis, decisions, reports, restoration,
   and procedural writeup together.
5. Reviewed campaign results become application inputs only through an explicitly
   promoted, versioned bundle under `instrument/promoted_bundles/`.
6. `software/control_app/` consumes installed configuration, recipes, SDK-backed
   services, and promoted bundles; it does not derive runtime values from prose or
   raw campaign evidence.

## Directory responsibilities

- `software/`: GUI, device services, workflow orchestration, tests, and tools.
- `instrument/`: installed hardware/wiring configuration, runtime recipes,
  schemas, and promoted machine-readable products.
- `campaigns/`: master instructions, registry, reusable methods/templates, and
  self-contained phase packages.
- `evidence/`: generic GUI and operational runs that have not been imported into
  a registered phase package.
- `references/`: manuals, SDKs/drivers, certificates, and the reference registry.
- `theory/`: versioned model and notebook derivatives, not observations.
- `docs/`: this architecture overview, repository documentation instructions,
  the phase-record contract, and focused operating procedures.
- `.archive/`: tracked, inactive source material preserved for traceability and
  retrospective documentation. It is never an execution or runtime authority.

## Control application architecture

The desktop application reads `instrument/hardware_configuration.yaml`,
`instrument/wiring_map.yaml`, and the explicit catalogs under
`instrument/recipes/`. Ordinary GUI output is written below
`evidence/experiments/`. Campaign evidence is created only when an authorized
phase records or imports that output using the phase-record contract.

The recipe-driven Workflows tab exposes only entries declared in
`instrument/recipes/ui_workflows.yaml`. A workflow must validate and save an
immutable configured snapshot before Run becomes available. Changing an exposed
setting invalidates that configured state. Workflows requiring MIRcat control
also require manufacturer-GUI ownership to be released before the application
opens the SDK connection.

The experiment builder uses versioned definitions, a capability registry,
cross-device constraints, and registered service adapters. Loading, validating,
editing, and configuring a definition do not access hardware. Execution remains
gated until the engine has explicit device adapters and a valid immutable plan.
Device communication stays in `software/control_app/devices/`; definitions and
widgets do not duplicate SDK or serial behavior.

Every executable workflow must define stop, abort-to-safe, and failure-recovery
behavior. Reserved or disconnected routes cannot become selectable merely because
a UI field or recipe can represent them. Hardware safety infrastructure remains
independent of repository software.

## Scientific boundaries

Calibration establishes corrections, reference conventions, uncertainty, and
qualified measurement behavior. Characterization measures installed instrument
and system performance using those inputs. Validation tests frozen choices with
independent evidence. Biological observations do not define instrument
calibration or characterization.

Generic GUI records are operational evidence until an authorized phase imports
and indexes them. Planning text cannot create an observation, change phase status,
or promote a bundle. Theory and notebooks may define models or required inputs but
cannot substitute for measured evidence.

## Phase documentation

The normative record, identifier, table, provenance, retention, procedural-
writeup, review, and aggregation requirements are in
[`phase_record_contract.md`](phase_record_contract.md). Focused operator-facing
procedures remain under `operating_procedures/` and must cite the applicable
recipe, phase plan, and safety boundary.

## Provenance

Use stable human-readable IDs, relative paths, byte sizes, UTC timestamps,
software/schema/analysis versions, device and configuration identities, branch or
commit references, dirty-file lists, and explicit producer/source records.
Checksums may be informational, but repository-authored hash matching cannot be an
operational gate.
