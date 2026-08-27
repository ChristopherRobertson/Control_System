# Repository instructions

These instructions apply to the entire repository. More specific instructions
in subdirectories add to these rules and may not weaken them.

## Hash matching must not be an operational gate

Git may use commit and object hashes normally, and repository tools may record
or display hashes, checksums, or digest values for informational or diagnostic
purposes. Do not add a repository-specific requirement that any such value
must match a previously recorded value for the application, a campaign phase,
data loading, analysis, aggregation, reproduction, acceptance, closeout, or
promotion to work. A missing or changed value may be reported as information,
but it must not be the sole reason that repository-authored behavior fails or
blocks progress.

Normal integrity behavior internal to Git, package managers, file formats, and
external tools is not restricted. The prohibition applies to additional
hash-matching gates authored in this repository.

Prefer stable human-readable IDs, relative paths, byte sizes, UTC timestamps,
explicit software/schema/analysis versions, branch or commit references,
dirty-file lists, device identities, configuration registries, and
source/producer records for campaign provenance and aggregation.

## Unified repository hierarchy

`campaigns/registry/phase_registry.yaml` is the sole prospective phase and hard-
dependency authority. Calibration and characterization sequence documents are
detailed procedure catalogs and historical context, not independent schedules.
Completed and in-progress evidence stays at the path registered in
`campaigns/registry/evidence_locations.yaml`; never relocate it merely to match the
new hierarchy.

The control application consumes explicitly promoted machine-readable bundles from
`instrument/promoted_bundles/`, not raw campaign evidence or prose reports. Creating
a plan, registry row, bundle directory, or manifest never authorizes hardware,
changes phase status, or promotes a bundle.
