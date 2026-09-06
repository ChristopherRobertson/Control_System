"""Default wiring and finite recipe sequencing with no hardware transports."""
from copy import deepcopy
import json

import pytest

from control_app.devices.t660_service import T660Service
from control_app.workflows import timing_recipe_manager as recipes
from control_app.workflows.ndyag_alignment import recipe_with_ui_parameters
from control_app.workflows.t660_widget_commands import _manual_cha_recipe


def alignment_recipe(count=3):
    manager = recipes.TimingRecipeManager()
    source = manager.load_recipe("instrument/recipes/ndyag_alignment_10hz.yaml")
    return recipe_with_ui_parameters(source, q_switch_delay_us=250,
                                     shot_count=count, continuous=False)


def test_default_reference_and_finite_pump_recipes_resolve_to_distinct_units():
    manager = recipes.TimingRecipeManager()
    reference = manager.validate_recipe(_manual_cha_recipe(
        frequency="2MHz", delay="0ns", width="150ns"))["resolved_settings"]
    active = [(unit, channel) for unit, config in reference.items()
              for channel, settings in config["channels"].items() if settings["enabled"]]
    assert active == [("t660_1", "A")]
    finite = manager.validate_recipe(alignment_recipe())["resolved_settings"]
    assert list(finite) == ["t660_2", "t660_1"]
    assert finite["t660_2"]["finite_frame_count"] == 3
    assert finite["t660_2"]["channels"]["B"]["delay"] == "250us"
    assert finite["t660_1"]["channels"]["C"]["signal"] == "t660_2_trig_in"
    assert finite["t660_1"]["clock"]["shots"] == 0
    assert all(not config["channels"]["D"]["enabled"] for config in finite.values())


@pytest.mark.parametrize("fault", [None, "train_count", "frames_engine"])
def test_receiver_is_verified_before_source_starts_and_faults_are_saved(tmp_path, monkeypatch, fault):
    devices, events = {}, []

    class Device:
        validate_recipe_section = staticmethod(T660Service.validate_recipe_section)

        def __init__(self, name, config, **kwargs):
            self.name, self.source, self.closed = name, "SYN", False
            self.channels = {ch: {"enabled": True} for ch in "ABCD"}
            devices[name] = self

        def connect(self): pass
        def identify(self): pass
        def close(self): self.closed = True

        def set_trigger_source(self, source):
            self.source = source
            events.append((self.name, "source", source))

        def command(self, command, **kwargs):
            if command == "TRIG:SOUR OFF": self.source = "OFF"
            if command.startswith("CHAN:OFF "):
                self.channels[command[-1]]["enabled"] = False
            events.append((self.name, command))

        def apply_recipe(self, recipe):
            if self.name == "t660_2":
                assert devices["t660_1"].source == "OFF"
            else:
                assert ("t660_2", "verified") in events
            self.recipe = deepcopy(recipe)
            self.channels = deepcopy(recipe["channels"])
            self.source = recipe["trigger_source"]
            events.append((self.name, "apply"))

        def read_active_settings(self):
            def q(value): return {"ok": True, "response": str(value)}
            queries = {"trigger_source": q(self.source), "predivider": q(1),
                       "gate_mode": q(0), "burst": q("OFF"), "shots": q(0),
                       "frames_engine": q("RUNNING"), "train_count": q(0),
                       "trigger_input_polarity": q("POS"),
                       "trigger_input_termination": q("50OHM"),
                       "trigger_input_threshold_v": q(2), "synth_frequency": q("10Hz")}
            if self.name == "t660_2" and fault:
                queries[fault] = q(1 if fault == "train_count" else "OFF")
            channels = {}
            for channel, settings in self.channels.items():
                channels[channel] = {"enabled": q("ON" if settings["enabled"] else "OFF"),
                                     "delay_edge": q(settings.get("delay", "0ns")),
                                     "width_edge": q(settings.get("width", "150ns")),
                                     "polarity": q(settings.get("polarity", "positive")),
                                     "termination": q("50OHM"), "timing_mode": q("DW")}
            events.append((self.name, "verified"))
            return {"queries": queries, "channels": channels}

    monkeypatch.setattr(recipes, "T660Service", Device)
    output = tmp_path / "readback.json"
    if fault:
        with pytest.raises(recipes.TimingRecipeError, match="before advancing recipe"):
            recipes.TimingRecipeManager().apply_recipe(alignment_recipe(), output_path=output)
        assert ("t660_1", "apply") not in events
        assert all(device.source == "OFF" and not any(channel["enabled"] for channel in device.channels.values())
                   for device in devices.values())
        assert json.loads(output.read_text())["matches_recipe"] is False
    else:
        result = recipes.TimingRecipeManager().apply_recipe(alignment_recipe(), output_path=output)
        assert result["matches_recipe"] is True
        assert events.index(("t660_2", "verified")) < events.index(("t660_1", "apply"))
    assert all(device.closed for device in devices.values())
