# UI rendering evidence

Captured 2026-09-10 from the actual `ControlSystemMainWindow` with an isolated
ownership coordinator and a blocked hardware handler. Plotted values are saved
synthetic example data for layout inspection, not physical measurements.

- `single-1100x780.png`: Nanosecond Stroboscopy at 1100 × 780.
- `dual-1100x780.png`: Dual-Detector Nanosecond Stroboscopy at 1100 × 780.
- `dual-advanced-1100x780.png`: independent Auto overrides expanded.
- `phase-scan-reference.png`: unchanged accepted Phase Scan visual reference.
  Its existing minimum height expands a requested 1100 × 780 view to 1100 × 918.

The new tabs have zero outer horizontal/vertical scroll range at 1100 × 780.
Expanded Advanced uses its inner vertical scroll and has no horizontal overflow.
The layout follows the reference's narrow input/action pane, compact derived
summary, plot toolbar, and linked numeric/slider slices.
