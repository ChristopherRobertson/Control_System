# UI rendering evidence

Captured 2026-09-10 from the actual `ControlSystemMainWindow` with an isolated
ownership coordinator and a blocked hardware handler. Plotted values are saved
synthetic example data for layout inspection, not physical measurements.

The current override-form correction is shown in:

- `single-visible-overrides-1100x780.png`: all three HF2LI Auto choices visible.
- `dual-visible-overrides-1100x780.png`: all six independent sample/reference
  choices visible. Both views fit Save/Load Plan and acquisition actions without
  inner or outer scrolling; there is no disclosure control or QCL selector.

Earlier design evidence is preserved below:

- `single-1100x780.png`: Nanosecond Stroboscopy at 1100 × 780.
- `dual-1100x780.png`: Dual-Detector Nanosecond Stroboscopy at 1100 × 780.
- `dual-advanced-1100x780.png`: independent Auto overrides expanded.
- `phase-scan-reference.png`: unchanged accepted Phase Scan visual reference.
  Its existing minimum height expands a requested 1100 × 780 view to 1100 × 918.

The earlier tabs had zero outer horizontal/vertical scroll range at 1100 × 780.
Their expanded Advanced used an inner vertical scroll without horizontal overflow.
The layout follows the reference's narrow input/action pane, compact derived
summary, plot toolbar, and linked numeric/slider slices.
