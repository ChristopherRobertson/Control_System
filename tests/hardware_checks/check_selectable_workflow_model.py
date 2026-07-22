#!/usr/bin/env python3
"""Validate recipe discovery and the configure-before-run backend gate."""

from __future__ import annotations

import json
import tempfile

import _common  # noqa: F401

from control_app.config_loader import load_config_inventory
from control_app.ui.contracts import WorkflowCommand
from control_app.workflows.selectable_workflows import (
    configure_workflow,
    load_workflow_catalog,
    workflow_fingerprint,
)
from control_app.workflows.state_machine import WorkflowStateMachine


def main() -> int:
    catalog = load_workflow_catalog()
    assert set(catalog) == {"mircat_detector_alignment", "ndyag_alignment_10hz"}
    mircat = catalog["mircat_detector_alignment"]
    required_mircat = {
        "wavenumber_cm1",
        "qcl",
        "pulse_rate_hz",
        "pulse_width_ns",
        "current_ma",
        "use_t660_timing",
        "tec_timeout_s",
        "tune_timeout_s",
        "poll_interval_s",
    }
    assert required_mircat <= set(mircat["parameters"])

    with tempfile.TemporaryDirectory() as temporary:
        configured = configure_workflow(
            "mircat_detector_alignment", {}, output_dir=temporary
        )
        snapshot = json.loads(configured.saved_path.read_text(encoding="utf-8"))
        assert snapshot["parameters"] == configured.parameters
        assert snapshot["fixed_settings"]["mircat_gui_must_be_closed"] is True
        assert configured.fingerprint == workflow_fingerprint(
            configured.workflow_id, configured.parameters
        )

    machine = WorkflowStateMachine(
        operator="TEST",
        inventory=load_config_inventory(write_files=False),
        hardware_access=False,
    )
    blocked = machine(
        WorkflowCommand(
            device_key="workflow",
            command="workflow.run_selected",
            parameters={
                "fingerprint": "not-configured",
                "workflow_id": "mircat_detector_alignment",
                "workflow_parameters": {},
            },
            safety_approval=True,
        )
    )
    assert blocked.status == "blocked"
    assert "Configure & Save" in blocked.message

    saved = machine(
        WorkflowCommand(
            device_key="workflow",
            command="workflow.configure_selected",
            parameters={
                "workflow_id": "mircat_detector_alignment",
                "workflow_parameters": {},
            },
        )
    )
    assert saved.status == "complete"
    assert saved.data["configured_workflow_path"]
    no_approval = machine(
        WorkflowCommand(
            device_key="workflow",
            command="workflow.run_selected",
            parameters={
                "fingerprint": saved.data["fingerprint"],
                "workflow_id": "mircat_detector_alignment",
                "workflow_parameters": {},
            },
            safety_approval=False,
        )
    )
    assert no_approval.status == "blocked"
    assert "Safety approval" in no_approval.message
    print("PASS selectable workflow catalog and configure-before-run gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
