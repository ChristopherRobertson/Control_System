# HF-01 single targeted high-order validation point

Declaration ID: `HF01-TARGET-DECLARATION-001`

This declaration was frozen after the three accepted anchor repeats were
acquired and before the targeted data were viewed. It invokes the one targeted
point permitted by `HF01-MODEL-RESIDUAL-v1`.

The fast first-order and intermediate fourth-order anchors bracket the
manufacturer response at their retained frequencies. The slow eighth-order,
100 ms anchor shows a localized high-order response discrepancy: cutoff-region
and out-of-band magnitudes are materially larger than the eighth-order cascade
prediction despite an order-8 readback. The high-order region is not bracketed
by either passing anchor.

The targeted point is therefore:

| Acquisition ID | Order | Time constant | Predicted -3 dB cutoff | Requested rate | Offsets |
|---|---:|---:|---:|---:|---|
| `HF01-TARGET-HIGHORDER-001` | 8 | 10 ms | 4.79 Hz | 100 Sa/s | +0.479, +4.79, +23.95 Hz |

This retains order 8 while moving one decade faster, separating a general
high-order implementation discrepancy from a slow-record/reference-drift
artifact. It uses the same connected-zero, three rising, three falling, and
three offset-carrier structure as the frozen anchors, with at least 250 ms for
each offset so the eighth-order cascade has more than its 99% settling
allowance.

This is not an experiment preset and does not authorize any second targeted
point. If this point also rejects the manufacturer model, HF-01 stops for a
prospective amendment without computational configuration selection.
