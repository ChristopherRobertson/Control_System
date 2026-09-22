"""Device-owned settings groups for compact measurement pages.

These helpers only arrange widgets; acquisition and device sessions stay with
the existing host and experiment adapters.
"""
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLineEdit, QSizePolicy
from control_app.workflows.phase_scan import PhaseScanSettings


class AutomaticValueInput(QComboBox):
    """Independent optional numeric override with cached supported choices."""

    def __init__(self):
        super().__init__()
        self.setEditable(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(50)
        self.addItem("Automatic")

    def text(self):
        value = self.currentText().strip()
        return "" if value.lower() in ("automatic", "auto") else value

    def setText(self, value):
        self.setCurrentText(value or "Automatic")

    def clear(self):
        self.setCurrentIndex(0)

    def placeholderText(self):
        return "Automatic"

    def set_choices(self, values):
        wanted = self.text()
        blocked = self.blockSignals(True)
        super().clear()
        self.addItem("Automatic")
        for value in sorted(set(values)):
            self.addItem(f"{value:.12g}", value)
        self.setText(wanted)
        self.blockSignals(blocked)


class HF2LIValueInput(AutomaticValueInput):
    """Automatic or a device-supported value; never a free-text hardware request."""

    def __init__(self):
        super().__init__()
        self.setEditable(False)
        self.unit = ""
        self.automatic_value = None
        self.setItemText(0, "Pending settings")

    def text(self):
        if self.currentIndex() == 0:
            return ""
        value = self.currentData()
        return str(value) if value is not None else self.currentText().removesuffix(" " + self.unit).strip()

    def display_automatic(self, value, unit=""):
        self.unit, self.automatic_value = unit, value
        blocked = self.blockSignals(True)
        self.setItemText(0, f"{value:.7g} {unit}".strip() if isinstance(value, (float, int)) else "Pending settings")
        self.setItemData(0, "Calculated automatically; select a value to override", 3)
        for index in range(1, self.count()):
            number = self.itemData(index)
            if isinstance(number, (float, int)):
                self.setItemText(index, f"{number:.7g} {unit}".strip())
        self.blockSignals(blocked)

    def set_choices(self, values):
        super().set_choices(values)
        self.display_automatic(self.automatic_value, self.unit)

    def setCurrentText(self, value):
        value = str(value or "Automatic")
        if value.lower() in ("auto", "automatic"):
            self.setCurrentIndex(0)
            return
        index = self.findText(value)
        if index < 0:
            try:
                index = self.findData(float(value.removesuffix(" " + self.unit).strip()))
            except ValueError:
                pass
        if index < 0:
            # Retain saved requests visibly, without offering unverified values
            # as new choices. The planner must still validate the request.
            self.addItem(value)
            index = self.count() - 1
            self.model().item(index).setEnabled(False)
        self.setCurrentIndex(index)


def hf2li_choices(capabilities, role, kind, order=None):
    profile = capabilities.get(role, capabilities if role == "sample" else {})
    if kind == "order":
        return profile.get("orders", ())
    if kind == "rate":
        return profile.get("rates_sps", ())
    by_order = profile.get("timeconstants_by_order", {})
    if order is not None:
        return by_order.get(int(order), by_order.get(str(int(order)), ()))
    return sorted({value for values in by_order.values() for value in values})


def populate_hf2li_choices(panel, experiment, capabilities):
    """Publish one detached startup enumeration to all experiment editors."""
    editor = panel.settings_widget
    if experiment == "microsecond_stroboscopy":
        editor.set_capability_choices(capabilities)
        return
    fields = getattr(editor, "override_inputs", getattr(editor, "fields", {}))
    editor._hf2_choices = capabilities
    if not getattr(editor, "_hf2_binding_connected", False):
        editor._hf2_binding_connected = True
        editor.changed.connect(lambda: populate_hf2li_choices(panel, experiment, editor._hf2_choices))
    orders = {}
    for key, control in fields.items():
        if isinstance(control, HF2LIValueInput) and "order" in key and control.text():
            orders["reference" if "reference_" in key else "sample"] = float(control.text())
    for key, control in fields.items():
        if not isinstance(control, HF2LIValueInput):
            continue
        role = "reference" if key.startswith("reference_") or "reference_" in key else "sample"
        kind = "order" if "order" in key else "rate" if "rate" in key else "timeconstant"
        control.set_choices(hf2li_choices(capabilities, role, kind, orders.get(role)))


def settings_section(layout, title):
    group = QGroupBox(title)
    form = QFormLayout(group)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    layout.addWidget(group)
    return group, form


def run_label_section(layout):
    _, form = settings_section(layout, "Run Label")
    editor = QLineEdit()
    editor.setObjectName("run_label")
    editor.setPlaceholderText("Optional label")
    form.addRow("Run Label", editor)
    return editor


def compact_settings_page(panel):
    """Keep actions outside the scrolled settings and reserve plot space."""
    panel.left_panel.setMinimumWidth(370)
    panel.right_layout.setSpacing(5)
    panel.summary_form.setVerticalSpacing(3)
    panel.result_layout.setSpacing(4)
    panel.settings_layout.setSpacing(6)


class PhaseLaserSections:
    """The Phase Scan laser control list, shared without changing Phase Scan.

    Existing experiment editors can supply controls already bound to their
    native settings. Additional laser requests remain separate from timer
    implementation details and are retained in ``laser_settings``.
    """

    PUMP_DEFAULTS = {"pump_repetition_rate_hz": 10., "fire_to_qswitch_us": 250., "pump_wavelength_nm": 540.}
    MIRCAT_DEFAULTS = {key: getattr(PhaseScanSettings(), key) for key in
                      ("probe_repetition_rate_hz", "probe_pulse_width_ns", "qcl_current_ma", "scan_speed_cm1_s")}

    GROUPS = (
        ("Nd:YAG Settings", (
            ("pump_repetition_rate_hz", "Repetition Rate", " Hz", 10., 6),
            ("fire_to_qswitch_us", "FIRE - Q-SWITCH Delay", " µs", 1e6, 3),
            ("pump_wavelength_nm", "Wavelength", " nm", 10000., 3),
        )),
        ("MIRcat Settings", (
            ("start_wavenumber_cm1", "Start", " cm⁻¹", 10000., 3),
            ("stop_wavenumber_cm1", "Stop", " cm⁻¹", 10000., 3),
            ("scan_speed_cm1_s", "Scan Speed", " cm⁻¹/s", 10000., 3),
            ("probe_repetition_rate_hz", "Repetition Rate", " Hz", 1e7, 3),
            ("probe_pulse_width_ns", "Pulse Width", " ns", 1e6, 3),
            ("qcl_current_ma", "Current", " mA", 10000., 3),
        )),
    )

    def __init__(self, layout, changed, *, supplied=None, scanning=False, allow_single_point=False):
        supplied = supplied or {}
        self.inputs, self.extra_inputs = {}, {}
        self.scanning, self.range_edited, self._points = scanning, False, []
        self.allow_single_point = allow_single_point
        for title, fields in self.GROUPS:
            _, form = settings_section(layout, title)
            for key, label, suffix, maximum, decimals in fields:
                if not scanning and key == "scan_speed_cm1_s":
                    key, label, suffix = "step_size_cm1", "Step Size", " cm⁻¹"
                control = supplied.get(key)
                if control is None:
                    control = QDoubleSpinBox()
                    control.setObjectName(key)
                    control.setDecimals(decimals)
                    control.setRange(0, maximum)
                    control.setSuffix(suffix)
                    control.setSpecialValueText("Automatic")
                    control.setKeyboardTracking(False)
                    if key in self.PUMP_DEFAULTS:
                        control.setMinimum(.000001 if key == "pump_repetition_rate_hz" else 1.)
                        control.setSpecialValueText("")
                        control.setValue(self.PUMP_DEFAULTS[key])
                    elif key in self.MIRCAT_DEFAULTS:
                        control.setMinimum(.001)
                        control.setSpecialValueText("")
                        control.setValue(self.MIRCAT_DEFAULTS[key])
                    if key == "pump_wavelength_nm":
                        control.setReadOnly(True)
                        control.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
                    self.extra_inputs[key] = control
                    if not scanning and key in ("start_wavenumber_cm1", "stop_wavenumber_cm1", "step_size_cm1"):
                        control.valueChanged.connect(lambda *_: self._range_changed(changed))
                        control.lineEdit().textEdited.connect(lambda *_: self._range_changed(changed))
                    else:
                        control.valueChanged.connect(changed)
                if key in ("probe_repetition_rate_hz", "probe_pulse_width_ns"):
                    control.setToolTip("External T660 trigger setting. MIRcat internal settings are 2.1 MHz and 142 ns (provisional).")
                kind = {"start_wavenumber_cm1": "wavenumber", "stop_wavenumber_cm1": "wavenumber",
                        "qcl_current_ma": "current", "probe_pulse_width_ns": "width"}.get(key)
                if kind:
                    from .laser_settings import constrain_mircat_control
                    constrain_mircat_control(control, kind)
                self.inputs[key] = control
                form.addRow(label, control)
                if key == "pump_wavelength_nm":
                    control.setToolTip("Requested pump wavelength, retained with the run. Set the OPO wavelength on the instrument; this procedure has no automatic OPO wavelength actuator.")
                if key == "pump_repetition_rate_hz":
                    control.setToolTip("Maximum requested pump repetition rate. Observation, recovery and the experiment procedure can require slower isolated events.")

    def values(self):
        return {key: control.value() for key, control in self.extra_inputs.items()
                if key not in ("start_wavenumber_cm1", "stop_wavenumber_cm1", "step_size_cm1", "scan_speed_cm1_s") and control.value() != 0}

    def apply(self, values):
        for key, control in self.extra_inputs.items():
            if key in ("start_wavenumber_cm1", "stop_wavenumber_cm1", "step_size_cm1"):
                continue
            blocked = control.blockSignals(True)
            control.setValue(values.get(key) or self.PUMP_DEFAULTS.get(key, self.MIRCAT_DEFAULTS.get(key, 0)))
            control.blockSignals(blocked)

    def restore_automatic(self):
        self.apply({})

    def _range_changed(self, changed):
        self.range_edited = True
        self._update_step_enabled()
        changed()

    def _update_step_enabled(self):
        if self.scanning or not self.allow_single_point:
            return
        start, stop = (self.inputs[key] for key in ("start_wavenumber_cm1", "stop_wavenumber_cm1"))
        single = bool(start.cleanText().strip() and stop.cleanText().strip() and start.value() == stop.value())
        self.inputs["step_size_cm1"].setEnabled(not single)

    def set_points(self, points):
        if self.scanning:
            return
        self._points = list(points)
        from math import isclose
        increment = points[1]-points[0] if len(points) > 1 else 1.
        step = abs(increment)
        regular = step > 0 and all(isclose(b-a, increment, abs_tol=1e-8) for a, b in zip(points, points[1:]))
        for key, value in (("start_wavenumber_cm1", points[0] if points else 0),
                           ("stop_wavenumber_cm1", points[-1] if points else 0),
                           ("step_size_cm1", step if regular else 0)):
            control = self.inputs[key]
            blocked = control.blockSignals(True)
            control.setSpecialValueText("Loaded custom grid" if key == "step_size_cm1" and not regular else "")
            control.setValue(value)
            if not points and key in ("start_wavenumber_cm1", "stop_wavenumber_cm1"):
                control.clear()
                control.lineEdit().setPlaceholderText("Enter wavenumber")
            control.blockSignals(blocked)
        self.range_edited = False
        self._update_step_enabled()

    def points(self):
        from decimal import Decimal
        missing = [f"Set {label} Wavenumber to proceed" for key, label in
                   (("start_wavenumber_cm1", "Start"), ("stop_wavenumber_cm1", "Stop"))
                   if not self.inputs[key].cleanText().strip()]
        if missing:
            raise ValueError("\n".join(missing))
        if not self.range_edited:
            return list(self._points)
        start, stop, step = (Decimal(str(self.inputs[key].value())) for key in
                            ("start_wavenumber_cm1", "stop_wavenumber_cm1", "step_size_cm1"))
        if self.allow_single_point and start == stop:
            return [float(start)]
        if start <= 0 or stop <= 0 or step <= 0:
            raise ValueError("MIRcat Start, Stop and Step Size must be positive")
        if start <= stop:
            if self.allow_single_point:
                raise ValueError("Set Stop Wavenumber to proceed: it must be less than or equal to Start Wavenumber")
            raise ValueError("Start wavenumber must be greater than Stop wavenumber")
        count = (start-stop)/step
        if count != count.to_integral_value():
            raise ValueError("MIRcat Stop must lie on the grid defined by Start and Step Size")
        if count > 100000:
            raise ValueError("MIRcat range exceeds 100001 measurement positions")
        increment = -step
        return [float(start+i*increment) for i in range(int(count)+1)]
