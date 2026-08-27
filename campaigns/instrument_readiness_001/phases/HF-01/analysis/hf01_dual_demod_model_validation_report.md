# HF-01 dual-demodulator model validation

Analysis: `HF01-ANALYSIS-DUAL-DEMOD-MODEL-001`  
Criterion: `HF01-MODEL-RESIDUAL-v3`  
Overall status: **PASS**

The analysis uses exact-timestamp complex division of demodulator 0 by
demodulator 1. The demodulator 1 transfer function is explicitly restored
to reconstruct the filter-under-test response.

| Anchor | Integrity | Magnitude | Phase | Complex RMS | Cutoff | Steps | Group delay | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fast | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| intermediate | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| slow | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

The intermediate positive/negative pair is **PASS**. Computational
selection is authorized under the frozen phase plan.
