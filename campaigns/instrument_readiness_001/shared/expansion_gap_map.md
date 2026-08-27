# Calibration expansion gap map

The prospective dependency authority is `campaigns/phase_registry.yaml`.
The preserved reconstruction design adds HF-01.1, joint AR-01, PF-00, SV-02A/B,
all three acquisition modes, and optional QB-01M.

This map records how the expanded campaign handles the thesis and experimental gaps
without repeating completed work.

| Requirement | Existing evidence reused | New calibration work | Downstream characterization work |
|---|---|---|---|
| Electrical trigger/path timing | S0, MS-01, MS-02, T2-01, T1-01 | PT-01, CL-01 | None; import calibration bundle. |
| MIRcat external modes and state semantics | P0 mapping observation | MC-01, MD-01, MSW-01 | Exercise only approved modes. |
| HF2LI configuration and stream integrity | T2-01 EXT REF/DAQ route | HF-01, HF-02 | System-level settling and performance within qualified envelope. |
| Available optical power and beam metrology | P0 inventory plus available power-meter records | TR-01 and OM-01 qualify only resources required by the experiment claim grid; no energy meter is assumed | Average-power and beam measurements at conditions selected by experiment design; any mean pulse energy is explicitly derived rather than directly measured. |
| Visible/near-IR wavelength working reference | Retained Coherent documents plus the registered query-only device/adapter/driver intake and operator-confirmed safe operation | WM-01 entry preflight is ready; after separate authorization it qualifies installed identity cable/adapter communications settings response states 540 nm repeatability uncertainty and validity | PB-02 and every quantitative OPO-540 phase import native wavelength/status evidence and the WM-01 bundle; center wavelength is not a spectral-power fraction and 355 nm is outside the meter range. |
| Preliminary OPO-540 delay search electronic iris halo rejection optical attenuation splitter ratio and sample-plane transfer | OM-01 bounded pre-iris mixed-output observation plus permanent ELL15 identity and service records | ATT-01 imports WM-01; performs the preliminary bidirectional pre-iris FIRE-to-Q-SWITCH search; qualifies USB/API behavior; selects and locks the far-field mount; optimizes the 540 nm diameter without clipping; controls 950 nm leakage; and measures every used transfer element and splitter port | PB-02 performs the final narrow post-iris delay search; OG/OV use only the qualified fixed configuration; another OPO wavelength requires separate iris/centroid qualification. |
| Detector dark and illuminated transfer behavior | Installed-path inventory | DET-01, DET-02 | Measure platform sensitivity in accepted operating region. |
| Detector latency needed by optical timing | MS-01/MS-02 scope corrections and T1-01 electrical timing | DET-03 | Temporal instrument-response measurement. |
| Sample/reference power imbalance and dual-detector normalization | No completed quantitative evidence | DET-04 separates optical balance from detector/electronics balance and produces the wavelength-dependent normalization bundle | Import DET-04 in spectral sensitivity and biological analysis; do not repeat the balance calibration. |
| Spectral reference and axis | P0 polystyrene/Mylar observations | SP-01, SP-02 | Independent spectral validation and forward modeling. |
| Pump/probe beam output and geometry | No completed quantitative evidence; OM-01 records only binary containment of the unfiltered OPO footprint | Metrology resources preliminary delay and permanent OPO-540 iris configuration in OM-01/ATT-01 | PB-02 through OV-01 measure the final OPO-540 path; supplemental post-promotion PB-01 separately measures direct 355 nm for thesis evidence and is outside all gates. |
| Operational optical timing | MS-01/MS-02/T1-01 corrections | OP-01, CL-01 | Import corrected time origin; measure complete response without redoing path timing. |
| Finite rare-pump exposure and observed-event reconciliation | Completed electrical routes plus OP-01 optical timing | FE-01 qualifies only the shared permanent-iris OPO-540 event admission normal stop and no-emission fault paths | Import the finite-event controller for HRP first and MbCO second; biological dose recovery and photolysis remain separate experiment work. |
| Gas-tight cell path and temperature basis | P0 inventory and OM-01 metrology links | None; this is installed sample hardware rather than a calibration correction | SC-01 qualifies the minimum shared CaF2 cell set with blank leak path reassembly and 293 K/298 K temperature evidence without protein or CO. |
| Data provenance and aggregation | Existing stable phase directories | Common data contract, RPT-01, PROM-01 | Same contract and foreign-key bundle links. |
| Biological experiments | None; biological samples are not standards | Outside calibration | Separate biological campaigns after characterization promotion. |

## Non-duplication decisions

- Completed phase raw data remain in place and are indexed during RPT-01.
- New schemas do not trigger conversion or reacquisition of native evidence.
- Calibration qualifies measuring systems and corrections; characterization
  measures source/beam/system performance.
- Biological samples are never used to establish spectral or timing calibration.
- The minimum retained grids and experiment-only exclusions are controlled by
  `campaigns/instrument_readiness_001/shared/experiment_requirement_campaign_crosswalk.md`.
