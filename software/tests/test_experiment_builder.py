from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import yaml

from control_app.experiments.builder import ExperimentBuilder
from control_app.experiments.engine import ExperimentEngine, ServiceCapabilityAdapter
from control_app.experiments.models import ExperimentDefinition, ExperimentSchemaError
from control_app.experiments.validation import validate_experiment


def _document():
    fixture = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "experiment_builder"
        / "mircat_hf2li_sweep.yaml"
    )
    with fixture.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class ExperimentBuilderTests(unittest.TestCase):
    def test_definition_round_trip_and_immutable_plan(self):
        builder = ExperimentBuilder()
        definition = builder.create(_document())
        self.assertEqual(builder.validate(), ())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved = builder.save(root / "definition.json")
            self.assertEqual(ExperimentDefinition.load(saved).experiment_id, definition.experiment_id)
            plan = builder.configure(root / "plan.json")
            self.assertTrue(json.loads((root / "plan.json").read_text())["stop_actions"])
            with self.assertRaises(TypeError):
                plan.resource_ownership["mircat"] = "other"

    def test_unknown_schema_and_capabilities_are_rejected(self):
        document = _document()
        document["python"] = "import os"
        with self.assertRaises(ExperimentSchemaError):
            ExperimentDefinition.from_dict(document)
        document = _document()
        document["devices"][1]["capabilities"]["raw_sdk_call"] = "danger"
        errors = validate_experiment(ExperimentDefinition.from_dict(document))
        self.assertTrue(any(error.code == "unknown_capability" for error in errors))

    def test_trigger_wiring_duty_cycle_and_prohibited_routes(self):
        document = _document()
        document["devices"] = [item for item in document["devices"] if item["device"] != "t660_1"]
        document["required_devices"].remove("t660_1")
        document["resource_ownership"].pop("t660_1")
        document["metadata"]["routes"] = ["mircat.db9_pin_8"]
        next(item for item in document["devices"] if item["device"] == "mircat")["capabilities"]["pulse_width_ns"] = 1000.0
        codes = {error.code for error in validate_experiment(ExperimentDefinition.from_dict(document))}
        self.assertTrue({"trigger_route", "duty_cycle", "prohibited_route"} <= codes)

    def test_external_process_trigger_remains_unavailable(self):
        document = _document()
        next(item for item in document["devices"] if item["device"] == "mircat")["capabilities"]["process_trigger_mode"] = "external"
        errors = validate_experiment(ExperimentDefinition.from_dict(document))
        self.assertTrue(any(error.code == "unconfirmed_process_trigger" for error in errors))

    def test_pump_requires_its_upstream_trigger_and_both_spares_are_prohibited(self):
        document = _document()
        document["required_devices"].append("t660_2")
        document["resource_ownership"]["t660_2"] = "experiment_engine"
        document["devices"].append({"device": "t660_2", "capabilities": {"channel_a_ndyag_fire": True}})
        errors = validate_experiment(ExperimentDefinition.from_dict(document))
        self.assertTrue(any(error.code == "trigger_route" for error in errors))
        source = next(item for item in document["devices"] if item["device"] == "t660_1")
        source["capabilities"]["channel_c_t660_2_trigger"] = True
        errors = validate_experiment(ExperimentDefinition.from_dict(document))
        self.assertFalse(any(error.code == "trigger_route" for error in errors))
        for unit in ("t660_1", "t660_2"):
            document["metadata"]["routes"] = [f"{unit}.channel_d"]
            errors = validate_experiment(ExperimentDefinition.from_dict(document))
            self.assertTrue(any(error.code == "prohibited_route" for error in errors))

    def test_generic_engine_run_stop_abort_and_failure_cleanup(self):
        builder = ExperimentBuilder()
        builder.create(_document())
        with tempfile.TemporaryDirectory() as directory:
            plan = builder.configure(Path(directory) / "plan.json")
            calls = []
            adapters = {}
            for device in plan.resource_ownership:
                names = {step.capability for step in plan.steps if step.device == device}
                names |= {action.split(".", 1)[1] for actions in (plan.stop_actions, plan.abort_actions, plan.failure_cleanup_actions) for action in actions if action.startswith(device + ".")}
                adapters[device] = ServiceCapabilityAdapter({name: (lambda value, d=device, n=name: calls.append((d, n, value)) or "ok") for name in names})
            engine = ExperimentEngine(adapters)
            self.assertEqual(builder.run(engine, satisfied_prerequisites=set()).status, "blocked")
            self.assertEqual(builder.run(engine, satisfied_prerequisites=set(plan.safety_prerequisites)).status, "complete")
            self.assertEqual(builder.stop(engine).status, "stopped")
            self.assertEqual(builder.abort_to_safe(engine).status, "aborted")
            self.assertIn(("mircat", "disarm", True), calls)

    def test_processing_and_standard_export(self):
        builder = ExperimentBuilder()
        builder.create(_document())
        self.assertEqual(builder.process({"signal": [1, 2]})["data"]["signal"], [1, 2])
        with tempfile.TemporaryDirectory() as directory:
            target = builder.export(Path(directory) / "result.json")
            self.assertEqual(json.loads(target.read_text())["format_version"], "1.0")
