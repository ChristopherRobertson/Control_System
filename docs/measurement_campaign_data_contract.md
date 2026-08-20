# Measurement campaign data contract

Version: `1.1.0`

This contract makes calibration, characterization, and later experimental
campaigns collectable and aggregatable without reacquisition. It governs new
phase records. Existing native evidence remains valid and is linked through an
index; it is not rewritten solely to satisfy this contract.

## Required identifiers

Identifiers are stable, ASCII, and never reused:

- `campaign_id`: archival campaign directory name.
- `phase_id`: approved phase identifier such as `OM-01` or `PB-01`.
- `phase_run_id`: one approved continuation-safe phase record.
- `acquisition_id`: one attempted acquisition, including rejected attempts.
- `configuration_id`: stable human-readable registry key for the complete
  effective setup and its structured settings record.
- `calibration_bundle_id`: promoted or explicitly provisional calibration set.
- `sample_id`, `device_id`, `component_id`, and `operator_id`: registry keys,
  not free-text substitutes for identity.

All tables use these keys rather than relying on filenames or row order.

## Required phase-directory products

```text
readbacks/<phase-id>/
  phase_manifest.json
  acquisition_index.csv
  conditions.csv
  measurements.csv
  artifacts.csv
  exclusions.csv
  calibration_links.csv
  command_log.txt
  final_report.md
  restoration_confirmation.json
  raw/
  analysis/
  figures/
  tables/
```

Empty required tables retain their header row. Large or device-native files
remain in their native lossless format under `raw/`; tabular exports supplement
rather than replace them.

## Canonical table headers

### `acquisition_index.csv`

One row per attempted acquisition:

```text
campaign_id,phase_id,phase_run_id,acquisition_id,parent_acquisition_id,start_utc,end_utc,operator_id,configuration_id,calibration_bundle_id,sample_id,measurement_kind,condition_set_id,replicate_index,planned,accepted,rejection_code,raw_primary_artifact_id,notes
```

`accepted` is `true` or `false`; rejected and preview/control acquisitions are
never removed. `planned=false` identifies diagnostics or unplanned attempts.

### `conditions.csv`

Long-form conditions permit later joins without widening schemas:

```text
campaign_id,phase_id,acquisition_id,condition_set_id,condition_name,value_text,value_number,unit,source,uncertainty_value,uncertainty_unit,uncertainty_type,notes
```

Use either `value_text` or `value_number`. Record setpoints and readbacks as
different `condition_name` values.

### `measurements.csv`

Long-form measured and derived quantities:

```text
campaign_id,phase_id,acquisition_id,result_set_id,quantity_name,value,unit,statistic,reference_plane,sign_convention,correction_state,standard_uncertainty,coverage_factor,expanded_uncertainty,quality_flag,analysis_artifact_id,notes
```

`correction_state` is one of `raw`, `corrected`, `derived`, or `bounded`.
Corrections are not silently baked into a value; named correction terms appear
as their own rows or in a linked uncertainty/correction table.

For WaveMaster records, `quality_flag` is one of `valid`, `multi_line`,
`saturated`, `no_signal`, `invalid_reply`, or `communication_failure`. The
native response and time tag remain linked raw evidence. Non-numeric outcomes
have an empty numeric `value` and are never coerced to zero or a wavelength.

For the retained OPO-540 path, `conditions.csv` separately records the iris
device/configuration ID, command and readback diameter, tolerance/fault state,
locked-mount check, WaveMaster configuration ID, units, pulse/CW mode,
autocalibration state, probe/reference plane, response quality, center-
wavelength result, residual spectral-content result, and post-iris power. A
center wavelength and a residual spectral-power fraction are different
quantities and cannot share one measurement row or authority.

### `artifacts.csv`

```text
artifact_id,campaign_id,phase_id,acquisition_id,relative_path,artifact_role,media_type,byte_size,created_utc,modified_utc,producer,source_artifact_ids,immutable,notes
```

Paths are relative to the campaign root. `artifact_role` distinguishes native
raw, readback, operator observation, log, analysis source, derived table,
figure, report, photograph, and certificate link.

### `exclusions.csv`

```text
campaign_id,phase_id,acquisition_id,decision_utc,decision_maker,exclusion_code,criterion_version,reason,downstream_effect,superseded_by_acquisition_id,notes
```

Exclusion never deletes or mutates the source acquisition.

### `calibration_links.csv`

```text
campaign_id,phase_id,phase_run_id,calibration_bundle_id,calibration_quantity_id,source_campaign_id,source_phase_id,source_artifact_id,value_used,unit,standard_uncertainty,validity_status,notes
```

This table is the foreign-key bridge that prevents characterization from
copying or repeating calibration work.

## Manifest and provenance requirements

`phase_manifest.json` validates against `config/phase_manifest.schema.json`.
It records the repository branch and dirty-file list rather than claiming a
clean tree when one was not present. Device settings/readbacks,
software/driver versions, recipes, analysis source and environment are linked
as artifacts. UTC timestamps use ISO 8601 with a
`Z` suffix; local time may be stored additionally for operator convenience.

Units are explicit and stable (`s`, `ns`, `Hz`, `cm^-1`, `W`, `J`, `V`, `m`,
`deg`, `K`, `%RH`, or another documented unit). Numeric columns contain only
numbers. Missing values are empty and accompanied by a reason or
`USER_INPUT_REQUIRED`; zero is never used as a missing value.

## Immutability and versioning

- Native raw files become immutable once indexed with stable IDs, relative
  paths, byte sizes, timestamps, roles, and producers.
- A correction creates a new derived artifact with a new artifact ID.
- Analysis code and criterion versions are recorded for every result.
- Superseded artifacts remain indexed and point to their replacements.
- Schema changes increment the contract version; collectors must not infer a
  schema from filenames.
- External protected records are represented by stable identifier, location,
  version/date, equipment association, and access classification rather than
  copied without authorization.
- All provenance fields must comply with the repository-level `AGENTS.md`.

## Aggregation rule

Campaign-level aggregation concatenates tables with identical contract/schema
versions, verifies primary-key uniqueness, required artifact metadata, path
existence, byte-size consistency, and declared relationships, then joins only
on stable identifiers. It never parses prose reports to recover numerical
results. The prose report explains context; machine-readable tables are the
aggregation authority.

## Mandatory retention audit before phase closure

The phase cannot close until an audit confirms:

1. Every attempted acquisition has an index row.
2. Every raw and derived artifact has a stable ID, relative path, byte size,
   timestamp, producer, and role.
3. Accepted, rejected, preview, control, excluded, and superseded states are
   distinguishable.
4. Setpoints, readbacks, conditions, units, identities, and calibration bundle
   links are present.
5. Results identify analysis version, reference plane, correction state, and
   uncertainty or explicit limitation.
6. Restoration and final safe state are recorded when hardware was involved.
7. No canonical calibration or characterization output was promoted without
   its campaign-specific approval gate.
