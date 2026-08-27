# Master dependency sequence

Status: **PROSPECTIVE DEPENDENCY VIEW; NO HARDWARE EXECUTION AUTHORIZED**

Authority: `campaigns/phase_registry.yaml`. This view replaces independent
calibration and characterization order statements. Domain-specific legacy sequences
remain detailed procedure catalogs, not competing execution schedules.

## Preserved completed inputs

`P0 -> S0 -> MS-01 -> MS-02 -> T2-01 -> T1-01 -> PT-01 -> MC-01`

`P0 -> TR-01 -> OM-01`

`T2-01 + TR-01 -> HF-01`

`P0 + TR-01 -> CH-00`

All retain their recorded statuses and evidence. WM-01 resumes its existing run.

## Current independent work and convergence

1. `HF-01 + CH-00 -> HF-01.1`.
2. In parallel where their own gates permit: `MD-01`, `MSW-01`, `HF-02`, `DET-01`,
   `SP-01`, `WM-01`, and analysis-only planning.
3. `WM-01 + OM-01 -> ATT-01 -> PB-02`.
4. Detector/source/cell readiness: `DET-02 -> DET-03/DET-04`, `QB-01`, and `SC-01`.
5. Installed geometry: `PB-02 + QB-01 + SC-01 + ATT-01 -> OG-01 -> OV-01`.
6. `HF-01.1 + MSW-01 + HF-02 + detector/source + OG-01 + OV-01 -> AR-01`.
7. `AR-01 + DET-04 + SC-01 + OG-01 -> PF-00`.
8. `SP-01 -> SV-01`; `SP-01 + AR-01 + DET-04 -> SP-02`.
9. `PF-00 + SP-02 + SV-01 + AR-01 + DET-04 -> SV-02A`.
10. Frozen SV-02A unlock only: `SV-02A -> SV-02B`.
11. Timing convergence: `ATT-01 + PB-02 + DET-03 -> OP-01 -> FE-01 -> CL-01`.
12. Core installed response: `SV-02B + CL-01 + AR-01 + OV-01 -> IR-01 -> PF-01
    -> RP-01`.
13. After SV-02B, end-to-end/reporting: `E2E-01`, `E2E-CH`, `RPT-01`, `PROM-01`, `RPT-CH`, and
    `PROM-CH` according to the registry.

## Biological branches

HRP is first: `R0/R1/R2/R3 -> R4 -> R5 -> R6 -> R7 -> optional R8 -> R9`.
R9 includes closeout and verified restoration.

Only after R9 and explicit handoff may the optional branch begin:
`QB-01M -> MB-00 -> MB-01 -> ... -> MB-07 -> optional MB-08 -> MB-09`.

PB-01 and the entire MbCO campaign are optional and do not block HRP core promotion.
