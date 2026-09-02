"""Measured absorbance surface: X=wavenumber, Y=absorbance, Z=pump age."""
from __future__ import annotations

import numpy as np


def make_surface_figure(result):
    from matplotlib.figure import Figure
    from matplotlib import colormaps
    from matplotlib.colors import Normalize
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    figure = Figure(figsize=(8, 5), layout="constrained")
    axes = figure.add_subplot(111, projection="3d")
    values = np.asarray(result["absorbance"])
    if not np.isfinite(values).any():
        raise ValueError("No valid measured absorbance values for a 3D map")
    # Preserve holes even when decimating: every point within a display cell
    # must be supported, not just its four corners.
    shift_ms = float(result.get("display_pump_time_ms", 0))
    x, z = np.meshgrid(result["wavenumber_cm1"], np.asarray(result["time_s"]) * 1000 + shift_ms)
    normalizer = Normalize(vmin=np.nanmin(values), vmax=np.nanmax(values))
    rows = np.linspace(0, values.shape[0]-1, min(values.shape[0], 256), dtype=int)
    columns = np.linspace(0, values.shape[1]-1, min(values.shape[1], 256), dtype=int)
    holes = np.pad((~np.isfinite(values)).astype(np.int64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    vertices, heights = [], []
    for top, bottom in zip(rows[:-1], rows[1:]):
        for left, right in zip(columns[:-1], columns[1:]):
            invalid = holes[bottom+1, right+1] - holes[top, right+1] - holes[bottom+1, left] + holes[top, left]
            if invalid:
                continue
            positions = ((top, left), (bottom, left), (bottom, right), (top, right))
            vertices.append([(x[r, c], values[r, c], z[r, c]) for r, c in positions])
            heights.append(np.mean([values[r, c] for r, c in positions]))
    if vertices:
        axes.add_collection3d(Poly3DCollection(vertices, facecolors=colormaps["viridis"](normalizer(heights)),
                                             edgecolors="none"))
    else:
        valid = np.isfinite(values)
        axes.scatter(x[valid], values[valid], z[valid], s=5)
    axes.auto_scale_xyz(x.ravel(), values[np.isfinite(values)], z.ravel())
    axes.set_xlabel("Wavenumber (cm⁻¹)", labelpad=9)
    axes.set_ylabel("Absorbance", labelpad=10)
    centered = "display_pump_time_ms" in result
    electrical = "electrical_sync" in result.get("pump_reference_bases", [])
    reference_label = "Pump sync" if electrical else "Pump"
    axes.set_zlabel(f"Time (ms; {reference_label.lower()} at {shift_ms:g})" if centered else "Time after pump (ms)", labelpad=9)
    axes.invert_xaxis()
    axes.invert_zaxis()
    axes.view_init(elev=20, azim=25, vertical_axis="y")
    if centered:
        window = result.get("observation_window_s")
        if window:
            lower, upper = np.asarray(window)*1000+shift_ms
            axes.set_zlim(upper, lower)
            if upper-lower <= 10:
                axes.set_zticks(np.arange(np.ceil(lower*2)/2, upper+1e-9, .5))
        axes.plot([np.min(x), np.max(x)], [np.nanmin(values)]*2, [shift_ms]*2, color="#b96323", ls="--")
    title = "Reconstructed absorbance"
    if result.get("completion_status") == "INCOMPLETE_MISSING_PULSE_COVERAGE":
        title += " · INCOMPLETE MISSING-PULSE COVERAGE · NOT FOR PUBLICATION"
        figure.text(.5, .5, "INCOMPLETE · NOT FOR PUBLICATION", ha="center", va="center",
                    rotation=28, fontsize=24, color="#b00020", alpha=.22, weight="bold")
    elif not result.get("publication_eligible", False):
        title += " · EXPLORATORY PROOF OF CONCEPT · NOT FOR PUBLICATION"
        figure.text(.5, .5, "EXPLORATORY · NOT FOR PUBLICATION", ha="center", va="center",
                    rotation=28, fontsize=22, color="#b00020", alpha=.20, weight="bold")
    elif result.get("provisional"):
        title += " · PROVISIONAL wavenumber axis"
    elif electrical:
        title += " · electrical pump-sync reference"
    axes.set_title(title)
    return figure
