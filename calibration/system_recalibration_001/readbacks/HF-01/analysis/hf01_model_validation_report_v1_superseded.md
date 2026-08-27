# HF-01 model-validation disposition

Analysis ID: `HF01-ANALYSIS-MODEL-VALIDATION-001`  
Criterion: `HF01-MODEL-RESIDUAL-v1`  
Phase disposition: `STOPPED_PENDING_PROSPECTIVE_AMENDMENT`

## Result

The HF2LI manufacturer response model is **not validated** by the retained HF-01
evidence. This is not a claim that the physical model is globally rejected.
The frozen criterion cannot pass because one primary anchor fails acquisition
repeatability and four mandatory phase-domain metrics are not identifiable from
the recorded clock domains.

The intermediate and installed slow anchors agree with the manufacturer model
for the available magnitude, cutoff, and step-response checks:

| Region | Retained acquisition | Installed time constant | Magnitude RMS residual | Cutoff residual | Six step transitions |
|---|---|---:|---:|---:|---|
| Fast | `HF01-ANCHOR-FAST-R2-001` | 4.000020 us | 0.082501 | +19.283% | Pass |
| Intermediate | `HF01-ANCHOR-INTERMEDIATE-R1-001` | 1.001889 ms | 0.000444 | -0.055% | Pass |
| Slow | `HF01-ANCHOR-SLOW-R3-001` | 71.153100 ms | 0.000334 | -0.055% | Pass |

The fast residuals are not interpreted as a manufacturer-model rejection. Its
first zero-offset carrier scale differs from the other two replicates, producing
a 0.350663 span-over-mean repeatability result. The acquisition therefore fails
the frozen three-independent-window integrity requirement.

The slow acquisition was requested at 100 ms, but the installed node read back
71.153100 ms. Zero-output diagnostics show that write order does not change the
value and that 71.153100 ms is closer to 100 ms than the next installed value,
142.271737 ms. Response predictions therefore use the installed readback, under
which the slow magnitude and step data pass.

`HF01-TARGET-HIGHORDER-001` is retained as diagnostic evidence only. It passes
the available magnitude, cutoff, and settling checks at its installed readback,
but it was invoked by an earlier analysis that compared slow data with the
requested 100 ms rather than the installed 71.153100 ms. It cannot count as a
primary anchor or repair the clock-domain limitation.

## Unevaluable frozen metrics

The PicoScope carrier-input phase and HF2LI complex output were not synchronized
to a shared marker during the response anchors. The HF2LI `status/time` command
brackets are quantized at approximately 65.5 ms, which is not sufficient to
remove the per-frequency source phase and delay. Consequently these required
metrics have no valid pass/fail value:

- per-frequency phase residual;
- normalized RMS complex residual;
- group delay; and
- intermediate positive/negative phase-sign reversal.

Magnitude symmetry for the intermediate positive/negative cutoff pair passes
with a fractional difference of 0.002083, but that does not substitute for the
required phase-sign check.

## Stopping decision

The single targeted-point allowance has been used, and it does not fix the
unsynchronized response design. Under the frozen stopping rule, HF-01 stops for
a prospective amendment. No supported-parameter computation, experiment
configuration selection, boundary challenger, Signal Input 2 equivalence run,
reload confirmation, restoration, or canonical promotion is authorized from
this result.

`HF01-AMENDMENT-STOP-SAFE-STATE-001` verifies electronic safe idle: all T660
temporary outputs match the safe recipe, the PicoScope AWG is programmed to
zero, both HF2LI signal outputs are off, the external master clock is selected
and locked, and clip/sample-loss flags are clear. Temporary physical wiring
remains in place; no cable restoration is inferred.

The full machine-readable results are in
`analysis/hf01_model_validation_results.json`; point residuals are in
`analysis/hf01_model_validation_magnitude_residuals.csv`. Superseded analysis
drafts remain preserved with `invalid_draft` filenames and are excluded from
acceptance.
