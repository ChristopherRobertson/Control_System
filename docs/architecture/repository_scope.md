# Repository scope and authority boundaries

This monorepo supports thesis-level instrument control, calibration,
characterization, validation, and experimental acquisition without mixing their
authorities.

## Authority flow

1. `campaigns/phase_registry.yaml` defines phase identity, status, dependencies,
   plan locations, and evidence keys.
2. Procedures under `campaigns/` define how an authorized phase is performed.
3. Native and derived records are retained in the phase package registered by
   `campaigns/registries/evidence_locations.yaml`.
4. Reviewed campaign results may be assembled into a machine-readable bundle under
   `instrument/promoted_bundles/` only through the existing scientific closeout and
   explicit promotion gates.
5. `software/control_app/` consumes installed configuration, recipes, SDKs, and
   explicitly promoted bundles. It does not infer runtime values from raw evidence
   or prose reports.

This lets application code and scientific work remain cleanly separated while Git
still versions their interfaces together. No second repository, submodule, or path
outside the checkout is required for normal development or reproduction.

## Directory ownership

- `software/`: executable code and verification only;
- `instrument/`: current installed configuration, runtime recipes and schemas, and
  promoted runtime products;
- `campaigns/`: prospective procedure and dependency authority;
- `evidence/`: observations, acquisition records, analysis outputs, exclusions,
  closeout, and restoration evidence;
- `references/`: manuals, SDKs/drivers, and certificates; and
- `theory/`: model artifacts, not observations.

Generic GUI output under `evidence/experiments/runs/` is operational data, not
campaign evidence unless an approved phase imports and indexes it. Planning text
cannot create an observation, close a phase, or promote a bundle.

## Scientific boundaries

Polystyrene and Mylar are nonbiological characterization materials. SV-02 uses
polystyrene to define and freeze the wavenumber correction and Mylar as the
independent validation standard. HRP and optional cryogenic MbCO requirements trim
the readiness scope, but biological observations never define instrument
calibration.

The separately maintained canonical theoretical notebook defines forward models and
required experimental inputs. Versioned derivatives may be placed under
`theory/notebooks/`; notebook output cannot substitute for measurement evidence or a
promoted instrument result.

Publication drafts, journal submission packages, and paper-specific validation
plans are outside this repository's operational authority.

## Provenance rule

Use stable human-readable campaign, phase, run, acquisition, artifact,
configuration, and bundle identifiers. Paths, byte sizes, UTC timestamps,
software/schema versions, Git references, and dirty-file lists may document
provenance. Repository-authored hash matching must never become a gate for loading,
analysis, aggregation, reproduction, acceptance, closeout, or promotion.
