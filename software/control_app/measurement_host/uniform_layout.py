"""Shared experiment-page geometry and action vocabulary."""
from dataclasses import asdict, is_dataclass
from PySide6.QtWidgets import (QWidget, QGroupBox, QFormLayout, QHBoxLayout,
    QVBoxLayout, QLabel, QPushButton, QAbstractSpinBox, QComboBox, QLineEdit, QSplitter, QScrollArea, QSizePolicy)
from .settings_sections import HF2LIValueInput


def effective_hf2_values(panel, plan):
    def plain(v):
        return asdict(v) if is_dataclass(v) else v if isinstance(v, dict) else {}
    settings = plain(getattr(plan, "resolved_settings", None) or getattr(plan, "settings", {}))
    resolved = plain(getattr(plan, "resolved", {}))
    selected = plain(getattr(plan, "selected", {}))
    hf = plain(getattr(plan, "hf2_selection", {}))
    fields = getattr(getattr(panel, "settings_widget", None), "fields", {})
    fields = {**fields, **getattr(getattr(panel, "settings_widget", None), "override_inputs", {})}
    editor = getattr(panel, "settings_widget", None)
    for key, value in getattr(editor, "_controls", {}).items():
        fields[key] = value[0] if isinstance(value, tuple) else value
    fields.update(getattr(panel, "override_inputs", {}))
    fields.update(getattr(editor, "override_modes", {}))
    for key, control in fields.items():
        if not isinstance(control, (HF2LIValueInput, QComboBox)):
            continue
        if not isinstance(control, HF2LIValueInput) and not hasattr(panel, "runner"):
            continue
        role = "reference" if "reference" in key else "sample"
        profile = resolved.get(role) or selected.get("hf2li", {}).get(role) or hf.get(role) or hf
        kind = "order" if "order" in key else "rate_sps" if "rate" in key else "timeconstant_s"
        response = settings.get("response", {})
        value = profile.get(kind)
        if value is None:
            candidates = {"order": [f"{role}_filter_order", "filter_order", "hf2_order"],
                          "rate_sps": [f"{role}_rate_hz", "sample_rate_hz", "hf2li_rate_hz", "sample_rate_sps"],
                          "timeconstant_s": [f"{role}_filter_timeconstant_s", "filter_time_constant_s", "hf2_time_constant_s", "time_constant_s"]}[kind]
            value = next((source[k] for source in (response, settings, selected) for k in candidates if source.get(k) is not None), None)
        unit = "Sa/s" if kind == "rate_sps" else "s" if kind == "timeconstant_s" else ""
        if isinstance(control, HF2LIValueInput):
            control.display_automatic(value, unit)
        elif control.count():
            blocked = control.blockSignals(True)
            control.setItemText(0, f"{value:.7g} {unit}".strip() if isinstance(value, (float, int)) else "Pending settings")
            for i in range(1, control.count()):
                v = control.itemData(i)
                if isinstance(v, (float, int)):
                    control.setItemText(i, f"{v:.7g} {unit}".strip())
            control.blockSignals(blocked)


def standardize_experiment_page(panel, experiment, mode):
    phase = experiment == "phase_scan"
    splitter = panel.findChild(QSplitter)
    if splitter is None:
        return  # Optional measurement modules own their custom layout.
    left = splitter.widget(0)
    left.setFixedWidth(390)
    groups = panel.findChildren(QGroupBox)
    summary = next(g for g in groups if "experiment and effective" in g.title().lower())
    parent_layout = summary.parentWidget().layout()
    wrapper = QGroupBox("Instructions and Experiment Summary")
    wrapper.setMinimumHeight(180)
    layout = QVBoxLayout(wrapper)
    parent_layout.replaceWidget(summary, wrapper)
    summary.setTitle("")
    summary_scroll = QScrollArea()
    summary_scroll.setWidgetResizable(True)
    summary_scroll.setWidget(summary)
    summary_scroll.setMinimumHeight(0)
    summary_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
    summary_scroll.setMaximumHeight(170)
    layout.addWidget(summary_scroll)
    panel.instructions_group = wrapper
    hf_group = next(g for g in groups if g.title() == "HF2LI Settings")
    editor = getattr(panel, "settings_widget", None)
    candidates = {**getattr(editor, "fields", {}), **getattr(editor, "override_inputs", {}),
                  **getattr(editor, "override_modes", {}), **getattr(panel, "override_inputs", {})}
    hf_controls = {}
    for key, control in candidates.items():
        if isinstance(control, HF2LIValueInput) or (phase and key in panel.override_inputs):
            role = "reference" if "reference" in key else "sample"
            kind = "order" if "order" in key else "rate" if "rate" in key else "timeconstant"
            hf_controls[role, kind] = control
    def empty_layout(current):
        while current.count():
            item = current.takeAt(0)
            if item.widget():
                item.widget().hide()
            elif item.layout():
                empty_layout(item.layout())
    empty_layout(hf_group.layout())
    hf_body = QWidget()
    hf_form = QFormLayout(hf_body)
    for role in (("sample", "reference") if mode == "dual" else ("sample",)):
        for kind, title in (("order", "Filter Order"), ("timeconstant", "Time Constant"), ("rate", "Sample Rate")):
            control = hf_controls.get((role, kind))
            if control is not None:
                hf_form.addRow((role.title() + " " if mode == "dual" else "") + title, control)
                control.show()
    reset = QPushButton("Restore Automatic Settings")
    reset.clicked.connect(lambda: [control.setCurrentIndex(0) for control in hf_controls.values()])
    hf_form.addRow(reset)
    hf_group.layout().addWidget(hf_body)
    instructions = QWidget()
    instruction_layout = QVBoxLayout(instructions)
    instruction_layout.setContentsMargins(0, 0, 0, 0)
    instruction_layout.setSpacing(1)
    instruction_scroll = QScrollArea()
    instruction_scroll.setWidgetResizable(True)
    instruction_scroll.setWidget(instructions)
    instruction_scroll.setMaximumHeight(64)
    instruction_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
    layout.addWidget(instruction_scroll)
    # Move standalone status/instruction labels, keeping form row labels in place.
    form_labels = {form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget()
                   for form in left.findChildren(QFormLayout) for row in range(form.rowCount())
                   if form.itemAt(row, QFormLayout.ItemRole.LabelRole)}
    for label in left.findChildren(QLabel):
        if label not in form_labels:
            if hf_group.isAncestorOf(label):
                continue
            instruction_layout.addWidget(label)
    for group in left.findChildren(QGroupBox):
        if group.title() in ("Nd:YAG Settings", "Nd:YAG + OPO Settings"):
            group.setTitle("Nd:YAG + OPO Settings")
        group.setContentsMargins(0, 0, 0, 0)
        if group.layout():
            group.layout().setContentsMargins(10, 16, 10, 8)
            group.layout().setSpacing(6)
        if group.title() in ("Run Label", "Nd:YAG + OPO Settings", "MIRcat Settings", "HF2LI Settings"):
            group.setFixedWidth(330)
        for form in group.findChildren(QFormLayout):
            form.setVerticalSpacing(6)
            form.setHorizontalSpacing(10)
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                if item and isinstance(item.widget(), QLabel):
                    label = item.widget()
                    label.setFixedWidth(145)
                    if group.title() == "MIRcat Settings":
                        name = label.text().split(" (")[0]
                        names = {"Repetition rate": "Repetition Rate", "Pulse width": "Pulse Width", "Scan speed": "Scan Speed", "Number of Scans": "Number of Scans"}
                        name = names.get(name, name)
                        label.setText(name)
                        unit = {"Repetition Rate": "Hz", "Pulse Width": "ns", "Current": "mA"}.get(name)
                        field = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                        control = field.widget() if field else None
                        if unit and control is not None and not isinstance(control, QAbstractSpinBox):
                            form.takeAt(form.indexOf(control))
                            inline = QWidget()
                            inline_layout = QHBoxLayout(inline)
                            inline_layout.setContentsMargins(0, 0, 0, 0)
                            inline_layout.setSpacing(4)
                            inline_layout.addWidget(control, 1)
                            inline_layout.addWidget(QLabel(unit))
                            form.setWidget(row, QFormLayout.ItemRole.FieldRole, inline)
                    if group.title() == "HF2LI Settings":
                        label.setText(label.text().replace(" (Sa/s)", "").replace(" (s)", "").replace("CH1 sample rate", "Sample rate"))
        for control in [*group.findChildren(QAbstractSpinBox), *group.findChildren(QComboBox), *group.findChildren(QLineEdit)]:
            if not isinstance(control.parentWidget(), (QAbstractSpinBox, QComboBox)):
                control.setFixedHeight(26)
                control.setMinimumWidth(0)
                control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        if group.title() == "HF2LI Settings":
            resets = [b for b in group.findChildren(QPushButton) if "automatic" in b.text().lower()]
            if not resets:
                reset = QPushButton("Restore Automatic Settings")
                def restore(_checked=False, group=group):
                    for control in group.findChildren(HF2LIValueInput):
                        control.setCurrentIndex(0)
                reset.clicked.connect(restore)
                group.layout().addWidget(reset)
            for b in resets:
                b.setText("Restore Automatic Settings")
        heights = {"Run Label": 70, "Nd:YAG + OPO Settings": 140, "MIRcat Settings": 310, "HF2LI Settings": 270}
        if group.title() in heights:
            group.setFixedHeight(heights[group.title()])
    save = getattr(panel, "save_button", None) if phase else panel.save_plan_button
    load = panel.load_plan_button
    save.setText("Save Plan")
    load.setText("Load Plan")
    if phase:
        row = QHBoxLayout()
        save.parentWidget().layout().addLayout(row)
        row.addWidget(save); row.addWidget(load)
    else:
        panel.file_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
    bar = QWidget()
    actions = QHBoxLayout(bar)
    actions.setContentsMargins(0, 4, 0, 0)
    slots = [("Acquire Blank", ("background_button",) if phase else ("blank_button", "acquire_blank_button")),
             ("Load Blank", ("load_background_button",) if phase else ("load_blank_button",)),
             ("Acquire Sample (Pump Off)", ("test_button",) if phase else ("preliminary_button",)),
             ("Load Sample (Unpumped)", ("load_preliminary_button",)),
             ("Start Acquisition", ("start_button",)), ("Abort Acquisition", ("abort_button",)),
             ("New Run", ("new_run_button",))]
    panel.standard_actions = []
    for index, (title, names) in enumerate(slots):
        button = next((getattr(panel, name) for name in names if getattr(panel, name, None) is not None), None)
        unsupported = (index < 2 and mode == "dual") or (index == 2 and experiment == "steady_state_slow_scan")
        if button is None or unsupported:
            if button is not None:
                button.hide()
            button = QPushButton(title)
            button.setEnabled(False)
        button.setText(title)
        button.setMinimumWidth(0)
        button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        button.setStyleSheet("font-size: 11px")
        button.setFixedHeight(30)
        actions.addWidget(button, 1)
        button.show()
        panel.standard_actions.append(button)
    panel.layout().addWidget(bar)
    for widget in panel.findChildren(QWidget):
        if hasattr(widget, "figure") and hasattr(widget, "draw_idle"):
            widget.setMinimumHeight(100)
    effective_hf2_values(panel, panel.plan)
