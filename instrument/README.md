# Runtime configuration

All acquisitions are **functionality tests**, with no runtime calibration or scientific claims until explicit operator release. Current priority is end-to-end app workflows. See [result status](../docs/result_status.md). MUX work is deferred; current experiments use direct detector and marker connections.

`hardware_configuration.yaml` identifies installed devices and validity limits.
`wiring_map.yaml`, `wiring_table.xlsx` and `default_wiring_state.md` describe current
connections. `recipes/` contains executable timing resources and explicitly marked
engineering candidates. An unapproved candidate remains non-executable.

See [Phase Scan preview settings](phase_scan_preview.md) for disconnected planning
and [optical pump constraints](optical_pump_constraints.md) for installed OPO limits.
Nominal electrical command values are distinct from measured optical corrections.

Scientific calibration and fit results belong in System_Research. To select a new
runtime parameter set, obtain explicit operator approval of the values, units,
uncertainties, device/configuration identities, validity envelope and source IDs.
Copy only the necessary machine-readable values into a uniquely identified directory
under `promoted_bundles/`, with a `manifest.yaml` matching the bundle schema. Register
that ID and path in `registry.yaml`. Set both statuses to `PROMOTED` only after
approval, then explicitly select `CONTROL_SYSTEM_BUNDLE_ID` and restart. Record
selection rationale and full scientific provenance with the research results.

The loader rejects missing IDs and mismatched or unpromoted manifests. Measurement
measurement adapters validate their required runtime fields. There are currently no
promoted bundles. Existing recipe values remain active independently where their
workflow permits raw acquisition; an empty registry does not grant calibrated claims.

Storage configuration belongs in the ignored `storage.local.json` installation file:
`{"research_root": "C:/absolute/path/to/System_Research"}`. The environment override
and output layout are described in the [root README](../README.md).
