# Frozen experiment constraints imported for HF-01 selection

HF-01 imports only already-authorized requirement envelopes. It does not turn
planning examples into experiment recipes and does not invent missing
biological tolerances.

| Configuration ID to select | Retained waveform/claim family | Fastest required retained feature used by HF-01 | Interval and channel constraints | Explicit applicability limit |
|---|---|---|---|---|
| `HF01-SWEEP-SELECTED-001` | Continuous Mylar/spectral sweep with sample and reference channels plus digital markers | Preserve scan-dependent peak position/shape and direction without filter-settling bias; 40 cm-1/s is a representative planning case only | Two analog channels; planning span 2050 to 1650 cm-1 gives 10 s active and about 30 s with provisional padding | Exact scan rate, allowed peak shift/broadening, padding, and maximum record duration remain downstream decisions. |
| `HF01-HRP-SELECTED-001` | Rare-pump fixed-wavenumber recovery stream | Preserve instrument-resolved early time through the approximately second-scale recovery; 100 ms sampling is a planning candidate, not the HF-01 analog carrier | Two analog channels; representative 4.605 s 99% recovery planning interval; exact sample-specific recovery remains unresolved | The optional high-rate branch is not authorized here. Exact fastest accepted feature, precision, and stop duration remain downstream. |
| `HF01-MBCO-SELECTED-001` | Fixed-wavenumber rare-pump/geminate and solvent-rebinding recovery | Mandatory microsecond-to-millisecond content; use `1 us` as the fastest mandatory feature. The `180 ns` geminate value is optional unless later IRF evidence makes it identifiable. | Two analog channels; representative evaluation through at least 10 ms with possible longer recovery | HF-01 must report if HF2LI filter/readout limits cannot preserve 1 us; it must not claim the optional 180 ns feature. |

All three selections require no clipping, valid timestamp-aware sampling,
sustainable aggregate rate, and explicit applicability envelopes. Total-error
ranking uses measured noise and validated filter response. Where the governing
documents omit a numeric bias/precision limit, HF-01 reports a Pareto envelope
instead of silently manufacturing an acceptance threshold.
