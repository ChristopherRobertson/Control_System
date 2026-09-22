"""Visible experiment names and ordering, independent of native record identity."""

EXPERIMENT_ORDER = (
    "steady_state_slow_scan",
    "fixed_wavenumber_kinetics",
    "nanosecond_stroboscopy",
    "microsecond_stroboscopy",
    "repeated_rapid_scan",
    "phase_scan",
)

EXPERIMENT_TITLES = {
    "steady_state_slow_scan": "Slow Scan",
    "fixed_wavenumber_kinetics": "Fixed Wavenumber",
    "nanosecond_stroboscopy": "Nanosecond Stroboscopy",
    "microsecond_stroboscopy": "Microsecond Stroboscopy",
    "single_pump_scan_burst": "Single Scan Phase Delay",
    "repeated_rapid_scan": "Rapid Scan Phase Delay",
    "phase_scan": "Phase Scan",
}


def tab_title(experiment_id: str, mode: str) -> str:
    """Return a UI label without changing experiment, preference or native IDs."""
    if mode not in ("single", "dual"):
        raise ValueError(f"Unsupported detector mode: {mode!r}")
    title = EXPERIMENT_TITLES.get(experiment_id, experiment_id.replace("_", " ").title())
    return f"DD {title}" if mode == "dual" else title
