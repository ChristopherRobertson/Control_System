# Calibration expansion gap map

This map records how the expanded campaign handles the thesis and experimental gaps
without repeating completed work.

| Requirement | Existing evidence reused | New calibration work | Downstream characterization work |
|---|---|---|---|
| Electrical trigger/path timing | S0, MS-01, MS-02, T2-01, T1-01 | PT-01, CL-01 | None; import calibration bundle. |
| MIRcat external modes and state semantics | P0 mapping observation | MC-01, MD-01, MSW-01 | Exercise only approved modes. |
| HF2LI configuration and stream integrity | T2-01 EXT REF/DAQ route | HF-01, HF-02 | System-level settling and performance within qualified envelope. |
| Available optical power and beam metrology | P0 inventory plus available power-meter records | TR-01 and OM-01 qualify only resources required by the experiment claim grid; no energy meter is assumed | Average-power and beam measurements at conditions selected by experiment design; any mean pulse energy is explicitly derived rather than directly measured. |
| Optical attenuation splitter ratio and sample-plane transfer | P0 statement that no attenuator was installed | ATT-01 for used elements and both installed splitter ports | Apply identified transfer corrections without assuming 50/50. |
| Detector dark and illuminated transfer behavior | Installed-path inventory | DET-01, DET-02 | Measure platform sensitivity in accepted operating region. |
| Detector latency needed by optical timing | MS-01/MS-02 scope corrections and T1-01 electrical timing | DET-03 | Temporal instrument-response measurement. |
| Sample/reference power imbalance and dual-detector normalization | No completed quantitative evidence | DET-04 separates optical balance from detector/electronics balance and produces the wavelength-dependent normalization bundle | Import DET-04 in spectral sensitivity and biological analysis; do not repeat the balance calibration. |
| Spectral reference and axis | P0 polystyrene/Mylar observations | SP-01, SP-02 | Independent spectral validation and forward modeling. |
| Pump/probe beam output and geometry | No completed quantitative evidence | Metrology resources only in OM-01/ATT-01 | PB-01 through OV-01. |
| Operational optical timing | MS-01/MS-02/T1-01 corrections | OP-01, CL-01 | Import corrected time origin; measure complete response without redoing path timing. |
| Finite rare-pump exposure and observed-event reconciliation | Completed electrical routes plus OP-01 optical timing | FE-01 qualifies only direct-532 and OPO-540 event admission normal stop and no-emission fault paths | Import the finite-event controller; biological dose recovery and photolysis remain experiment work. |
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
  `docs/experiment_requirement_campaign_crosswalk.md`.
