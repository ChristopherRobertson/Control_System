from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

import yaml

from control_app.devices.t660_service import (
    T660ConfigurationError,
    T660Service,
)
from control_app.workflows.timing_recipe_manager import (
    TimingRecipeError,
    TimingRecipeManager,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class _RecordingT660Service(T660Service):
    def __init__(self, *, role: str = "master_timing_trains_frames") -> None:
        super().__init__("t660_test", {"role": role})
        self.commands: list[tuple[str, bool]] = []

    def command(
        self,
        command: str,
        *,
        expect_response: bool = True,
        delay_s: float = 0.04,
    ) -> str:
        del delay_s
        self.commands.append((command, expect_response))
        if command == "*IDN?":
            return "HTI,T660-2,00431,28E660-1-1.7"
        return "OK"


class T660PersistentStateTests(unittest.TestCase):
    def test_apply_recipe_uses_documented_persistent_state_commands(self) -> None:
        service = _RecordingT660Service()
        service.apply_recipe(
            {
                "stop_first": True,
                "frames_engine": "OFF",
                "predivider": 0,
                "gate_mode": 0,
                "burst_enabled": False,
                "external_trigger": {
                    "polarity": "negative",
                    "termination": "HIZ",
                    "threshold_v": 1.25,
                },
                "clock": {"frequency": "10Hz", "shots": 0},
                "trigger_source": "REM",
                "channels": {
                    "A": {
                        "timing_mode": "delay_width",
                        "delay": "5ns",
                        "width": "10ns",
                        "polarity": "negative",
                        "termination": "LOWZ",
                        "enabled": False,
                    },
                    "B": {
                        "timing_mode": "rise_fall",
                        "enabled": False,
                    },
                },
                "force_eod": True,
                "start": True,
            }
        )
        self.assertEqual(
            [command for command, _ in service.commands],
            [
                "STOP",
                "TFRame:STOp",
                "TRIGger:EXTernal:PREDiv 0",
                "GATE:MODe 0",
                "BURst:MODe OFF",
                "TRIGger:INPut:POLarity NEGative",
                "TRIGger:INPut:TERMination HIZ",
                "TRIGger:INPut:VOLTage 1.25",
                "TRIG:FREQ:SYN 10Hz",
                "TRIG:SHOTS 0",
                "TRIG:SOUR REM",
                "CHAN:DelayWidth A",
                "TIME:DEL1 5ns",
                "TIME:DEL2 10ns",
                "CHAN:NEG A",
                "CHAN:LOwZ A",
                "CHAN:OFF A",
                "CHAN:RiseFall B",
                "CHAN:OFF B",
                "FEOD",
                "START",
            ],
        )

    def test_recipe_validation_rejects_ambiguous_or_unsafe_types(self) -> None:
        base = {
            "stop_first": True,
            "predivider": 1,
            "gate_mode": 0,
            "burst_enabled": False,
            "trigger_source": "OFF",
            "channels": {"A": {"enabled": False}},
        }
        invalid_recipes = []
        for path, value in (
            (("burst_enabled",), "false"),
            (("predivider",), 1.5),
            (("gate_mode",), 1),
            (("channels", "A", "enabled"), "false"),
        ):
            recipe = deepcopy(base)
            target = recipe
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            invalid_recipes.append(recipe)
        invalid_recipes.extend(
            [
                {**base, "external_trigger": {"threshold_v": float("nan")}},
                {**base, "channels": {"A": {"delay": "1ns"}}},
                {
                    **base,
                    "channels": {
                        "A": {
                            "timing_mode": "rise_fall",
                            "delay": "1ns",
                            "width": "2ns",
                        }
                    },
                },
            ]
        )
        for recipe in invalid_recipes:
            with self.subTest(recipe=recipe):
                with self.assertRaises(T660ConfigurationError):
                    T660Service.validate_recipe_section("t660_test", recipe)

    def test_readback_uses_p500_identity_and_gates_frames_query_by_role(self) -> None:
        basic = _RecordingT660Service(role="pump_timing")
        basic_readback = basic.read_active_settings()
        basic_commands = [command for command, _ in basic.commands]
        self.assertNotIn("IDentify", basic_commands)
        self.assertNotIn("TFRame:STATus?", basic_commands)
        self.assertEqual(
            basic_readback["queries"]["firmware"]["response"],
            "28E660-1-1.7",
        )

        frames = _RecordingT660Service(role="master_timing_trains_frames")
        frames.read_active_settings()
        self.assertIn(
            "TFRame:STATus?",
            [command for command, _ in frames.commands],
        )

    def test_readback_normalizes_documented_long_and_hardware_short_forms(self) -> None:
        resolved = {
            "t660_2": {
                "predivider": 1,
                "gate_mode": 0,
                "burst_enabled": False,
                "frames_engine": "OFF",
                "trigger_source": "REM",
                "external_trigger": {
                    "polarity": "positive",
                    "termination": "HIZ",
                    "threshold_v": 2.0,
                },
                "clock": {"frequency": "10Hz"},
                "channels": {
                    "A": {
                        "enabled": False,
                        "timing_mode": "delay_width",
                        "delay": "5ns",
                        "width": "10ns",
                        "polarity": "positive",
                        "termination": "LOWZ",
                    },
                    "B": {
                        "enabled": False,
                        "timing_mode": "rise_fall",
                    },
                },
            }
        }
        readbacks = {
            "t660_2": {
                "queries": {
                    "predivider": {"ok": True, "response": "1"},
                    "gate_mode": {"ok": True, "response": "0"},
                    "burst": {"ok": True, "response": "OFF"},
                    "frames_engine": {"ok": True, "response": "OFF"},
                    "trigger_source": {"ok": True, "response": "REM"},
                    "trigger_input_polarity": {
                        "ok": True,
                        "response": "POSitive",
                    },
                    "trigger_input_termination": {
                        "ok": True,
                        "response": "NONE",
                    },
                    "trigger_input_threshold_v": {
                        "ok": True,
                        "response": "+2.000",
                    },
                    "synth_frequency": {
                        "ok": True,
                        "response": "+000000010.000000",
                    },
                },
                "channels": {
                    "A": {
                        "enabled": {"ok": True, "response": "OFF"},
                        "timing_mode": {
                            "ok": True,
                            "response": "DelayWidth",
                        },
                        "termination": {"ok": True, "response": "NONE"},
                        "polarity": {"ok": True, "response": "POSitive"},
                        "delay_edge": {
                            "ok": True,
                            "response": "+000.000000005000",
                        },
                        "width_edge": {
                            "ok": True,
                            "response": "+000.000000010000",
                        },
                    },
                    "B": {
                        "enabled": {"ok": True, "response": "OFF"},
                        "timing_mode": {"ok": True, "response": "RF"},
                    },
                },
            }
        }
        self.assertEqual(
            TimingRecipeManager._compare_readback(resolved, readbacks),
            [],
        )
        mutations = (
            (("queries", "trigger_source", "response"), "EXT", "trigger_source"),
            (("queries", "predivider", "response"), "2", "predivider"),
            (("queries", "gate_mode", "response"), "1", "gate_mode"),
            (("queries", "burst", "response"), "ON", "burst_enabled"),
            (("queries", "frames_engine", "response"), "RUNNING", "frames_engine"),
            (
                ("queries", "trigger_input_polarity", "response"),
                "NEGative",
                "trigger_input_polarity",
            ),
            (
                ("queries", "trigger_input_termination", "response"),
                "50OHM",
                "trigger_input_termination",
            ),
            (
                ("queries", "trigger_input_threshold_v", "response"),
                "+2.100",
                "trigger_input_threshold_v",
            ),
            (("queries", "synth_frequency", "response"), "11", "synth_frequency"),
            (("channels", "A", "enabled", "response"), "ON", "enabled"),
            (
                ("channels", "A", "timing_mode", "response"),
                "RiseFall",
                "timing_mode",
            ),
            (("channels", "A", "termination", "response"), "50OHM", "termination"),
            (("channels", "A", "polarity", "response"), "NEGative", "polarity"),
            (
                ("channels", "A", "delay_edge", "response"),
                "+000.000000006000",
                "delay",
            ),
            (
                ("channels", "A", "width_edge", "response"),
                "+000.000000011000",
                "width",
            ),
        )
        for path, value, expected_field in mutations:
            changed = deepcopy(readbacks)
            target = changed["t660_2"]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            mismatches = TimingRecipeManager._compare_readback(resolved, changed)
            with self.subTest(path=path, value=value):
                self.assertTrue(
                    any(item.get("field") == expected_field for item in mismatches),
                    mismatches,
                )

    def test_safe_idle_fully_specifies_persistent_and_channel_state(self) -> None:
        recipe_path = REPO_ROOT / "recipes" / "safe_idle.yaml"
        recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
        validation = TimingRecipeManager().validate_recipe(recipe)
        resolved = validation["resolved_settings"]
        for unit, settings in resolved.items():
            with self.subTest(unit=unit):
                self.assertEqual(settings["trigger_source"], "OFF")
                self.assertEqual(settings["predivider"], 1)
                self.assertEqual(settings["gate_mode"], 0)
                self.assertIs(settings["burst_enabled"], False)
                self.assertEqual(
                    settings["external_trigger"],
                    {
                        "polarity": "positive",
                        "termination": "50OHM",
                        "threshold_v": 2.0,
                    },
                )
                for channel in "ABCD":
                    channel_settings = settings["channels"][channel]
                    self.assertIs(channel_settings["enabled"], False)
                    self.assertEqual(channel_settings["timing_mode"], "delay_width")
                    self.assertEqual(channel_settings["delay"], "0ns")
                    if unit == "t660_1" and channel == "C":
                        self.assertEqual(channel_settings["width"], "10ms")
                        self.assertEqual(channel_settings["polarity"], "negative")
                    else:
                        self.assertEqual(channel_settings["width"], "150ns")
                        self.assertEqual(channel_settings["polarity"], "positive")
                    self.assertEqual(channel_settings["termination"], "50OHM")
        self.assertEqual(resolved["t660_2"]["frames_engine"], "OFF")
        self.assertNotIn("frames_engine", resolved["t660_1"])

    def test_manager_rejects_string_booleans_before_hardware(self) -> None:
        manager = TimingRecipeManager()
        with self.assertRaises(TimingRecipeError):
            manager.validate_recipe(
                {
                    "approved_laser_safety_condition": "false",
                    "t660": {"t660_2": {"channels": {"A": {"enabled": False}}}},
                }
            )
        with self.assertRaises(TimingRecipeError):
            manager.validate_recipe(
                {
                    "approved_laser_safety_condition": False,
                    "t660": {
                        "t660_2": {
                            "burst_enabled": "false",
                            "channels": {"A": {"enabled": False}},
                        }
                    },
                }
            )


if __name__ == "__main__":
    unittest.main()
