"""Live numeric input feedback shared by experiment previews."""
import re
from PySide6.QtWidgets import QAbstractSpinBox, QFormLayout


def live_parameter_updates(widget, callback):
    for control in widget.findChildren(QAbstractSpinBox):
        control.setKeyboardTracking(True)
        control.lineEdit().textEdited.connect(callback)


def required_parameter_prompts(widget):
    prompts = []
    for form in widget.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            field = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            label = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            control = field.widget() if field else None
            if not isinstance(control, QAbstractSpinBox) or control.isHidden() or not control.isEnabled():
                continue
            if control.hasAcceptableInput():
                continue
            name = label.widget().text() if label and label.widget() else control.objectName()
            name = {"Start": "Start Wavenumber", "Stop": "Stop Wavenumber"}.get(name, name)
            prompts.append(f"Set {name} to proceed")
    return tuple(dict.fromkeys(prompts))


def plan_parameter_prompts(issues):
    prompts = []
    for issue in issues:
        for message in str(issue).splitlines():
            if message.startswith("Set ") or any(word in message.lower() for word in ("device", "startup", "capabilit", "connection")):
                prompts.append(message)
            else:
                subject = re.split(r"\s+(?:must|requires?|cannot|should)\b", message, maxsplit=1)[0]
                if subject != message:
                    subject = subject.removeprefix("Selected ").replace("_", " ")
                    prompts.append(f"Set {subject} to proceed: {message}")
                else:
                    prompts.append(f"Set valid procedure parameters to proceed: {message}")
    return "\n".join(dict.fromkeys(prompts))
