"""Validation for optional laser requests, independent of UI and timer recipes."""
import math


def validate_laser_settings(values):
    limits = {"pump_repetition_rate_hz": 10., "fire_to_qswitch_us": 1e6,
              "pump_wavelength_nm": 10000., "qcl_current_ma": 10000.,
              "probe_repetition_rate_hz": 1e7, "probe_pulse_width_ns": 1e6}
    for key, value in values.items():
        if key not in limits:
            raise ValueError(f"Unsupported laser setting: {key}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= limits[key]:
            raise ValueError(f"{key} must be positive and at most {limits[key]:g}")
    validate_mircat_limits(current=values.get("qcl_current_ma"), width=values.get("probe_pulse_width_ns"))
    return values


# Provisional installed optical settings; external T660 controls are independent.
MIRCAT_INTERNAL_RATE_HZ = 2_100_000.0
MIRCAT_INTERNAL_WIDTH_NS = 142.0


MIRCAT_LIMITS = {"current": (250., 1000., "MIRcat current", "mA"),
                 "width": (21., 1005., "MIRcat pulse width", "ns"),
                 "wavenumber": (1639., 2077., "Wavenumber", "cm^-1")}


def validate_mircat_limits(*, current=None, width=None, wavenumbers=()):
    for kind, values in (("current", (current,)), ("width", (width,)), ("wavenumber", wavenumbers)):
        low, high, label, unit = MIRCAT_LIMITS[kind]
        for value in values:
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or
                                      not math.isfinite(value) or not low <= value <= high):
                raise ValueError(f"{label} must be between {low:g} and {high:g} {unit}")


def constrain_mircat_control(control, kind):
    from PySide6.QtWidgets import QDoubleSpinBox, QComboBox
    from PySide6.QtGui import QDoubleValidator
    low, high, label, unit = MIRCAT_LIMITS[kind]
    if isinstance(control, QDoubleSpinBox):
        blocked = control.blockSignals(True)
        control.setRange(low, high)
        control.setSpecialValueText("")
        control.blockSignals(blocked)
    else:
        editor = control.lineEdit() if isinstance(control, QComboBox) else control
        if editor is not None:
            editor.setValidator(QDoubleValidator(low, high, 9, editor))
    control.setToolTip(f"{label}: {low:g}–{high:g} {unit}.")
