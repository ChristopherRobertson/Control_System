# ATT-01 planning context

This file preserves the phase-specific row or rows from the pre-migration
cross-phase planning matrices. The canonical phase plan is `plan.md`; this
context is retained so no planning detail is lost during the phase-primary
restructure.

## Source: calibration measurement matrix

| Field | Preserved value |
| --- | --- |
| `calibration_id` | ATT01 |
| `measured_quantity` | electronic-iris control preliminary 540 nm FIRE-to-Q-SWITCH delay search far-field placement halo rejection aperture optimization attenuation splitter and sample-plane transfer |
| `physical_reference_plane` | unfiltered OPO or other incident optical plane |
| `target_reference_plane` | qualified post-iris 540 nm plane and used sample detector and reference-detector planes |
| `measurement_method` | USB/API command-readback tests preliminary bidirectional delay search candidate-plane comparison diameter scan spectral/spatial diagnostics incident-transmitted power dual-port ratio and lasers-blocked iris-powered control |
| `required_equipment` | qualified power meter WM01-qualified wavelength spectrometer pulsed-light-safe spectral/spatial diagnostics electronic iris and only optical elements retained by the experiment union |
| `wiring_setup` | locked iris Z/X/Y mount and identified ports orientation polarization beam dumps and reference planes; direct 532 and 355 remain distinct |
| `programmed_values` | prospectively frozen coarse FIRE-to-Q-SWITCH delay sequence centered only provisionally near the prior 632 nm observation;540 nm diameter sequence plus low/high retained operating points; midpoint only after residual failure |
| `repetitions` | delay-search repeats in ascending and descending directions plus revisit;control/readback/reconnect/power-cycle series; complete diameter scan; three readings per endpoint plus revisit and return-to-540 approaches |
| `raw_data_product` | native programmed/read-back delay pre-iris power and wavelength-status records plus USB/API replies command log candidate-plane and diameter-scan profiles/spectra/powers 950 nm control incident transmitted and dual-port readings |
| `correction_terms` | device units/readback/dark/wavelength/placement/range and transfer corrections |
| `type_a_uncertainty` | delay-search direction/revisit repeatability command agreement hysteresis centroid/profile drift realignment and revisit |
| `type_b_uncertainty` | API/firmware semantics damage threshold meter and WM01 spectrometer uncertainty spectral residual polarization placement interpolation and transfer covariance |
| `combined_standard_uncertainty` | pending |
| `expanded_uncertainty` | pending |
| `traceability_source` | ELL15 and wavelength-spectrometer manufacturer documents OM01 WM01 and component records |
| `dependencies` | OM01 WM01 |
| `closure_test` | preliminary delay search accepted plus control fault tests permanent plane diameter core-margin halo-rejection 950 nm control dual-port closure insertion-loss and revisit agreement |
| `thesis_or_handoff_destination` | electronic-iris optical-transfer and preliminary-delay bundle for later OPO-540 characterization and experiments |
| `current_status` | DEFERRED PENDING WM01 REPLACEMENT SPECTROMETER QUALIFICATION |
| `bypass_allowed` | no |
| `effect_of_bypass` | OPO-540 emission and quantitative sample-plane dose remain blocked; dependency-independent phases may proceed only where separately authorized |
