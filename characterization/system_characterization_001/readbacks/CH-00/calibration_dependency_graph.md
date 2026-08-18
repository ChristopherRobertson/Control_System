# CH-00 calibration dependency graph

Only stable human-readable campaign, phase, quantity, and artifact identifiers
control dependency resolution. Hash or checksum matching is not a gate.

```mermaid
flowchart TD
  P0["P0 final decisions"] --> CH00["CH-00 minimum union"]
  MS["MS-01 / MS-02"] --> IR["IR-01"]
  T["T2-01 / T1-01 / PT-01"] --> E2E["IR-01 / E2E-CH"]
  TR["TR-01 identities and uncertainty bases"] --> OM["OM-01"]
  CH00 --> OM
  CH00 --> HF["HF-01 / HF-02"]
  CH00 --> SP["SP-01 / SP-02"]
  OM --> ATT["ATT-01"]
  ATT --> PB["PB-01 / PB-02"]
  HF --> AR["AR-01"]
  SP --> SV["SV-01 / SV-02"]
  PB --> IR
  AR --> IR
  SV --> PF["PF-01"]
  IR --> PF
  PF --> RP["RP-01"]
  RP --> E2E
  E2E --> RPT["RPT-CH"]
  RPT --> PROM["PROM-CH separate approval"]
```

Incomplete downstream calibration phases are declared dependencies, not
bypasses. CH-00 freezes what must later be linked; it does not promote or
validate their future results.
