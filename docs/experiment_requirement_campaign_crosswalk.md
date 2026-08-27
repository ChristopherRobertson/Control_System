# Experiment-requirement campaign crosswalk

> **Unified-order amendment:** `campaigns/registry/phase_registry.yaml` is the phase
> and dependency authority. `campaign_reconstruction_20260826.md` remains the design
> basis for HF-01.1, expanded AR-01, PF-00, SV-02A/B, three acquisition modes, and
> optional QB-01M/MbCO. This historical audit remains valid.

Status: **BRIEFS VERIFIED; MINIMUM CAMPAIGN MAPPING DEFINED; NO PHASE EXECUTION AUTHORIZED**

This crosswalk records the 2026-08-16 audit of:

- `characterization/system_characterization_001/plans/mylar_validation_requirement_brief.md`;
- `experiments/horseradish_peroxidase_requirement_brief.md`; and
- `experiments/myoglobin_co_requirement_brief.md`.

It maps only instrument calibration and characterization requirements. Sample
preparation, CO handling, biological state verification, biological controls,
sample-specific pilots, and biological acquisition remain in their experiment
campaigns and must not enlarge instrument campaigns.

This mapping is dependency-ordered and has no calendar completion target.
Historical timestamps remain provenance; advancement depends on phase gates
and accepted deliverables.

The retained biological OPO path includes one permanent USB/API-controlled iris
and is shared unchanged by HRP-C–CO first and MbCO second.
ATT-01 qualifies its control/readback and faults, selects and locks its
far-field mount, and optimizes the 540 nm diameter against halo rejection and
core clipping. It first performs the preliminary pre-iris 540 nm FIRE-to-
Q-SWITCH delay search. PB-02 performs the final narrow delay search through the
locked iris, and every later OPO-540 phase uses that same configuration.
The observed wavelength-dependent X/Y beam walk prevents extrapolation: another
OPO wavelength requires a separate approved iris/centroid qualification.
The Coherent WaveMaster is the visible/near-IR wavelength working reference.
WM-01 qualifies its installed identity, cable/adapter, communication,
settings, response states, repeatability, uncertainty, and validity before
ATT-01 and PB-02 use it. Its center-wavelength record does not assign residual
spectral-power fractions, and its specified range does not include 355 nm.

Biological execution is ordered HRP-C–CO R0–R9, including accepted closeout and
platform restoration, followed by MbCO MB-01–MB-09. The handoff preserves the
same promoted iris mount/diameter and 540 nm instrument configuration. HRP
biological measurements remain sample-specific evidence and never recalibrate
the platform or supply MbCO absorbance, quantum-yield, overlap, dose, damage, or
kinetic parameters.

## Brief verification result

All three briefs pass the requirements-level audit. Each is non-executable,
separates minimum and optional claims, uses the canonical notebook as a model
authority rather than measurement evidence, cites primary literature and
manufacturer/repository sources, and defines the following required content.

| Audit item | Mylar | HRP-C-CO | MbCO |
|---|---|---|---|
| Scientific question claims and excluded claims | PASS | PASS | PASS |
| Material or sample identity preparation and state verification | PASS | PASS | PASS |
| Cell geometry handling temperature and stability | PASS | PASS | PASS |
| Blanks controls artifacts and abort criteria | PASS | PASS | PASS |
| Spectral windows bands backgrounds and feature analysis | PASS | PASS | PASS |
| Pump/probe geometry power exposure and recovery | Pump-off scope correctly declared | PASS | PASS |
| Complete T660 MIRcat HF2LI Pico and detector timing workflow | PASS | PASS | PASS |
| Delay sign time zero IRF settling and repeated-pulse treatment | Not applicable beyond scan timing | PASS | PASS |
| Replicates randomization drift exclusions and precision rules | PASS | PASS | PASS |
| Analysis models uncertainty and predicted-versus-measured outputs | PASS | PASS | PASS |
| Data contract retention restoration and promotion gates | PASS | PASS | PASS |
| Safety and waste boundaries | PASS | PASS | PASS |
| Literature/manufacturer traceability for numerical starts | PASS | PASS | PASS |
| Minimum required path separated from optional extensions | PASS | PASS | PASS |

The source audit corroborated the briefs' critical anchors: Doster et al.'s
[HRP-C-CO study](https://pubmed.ncbi.nlm.nih.gov/3612808/) supports the two-state
spectral context and slow room-temperature solvent recovery; Schleeger et al.'s
[aqueous horse-heart MbCO flow-flash study](https://pmc.ncbi.nlm.nih.gov/articles/PMC2709881/)
supports the selected sample/preparation scale and microsecond-to-millisecond
design; and a primary [polarized PET spectroscopy study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10975901/)
supports the carbonyl-region feature and its polarization/orientation
sensitivity. Final instrument settings remain campaign-resolved.

One boundary correction was made in the HRP brief during verification: the
actual prepared HRP-C-CO FTIR spectrum belongs to its experiment reference-
preparation phase. `SV-01` and `SV-02` provide only nonbiological spectral-axis
authority and validation. The HRP calibration table now maps Pico/electrical
timing to MS/T phases and process-trigger timing to PT-01.

## Immutable calibration boundary

The following completed calibration phases remain unchanged and are imported
as existing evidence: P0, S0, MS-01, MS-02, T2-01, T1-01, PT-01, MC-01, TR-01,
and OM-01. Completed CH-00 characterization evidence also remains unchanged.
WM-01 started on 2026-08-21 and remains open but deferred after the installed
WaveMaster failed optical qualification. A replacement spectrometer is pending.
ATT-01 and every phase consuming WM-01 or independent 540 nm evidence cannot
begin until WM-01 passes. Dependency-independent phases HF-01, MD-01, MSW-01,
HF-02, DET-01, and SP-01 may proceed with separate authorization. RPT-01 cannot
close and PROM-01 cannot begin until the deferred chain is complete.

## Requirement-to-phase map

| Requirement family | Brief source | Calibration phase | Characterization phase | Minimum retained scope |
|---|---|---|---|---|
| Claims windows tolerances and optional-scope exclusions | all briefs | RPT-01 consumes the map | CH-00 plus retained downstream scope contract | Preserve the completed CH-00 record; unexecuted phases use one Mylar window one combined biological window one shared permanent-iris 540 nm biological pump path and two acquisition topologies. |
| Installed identities wiring and reference-detector identity | all briefs | completed P0/S0 plus TR-01 | CH-00 imports | Record only installed/used identities and validity conditions. |
| Pico channel/path and splitter timing correction | HRP and MbCO | completed MS-01/MS-02 | IR-01 imports | No reacquisition. |
| T660-2 and T660-1 electrical routes | HRP and MbCO | completed T2-01/T1-01 | IR-01 and E2E-CH import | No reacquisition or new timing grid. |
| MIRcat process-trigger electrical path | HRP and MbCO fixed-point workflows | PT-01 | E2E-CH exercises | Resume existing phase only; reserved pins remain excluded. |
| MIRcat GUI point/process behavior and safe stop | HRP and MbCO | MC-01 | QB-01 and E2E-CH use | One inhibited control and three repeats of the selected point/process sequence. |
| Measurement-resource uncertainty basis | all briefs | TR-01 | all quantitative phases import | Used resources only; discarded certificate work stays discarded. |
| Average-power metrology and beam-size method | HRP and MbCO; probe checks for Mylar | completed OM-01 plus downstream transfer | PB/QB/OG use | Preserve completed 532/355/540 observations as provenance; biological authority is the qualified post-iris 540 nm output plus merged probe anchors at used ranges only. Direct 355 nm PB-01 evidence is supplemental thesis characterization. |
| Visible/near-IR wavelength working reference | HRP and MbCO | WM-01 | PB-02/PF/RP/E2E-CH import | Qualify the installed WaveMaster at 540 nm with identity/settings/native status/uncertainty; retain non-numeric response states; do not infer spectral-power fraction or 355 nm wavelength. |
| OPO-540 preliminary delay search electronic iris halo rejection attenuator transfer and non-50/50 splitter behavior | all briefs; iris applies to the shared HRP/MbCO OPO-540 path | ATT-01 after WM-01 | PB-02 and OG/OV/PF/RP import | Freeze and execute a bidirectional preliminary pre-iris FIRE-to-Q-SWITCH delay search; qualify USB/API behavior; select/lock far-field mount; scan 540 nm diameter; control 950 nm home-sensor leakage; bound residual off-wavelength light and core clipping; used optics only. |
| HF2LI reference demodulator and filter configurations | all briefs | HF-01 | AR-01/PF-01 | Validate the manufacturer response model with three monitored PicoScope-AWG anchors, evaluate the supported range/time-constant/order/rate space computationally, and confirm only the selected continuous-sweep, HRP, and MbCO settings plus one challenger when selection uncertainty requires it. No Mylar parameter grid. |
| MIRcat DB9 full-word mapping | Mylar scan plus biological point workflow | MD-01 | QB-01/AR-01 | Three scans per direction and three point/process sequences under each retained biological acquisition configuration, using accepted pins only. |
| Sweep markers and point-tune transition timing | all briefs | MSW-01 | AR-01 | One selected sweep configuration and one point-tune sequence under each HRP and MbCO acquisition configuration. |
| Cross-stream timestamps loss and endurance | all briefs | HF-02 | AR-01/PF-01 | One longest sweep, one longest HRP recovery, and one retained MbCO stream. |
| Detector dark drift and cross-talk | all briefs | DET-01 | PF-01 imports | Used gains/ranges for all three HF2LI configurations only, with short, longest, and revisit records. |
| Per-channel gain linearity saturation and SNR | all briefs | DET-02 | PF-01 imports | Merged Mylar/HRP/MbCO probe anchors and low/high powers only. |
| Detector response latency and bandwidth | HRP and MbCO timing | DET-03 | IR-01 | Measure the installed detector/amplifier/cable path at the fastest required acquisition path and low/high signal, then compose it with HF-01 complex filter transfers for HRP and MbCO; repeat another configuration only after a failed or marginal composition check. |
| Installed optical and detector balance normalization | all briefs | DET-04 | SV-02/PF-01 | Same merged anchors/powers as DET-02 plus one realignment. |
| Polystyrene/Mylar feature authority | Mylar | SP-01 | SV-01/SV-02 | Position/shape authority only; no thickness or absolute-film claim. |
| Spectral axis and direction uncertainty | all briefs | SP-02 | SV-02 imports | Mylar/polystyrene carbonyl region plus combined 1885-1980 cm^-1 biological region only. |
| Pump command to sample optical timing | HRP and MbCO shared post-iris OPO 540 | OP-01 | IR-01 | One retained biological pump path captured under separate HRP and MbCO acquisition IDs; iris is static and configuration-tracked but is not a timing origin or event gate. |
| Finite pump-event admission and independent event count | HRP and MbCO | **FE-01 new** | PB/IR/E2E-CH import | Zero one-event and one finite block per path plus no-emission fault paths. |
| Complete timing closure and long recovery clock bridge | HRP and MbCO | CL-01 | IR-01 | One shared OPO-540 pump path, two acquisition topologies, and three experiment-specific configurations including the retained HRP and MbCO record envelopes. |
| Calibration end-to-end workflow | all briefs | E2E-01 | E2E-CH imports | One probe-only sweep, one HRP-style rare-pump run, and one MbCO-style rare-pump run; reuse FE-01 fault evidence. |
| Supplemental direct 355 nm OPO-drive measurement | thesis and source characterization only | installed high-energy 355 nm detector entry qualification and the final PB-02 operating configuration | PB-01 after PROM-CH | Measure the direct upstream 355 nm drive at the final OPO operating condition and its retained low/high envelope; direct 532 and 1064 are safety/health observations. PB-01 is excluded from completion promotion biological-entry and OPO-540 gates. |
| Permanent post-iris 540 nm OPO output and final delay search | HRP then MbCO | OM pre-iris history plus WM/ATT/OP/FE qualified configuration | PB-02 | Perform a narrow bidirectional FIRE-to-Q-SWITCH delay search through the locked iris and select maximum wavelength-qualified stable post-iris 540 nm power; then complete three return visits and retain WaveMaster status iris readback X/Y profile aperture margin residual spectral content and post-iris power. |
| QCL source envelope | all briefs | SP/MSW/DET inputs | QB-01 | One Mylar window plus merged biological band/off-band anchors in sweep and point modes. |
| Gas-tight cell path blank and temperature stage | HRP and MbCO | metrology links only | **SC-01 new** | Minimum shared CaF2 cell set; blank/leak/path/reassembly; 293 K and 298 K only when required. |
| Sample-plane beam geometry and transfer | all briefs | OM/ATT inputs | OG-01 | Probe-only Mylar plus permanent post-iris OPO-540 at HRP and MbCO probe geometries only; each theoretical dose uses post-iris sample-plane power. |
| Pump/probe overlap | HRP and MbCO | ATT iris configuration for OPO-540 | OV-01 | One shared pump path with two pump/probe geometry pairs three placements and one downstream realignment each; the iris is not adjusted to fit a desired response. |
| Sweep/point settling dwell and filter memory | all briefs | HF/MSW/DET inputs | AR-01 | Two bracket settings per topology; no exhaustive grid. |
| Independent polymer FTIR references | Mylar | SP-01 authority | SV-01 | One specimen-matched polystyrene set and one Mylar set. |
| Polystyrene fit/freeze and independent Mylar validation | Mylar | SP-02 and DET-04 inputs | SV-02 | Predeclared alignment/holdout plus three Mylar scans per direction. |
| Temporal IRF and chemical time-zero handoff | HRP and MbCO | OP/FE/CL/DET-03 plus static ATT iris configuration | IR-01 | Fixed-iris 540 nm at both HRP bands and MbCO A1 only. |
| Noise sensitivity artifacts and averaging | all briefs | DET/HF/ATT inputs | PF-01 | Mylar sweep two HRP bands MbCO A1 and one shared off-band; short and experiment-length records. |
| Between-run reproducibility | all briefs | promoted calibration inputs | RP-01 | One compact three-block checkpoint suite on three days; never repeat full grids. |
| Integrated nonbiological demonstration | all briefs | E2E-01/FE-01/WM-01/ATT-01 | E2E-CH | One composite phase with pump-off Mylar OPO-540/HRP-style and OPO-540/MbCO-style blocks using one unchanged iris and qualified wavelength-reference configuration including mismatch stop and setpoint/status audit. |
| Reporting retention and promotion | all briefs | RPT-01/PROM-01 | RPT-CH/PROM-CH | Aggregate existing evidence; no replacement acquisition. |

## Requirements intentionally left in experiment campaigns

The following have no calibration or characterization phase because they are
sample-specific and must be completed independently in the HRP-C-CO or MbCO
experiment campaign:

- protein supplier/lot/isoform/species identity and concentration basis;
- buffer pH ionic strength reductant oxygen exclusion CO loading and chemical
  mass balance;
- actual-sample UV-visible and FTIR state verification;
- CO/compressed-gas biological/chemical safety approvals and waste procedures;
- sample-specific concentration/path selection after SC-01 supplies qualified
  hardware choices;
- dose-linearity photodamage recovery cadence sample refresh and replacement
  pilots;
- biological blanks alternate states pump/probe controls and post-integrity
  checks;
- independent preparation/day replication randomization and exclusions;
- HRP pocket/solvent and MbCO geminate/bimolecular model comparison; and
- versioned biological analysis packages and experiment-specific promotion.

Keeping these items out of instrument campaigns prevents biological data from
defining calibration and avoids performing chemistry work that cannot be reused
between the two proteins.

## Minimal-grid rule

Every retained campaign phase starts with the grid in this crosswalk. A point
may be added only after a named predeclared acceptance criterion fails or a
brief's mandatory claim is formally changed before the affected phase begins.
Optional literature extensions do not expand the grid. Shared wavelengths,
power points, detector settings, controls, and configurations are measured once
and linked to all applicable requirements by stable human-readable IDs.
