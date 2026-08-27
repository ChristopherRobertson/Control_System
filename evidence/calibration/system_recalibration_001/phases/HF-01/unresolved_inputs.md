# HF-01 unresolved-input register

| ID | Status | Required input or observation | Disposition |
|---|---|---|---|
| `HF01-UIR-001` | `RESOLVED` | Current observed nonemitting/inhibit and shutter state for both laser systems | `HF01-OPCONF-001` records lasers off and the installed Nd:YAG/OPO interlock disconnected; `HF01-OPCONF-002` records shutters closed under the operator's standing convention and authorizes advance past repetitive safety checks. |
| `HF01-UIR-002` | `RESOLVED_WITH_LIMITATION` | Inspect the two available male BNC tees and two intended RG-58 cables; identify one passive DC-coupled tee and retain the second disconnected | Operator confirmed labels and the retained stimulus routes in `HF01-OPCONF-003`, then confirmed default wiring with the stimulus assembly and spare tee disconnected in `HF01-OPCONF-014`. Exact markings and cable lengths were not reported; connected PicoScope measurements and channel-equivalence results bound the applicable electrical path instead. |
| `HF01-UIR-003` | `USER_INPUT_REQUIRED` | Exact operational detector-output voltage interval | Detector phases remain the authority. HF-01 uses only its conservative electrical test envelope and does not claim it as a detector interval. |
| `HF01-UIR-004` | `USER_INPUT_REQUIRED` | Numeric final precision/bias thresholds and exact maximum record durations for sweep, HRP-C-CO, and MbCO remain unfrozen in the governing briefs | HF-01 reports applicability envelopes and uses the frozen waveform/feature constraints; it does not invent biological tolerances. A selection is valid only within the resulting envelope. |
| `HF01-UIR-005` | `RESOLVED` | Prospective authorization for exactly one replacement 10 Hz digital timing check after the first check's HF2 DIO export defect | `HF01-AUTH-AMEND-002` authorizes `HF01-TIMING10-R1-001` only. `HF01-TIMING10-001` remains preserved as rejected partial. |
| `HF01-UIR-006` | `RESOLVED` | Prospective authorization for one final device-resolved 10 Hz check and `HF01-TIMING-COPY-v2` | `HF01-AUTH-AMEND-003` authorizes exactly one `HF01-TIMING10-R2-001` execution using the frozen 1 ms/max-rate method; it authorizes no automatic retry. |
| `HF01-UIR-007` | `RESOLVED` | Prospective authorization for acquisition-window-corrected `HF01-TIMING10-R3-001` and necessary bounded repeats | `HF01-AUTH-AMEND-004` authorizes R3 and subsequent necessary HF-01 acquisition repeats without per-run permission. Each run remains uniquely identified and preserved. |
| `HF01-UIR-008` | `RESOLVED` | A phase-synchronized response-acquisition method and disposition of the invalid fast carrier replicate | `HF01-AUTH-AMEND-005`, `HF01-PLAN-v3`, and `HF01-MODEL-RESIDUAL-v3` authorize exactly three paired-demodulator anchors. The method uses reference-gated exact-timestamp ratios, explicit reference-filter correction, and one bounded constant paired-pipeline delay per anchor. |

No unresolved entry authorizes scope expansion. A missing or changed hash is not
an unresolved input and is never an operational gate.

`HF01-UIR-003` and `HF01-UIR-004` do not invalidate the electrical
characterization. They limit downstream use: DET-01/DET-02 must establish the
installed detector voltage/noise envelope, and AR-01/biological planning must
freeze experiment-specific distortion, precision, and duration thresholds.
The mandatory 1 us MbCO requirement is not an unresolved input; HF-01 produced
a hard negative result showing that no supported two-channel HF2LI setting can
preserve it.
