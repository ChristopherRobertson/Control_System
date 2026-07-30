from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml

from control_app.config_loader import REPO_ROOT, load_config_inventory
from control_app.workflows.timing_trace_analysis import DEFAULT_SEPARATIONS_NS
from control_app.workflows.timing_calibration_procedure import (
    MEASUREMENT_STEPS,
    MAX_SAMPLES_PER_TRACE,
    SafeIdleVerificationError,
    TimingCalibrationProcedure,
    _consolidate_best_effort_results,
    _plan_capture_settings,
    _require_fresh_acquisition_directory,
    _steps_for_execution_scope,
    _load_and_validate_optical_recipe,
    _apply_verified_safe_idle,
    analyze_optical_trace,
    consolidate_results,
    create_unique_run_directory,
    derive_measurement_system_corrections,
    fit_delay_sweep,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


class TimingCalibrationProcedureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = load_config_inventory(write_files=False)
        (REPO_ROOT / "calibration").mkdir(parents=True, exist_ok=True)

    def test_complete_plan_has_exact_sequence_time_origins_and_cables(self) -> None:
        workflow = TimingCalibrationProcedure(operator="Test", inventory=self.inventory)
        plan = workflow.build_plan(shot_count=1, reduced_set_rationale="unit-test speed")
        self.assertEqual(
            [item["step"] for item in plan["operator_sequence"]],
            ["0a", "0b", "0c", "1", "2", "3", "4", "5", "6", "7", "8"],
        )
        self.assertIn("first programmed T660-2", plan["time_origins"]["t_master"])
        self.assertIn("sample", plan["time_origins"]["t_chem"])
        self.assertEqual(plan["recipes"]["optical"]["effective_trigger_source"], "REM")
        self.assertEqual(plan["capture_policy"]["maximum_samples_per_trace"], MAX_SAMPLES_PER_TRACE)
        for item in plan["operator_sequence"]:
            self.assertTrue(item["pico_ch_a"])
            self.assertTrue(item["pico_ch_b"])
            self.assertTrue(item["remains_connected"])
            self.assertTrue(item["disconnect"])
            expected_rate = 10 if item["step"] in {"4", "5", "6", "7", "8"} else 100
            self.assertEqual(item["trigger_rate_hz"], expected_rate)
        optical = next(item for item in plan["operator_sequence"] if item["step"] == "7")
        self.assertTrue(optical["requires_laser_safety_confirmation"])
        self.assertIn("output 1", optical["splitter_mapping"])
        self.assertIn("output 2", optical["splitter_mapping"])

    def test_ms01_execution_scope_stops_after_normal_and_swapped_captures(self) -> None:
        workflow = TimingCalibrationProcedure(operator="Test", inventory=self.inventory)
        plan = workflow.build_plan(shot_count=1, reduced_set_rationale="unit-test speed")

        scoped = _steps_for_execution_scope(plan, "MS-01")

        self.assertEqual([item["step"] for item in scoped], ["0a", "0b"])
        self.assertEqual(
            [item["measurement_id"] for item in scoped], ["MS-00A", "MS-00B"]
        )
        self.assertNotIn("0c", {item["step"] for item in scoped})
        self.assertNotIn("1", {item["step"] for item in scoped})

    def test_freshness_check_allows_current_attempt_command_log(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "calibration") as temp:
            run_dir = Path(temp)
            for name in (
                "timing_calibration_plan.json",
                "timing_calibration_plan.md",
                "workflow_status.json",
                "command_log.txt",
            ):
                (run_dir / name).write_text("", encoding="utf-8")

            _require_fresh_acquisition_directory(run_dir)

    def test_missing_step7_metadata_is_cataloged_not_a_prehardware_blocker(self) -> None:
        workflow = TimingCalibrationProcedure(operator="Test", inventory=self.inventory)
        plan = workflow.build_plan()

        self.assertEqual(plan["prehardware_blockers"], [])
        required = {item["field"] for item in plan["user_input_required"]}
        self.assertIn("photodetector_response_delay_ns", required)
        self.assertNotIn("step7_load_match_method", required)
        self.assertNotIn("step7_load_match_standard_uncertainty_ns", required)
        self.assertTrue(
            all(item["value"] == "USER_INPUT_REQUIRED" for item in plan["user_input_required"])
        )

    def test_best_effort_report_preserves_missing_inputs_without_zero_placeholders(self) -> None:
        rows = [
            row
            for row in _synthetic_measurement_rows()
            if row["measurement_id"] in {"MS-00A", "MS-00B"}
        ]
        with tempfile.TemporaryDirectory() as temp:
            outputs = _consolidate_best_effort_results(
                rows,
                output_dir=temp,
                user_input_required=["photodetector_response_delay_ns"],
                skipped_steps=[
                    {
                        "step": "7",
                        "measurement_id": "TC-07",
                        "status": "USER_INPUT_REQUIRED",
                        "fields": ["photodetector_response_delay_ns"],
                    }
                ],
            )
            report = json.loads(
                Path(outputs["best_effort_final_report_json"]).read_text(encoding="utf-8")
            )
            self.assertEqual(report["status"], "BEST_EFFORT_WITH_USER_INPUT_REQUIRED")
            self.assertEqual(
                report["user_input_required"][0]["value"], "USER_INPUT_REQUIRED"
            )
            self.assertNotIn("photodetector_response_delay_ns", report["measurement_system_corrections"])

    def test_step_zero_preserves_fixed_bulkheads_and_restores_clock_splitter(self) -> None:
        step_0a = next(step for step in MEASUREMENT_STEPS if step.step == "0a")
        step_0b = next(step for step in MEASUREMENT_STEPS if step.step == "0b")
        step_0c = next(step for step in MEASUREMENT_STEPS if step.step == "0c")
        step_1 = next(step for step in MEASUREMENT_STEPS if step.step == "1")

        step_zero_text = " ".join(
            (
                step_0a.pico_ch_a,
                step_0a.pico_ch_b,
                *step_0a.disconnect,
                step_0b.pico_ch_a,
                step_0b.pico_ch_b,
                *step_0b.disconnect,
                step_0c.pico_ch_a,
                step_0c.pico_ch_b,
                *step_0c.disconnect,
            )
        )
        self.assertIn("fixed 12-inch", step_zero_text)
        self.assertIn("directly to that BNC bulkhead", step_zero_text)
        self.assertIn("park it for restoration", step_zero_text)
        self.assertNotIn("installed EXT REF downstream BNC cable -> CLOCK-SPLITTER-01", step_zero_text)
        self.assertNotIn("dedicated T660-2 CHA test lead", step_zero_text)
        self.assertNotIn("at the T660-2 CHA source", step_zero_text)

        step_1_transition = " ".join(step_1.disconnect)
        self.assertIn("Restore CLOCK-SPLITTER-01 to T660-2 CLOCK", step_1_transition)
        self.assertIn("T660-1 CLOCK and HF2LI CLOCK", step_1_transition)
        self.assertIn("before any clock-dependent recipe", step_1_transition)

    def test_step_zero_uses_integral_splitter_branches_directly(self) -> None:
        step_0a = next(step for step in MEASUREMENT_STEPS if step.step == "0a")
        step_0b = next(step for step in MEASUREMENT_STEPS if step.step == "0b")

        self.assertIn("S1 -> directly to CHA", step_0a.splitter_mapping)
        self.assertIn("S2 -> directly to CHB", step_0a.splitter_mapping)
        self.assertIn("S2 -> directly to CHA", step_0b.splitter_mapping)
        self.assertIn("S1 -> directly to CHB", step_0b.splitter_mapping)
        self.assertIn("third integral branch -> open and unconnected", step_0a.splitter_mapping)
        self.assertIn("third integral branch -> open and unconnected", step_0b.splitter_mapping)
        self.assertNotIn("measurement assembly", step_0a.pico_ch_a)
        self.assertNotIn("measurement assembly", step_0a.pico_ch_b)

    def test_t6601_channel_d_is_unmapped_and_absent_from_calibration_recipes(self) -> None:
        self.assertIsNone(
            self.inventory.devices["t660_1"]["channel_map"]["D"]
        )
        self.assertNotIn(
            "mircat_db9_pin_5_laser_output_on_off",
            self.inventory.signal_map,
        )
        for recipe_name in ("timing_calibration.yaml", "pump_probe_single_point.yaml"):
            recipe = yaml.safe_load(
                (REPO_ROOT / "recipes" / recipe_name).read_text(encoding="utf-8")
            )
            signals = recipe["t660"]["t660_1"]["signals"]
            self.assertNotIn("mircat_db9_pin_5_laser_output_on_off", signals)
        self.assertNotIn("9", {step.step for step in MEASUREMENT_STEPS})

    def test_unique_run_directory_never_reuses_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            first = create_unique_run_directory(run_parent=parent)
            second = create_unique_run_directory(run_parent=parent)
            self.assertNotEqual(first, second)
            marker = first / "old_data.txt"
            marker.write_text("preserve", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                create_unique_run_directory(requested_path=first)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    @unittest.skip("obsolete administrative plan-difference gate removed")
    def test_hardware_parameters_cannot_differ_from_frozen_plan(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "calibration") as temp:
            run_dir = Path(temp) / "run"
            run_dir.mkdir()
            workflow = TimingCalibrationProcedure(operator="Test", inventory=self.inventory)
            workflow.write_plan(
                run_dir,
                shot_count=1,
                reduced_set_rationale="unit test",
                photodetector_response_delay_ns=0.0,
                photodetector_response_uncertainty_ns=0.1,
                **_step7_provenance_kwargs(),
            )
            with self.assertRaisesRegex(Exception, "differ from the frozen reviewed plan"):
                workflow.run(
                    run_dir=run_dir,
                    shot_count=1,
                    reduced_set_rationale="unit test",
                    photodetector_response_delay_ns=1.0,
                    photodetector_response_uncertainty_ns=0.1,
                    **_step7_provenance_kwargs(),
                    prompt=lambda message: (_ for _ in ()).throw(AssertionError(message)),
                )
            markdown_path = run_dir / "timing_calibration_plan.md"
            markdown_path.write_text(
                markdown_path.read_text(encoding="utf-8") + "\nmodified\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(Exception, "Markdown cable plan"):
                workflow.run(
                    run_dir=run_dir,
                    shot_count=1,
                    reduced_set_rationale="unit test",
                    photodetector_response_delay_ns=0.0,
                    photodetector_response_uncertainty_ns=0.1,
                    **_step7_provenance_kwargs(),
                    prompt=lambda message: (_ for _ in ()).throw(AssertionError(message)),
                )

    @unittest.skip("obsolete prior-plan execution gate removed")
    def test_execution_requires_prior_json_and_markdown_plan(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "calibration") as temp:
            workflow = TimingCalibrationProcedure(operator="Test", inventory=self.inventory)
            with self.assertRaisesRegex(Exception, "prior plan-only invocation"):
                workflow.run(
                    run_dir=temp,
                    shot_count=1,
                    reduced_set_rationale="unit test",
                    photodetector_response_delay_ns=0.0,
                    photodetector_response_uncertainty_ns=0.1,
                    **_step7_provenance_kwargs(),
                    prompt=lambda message: (_ for _ in ()).throw(AssertionError(message)),
                )

    @unittest.skip("obsolete plan-review confirmation gate removed")
    def test_nonsemantic_recipe_comment_change_does_not_block_review(self) -> None:
        with tempfile.TemporaryDirectory() as recipe_temp, tempfile.TemporaryDirectory(
            dir=REPO_ROOT / "calibration"
        ) as run_temp:
            pico_recipe = Path(recipe_temp) / "pico.yaml"
            pico_recipe.write_bytes(
                (REPO_ROOT / "recipes" / "picoscope_settings_test.yaml").read_bytes()
            )
            run_dir = Path(run_temp) / "run"
            run_dir.mkdir()
            workflow = TimingCalibrationProcedure(operator="Test", inventory=self.inventory)
            workflow.write_plan(
                run_dir,
                picoscope_recipe_path=pico_recipe,
                shot_count=1,
                reduced_set_rationale="unit test",
                photodetector_response_delay_ns=0.0,
                photodetector_response_uncertainty_ns=0.1,
                **_step7_provenance_kwargs(),
            )
            pico_recipe.write_text(
                pico_recipe.read_text(encoding="utf-8") + "\n# changed after review\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "REVIEWED TIMING PLAN"):
                workflow.run(
                    run_dir=run_dir,
                    picoscope_recipe_path=pico_recipe,
                    shot_count=1,
                    reduced_set_rationale="unit test",
                    photodetector_response_delay_ns=0.0,
                    photodetector_response_uncertainty_ns=0.1,
                    **_step7_provenance_kwargs(),
                    prompt=lambda message: (_ for _ in ()).throw(AssertionError(message)),
                )

    def test_safe_idle_wraps_interrupt_as_unknown_output_state(self) -> None:
        class InterruptingManager:
            def apply_recipe(self, recipe, *, output_path):
                raise KeyboardInterrupt("operator interrupt during STOP/readback")

        with self.assertRaises(SafeIdleVerificationError) as caught:
            _apply_verified_safe_idle(
                InterruptingManager(),
                Path("unused.json"),
                recipe={"name": "safe"},
            )
        self.assertIsInstance(caught.exception.__cause__, KeyboardInterrupt)

    @unittest.skip("obsolete prehardware blocking-status gate removed")
    def test_cli_consumes_reviewed_plan_into_explicit_blocked_status(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "calibration") as temp:
            run_dir = Path(temp) / "cli_plan"
            command = [
                sys.executable,
                str(
                    REPO_ROOT
                    / "tests"
                    / "hardware_checks"
                    / "check_complete_timing_calibration.py"
                ),
                "--operator",
                "CLI Test",
            ]
            planned = subprocess.run(
                [*command, "--run-dir", str(run_dir)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
            status_path = run_dir / "workflow_status.json"
            plan_status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(plan_status["status"], "PLAN_ONLY_READY_FOR_REVIEW")
            self.assertIs(plan_status["hardware_opened"], False)

            blocked = subprocess.run(
                [*command, "--execute", "--reviewed-plan-dir", str(run_dir)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
            blocked_status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(
                blocked_status["status"], "EXECUTION_BLOCKED_PREHARDWARE"
            )
            self.assertIs(blocked_status["hardware_access_attempted"], False)
            self.assertIs(blocked_status["hardware_opened"], False)
            self.assertFalse((run_dir / "raw_pico_traces").exists())

    def test_generated_recipes_are_sparse_and_explicit(self) -> None:
        workflow = TimingCalibrationProcedure(operator="Test", inventory=self.inventory)
        for step in MEASUREMENT_STEPS:
            if step.target_signal == "mircat_db9_pin_4_process_trigger":
                self.assertEqual(step.target_edge, "falling")
            if step.optical:
                continue
            recipe = workflow.build_step_recipe(step, programmed_delay_ns=1_000_000)
            validation = TimingRecipeManager(self.inventory).validate_recipe(recipe)
            self.assertEqual(validation["status"], "VALIDATED_PREHARDWARE")
            units = recipe["t660"]
            for unit in units.values():
                self.assertEqual(set(unit["channels"]), {"A", "B", "C", "D"})
            if step.step in {"4", "5", "6", "8"}:
                self.assertEqual(list(units), ["t660_1", "t660_2"])
                self.assertEqual(units["t660_2"]["clock"]["frequency"], "10Hz")
                for settings in units["t660_1"]["channels"].values():
                    if settings.get("signal") in {"ndyag_fire", "ndyag_q_switch"} and settings.get("enabled"):
                        self.assertEqual(settings["polarity"], "negative")
                        self.assertEqual(settings["width"], "10us")
                    if settings.get("signal") == "mircat_db9_pin_4_process_trigger":
                        self.assertEqual(settings["polarity"], "negative")
                        self.assertEqual(settings["width"], "10ms")
            else:
                self.assertEqual(units["t660_2"]["clock"]["frequency"], "100Hz")
        optical = next(step for step in MEASUREMENT_STEPS if step.optical)
        with self.assertRaisesRegex(Exception, "approved optical recipe"):
            workflow.build_step_recipe(optical, programmed_delay_ns=0)

    def test_capture_planner_advances_timebase_and_covers_one_millisecond(self) -> None:
        class FakePico:
            capture_settings: dict

            def validate_sample_timing(self):
                timebase = int(self.capture_settings["timebase"])
                if timebase == 1:
                    return {"sample_interval_ns": 2.0, "max_samples": 200_000, "timebase": 1}
                return {
                    "sample_interval_ns": float(2 ** timebase),
                    "max_samples": 400_000,
                    "timebase": timebase,
                }

        pico = FakePico()
        base = {
            "timebase": 1,
            "total_samples": 100_000,
            "pre_trigger_samples": 1_000,
            "external_trigger": {},
        }
        settings, validation = _plan_capture_settings(
            pico,
            base,
            programmed_delay_ns=1_000_000,
            base_sample_interval_ns=2.0,
            trigger_edge="rising",
        )
        self.assertGreater(settings["timebase"], 1)
        post_span = (settings["total_samples"] - settings["pre_trigger_samples"]) * validation["sample_interval_ns"]
        self.assertGreaterEqual(post_span, 1_010_000)
        self.assertLessEqual(settings["total_samples"], validation["max_samples"])
        self.assertLessEqual(settings["total_samples"], MAX_SAMPLES_PER_TRACE)

    def test_splitter_math_and_ppm_fit(self) -> None:
        rows = []
        for value in (7.0, 7.2, 6.8):
            rows.append({"measurement_id": "MS-00A", "measured_separation_ns": value})
        for value in (-1.0, -0.8, -1.2):
            rows.append({"measurement_id": "MS-00B", "measured_separation_ns": value})
        for value in (8.0, 8.2, 7.8):
            rows.append({"measurement_id": "MS-00C", "measured_separation_ns": value})
        corrections = derive_measurement_system_corrections(rows)
        self.assertAlmostEqual(corrections["scope_channel_and_fixed_lead_b_minus_a_ns"], 3.0)
        self.assertAlmostEqual(corrections["splitter_branch_2_minus_1_ns"], 4.0)
        self.assertAlmostEqual(
            corrections["installed_step7_branch_2_monitor_minus_branch_1_qswitch_ns"],
            5.0,
        )

        points = []
        for programmed in DEFAULT_SEPARATIONS_NS:
            points.append(
                {
                    "programmed_delay_ns": programmed,
                    "mean_corrected_measured_ns": 7.5 + programmed * (1.0 + 8e-6),
                }
            )
        fit = fit_delay_sweep(points)
        self.assertAlmostEqual(fit["fixed_offset_intercept_ns"], 7.5, places=6)
        self.assertAlmostEqual(fit["slope_ppm"], 8.0, places=6)

    def test_t660_readback_checks_state_frequency_delay_width_and_termination(self) -> None:
        resolved = {
            "t660_2": {
                "clock": {"frequency": "10Hz"},
                "channels": {
                    "A": {
                        "enabled": True,
                        "delay": "100ns",
                        "width": "150ns",
                        "termination": "50OHM",
                    },
                    "B": {"enabled": False},
                },
            }
        }
        readback = {
            "t660_2": {
                "queries": {"synth_frequency": {"ok": True, "response": "+000000010.000000"}},
                "channels": {
                    "A": {
                        "enabled": {"ok": True, "response": "ON"},
                        "delay_edge": {"ok": True, "response": "+000.000000100000"},
                        "width_edge": {"ok": True, "response": "+000.000000150000"},
                        "termination": {"ok": True, "response": "50OHM"},
                        "timing_mode": {"ok": True, "response": "DW"},
                    },
                    "B": {"enabled": {"ok": True, "response": "OFF"}},
                },
            }
        }
        self.assertEqual(TimingRecipeManager._compare_readback(resolved, readback), [])
        readback["t660_2"]["channels"]["B"]["enabled"]["response"] = "ON"
        mismatches = TimingRecipeManager._compare_readback(resolved, readback)
        self.assertEqual(mismatches[0]["field"], "enabled")
        self.assertEqual(mismatches[0]["expected"], "OFF")

    def test_optical_trace_checks_pulse_and_saturation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            good = Path(temp) / "good.csv"
            _write_trace(good, reference_falling=True, target_index=30, target_level=10_000)
            result = analyze_optical_trace(
                good,
                sample_interval_ns=2.0,
                pre_trigger_samples=10,
                reference_threshold_adc=5_000,
                reference_edge="falling",
                target_threshold_adc=5_000,
                target_edge="rising",
                maximum_latency_ns=100.0,
                blocked_control={
                    "detector_signal_excursion_adc": 0.0,
                    "detector_baseline_noise_adc": 0.0,
                },
            )
            self.assertAlmostEqual(result["measured_separation_ns"], 40.0)
            self.assertTrue(result["blocked_control_comparison_applied"])

            late = Path(temp) / "late.csv"
            _write_trace(late, reference_falling=True, target_index=70, target_level=10_000)
            with self.assertRaisesRegex(Exception, "between 5 and 50 ns"):
                analyze_optical_trace(
                    late,
                    sample_interval_ns=2.0,
                    pre_trigger_samples=10,
                    reference_threshold_adc=5_000,
                    reference_edge="falling",
                    target_threshold_adc=5_000,
                    target_edge="rising",
                    maximum_latency_ns=50.0,
                )

            with self.assertRaisesRegex(Exception, "control-like"):
                analyze_optical_trace(
                    good,
                    sample_interval_ns=2.0,
                    pre_trigger_samples=10,
                    reference_threshold_adc=5_000,
                    reference_edge="falling",
                    target_threshold_adc=5_000,
                    target_edge="rising",
                    maximum_latency_ns=100.0,
                    blocked_control={
                        "detector_signal_excursion_adc": 10_000.0,
                        "detector_baseline_noise_adc": 0.0,
                    },
                )

            saturated = Path(temp) / "saturated.csv"
            _write_trace(saturated, reference_falling=True, target_index=30, target_level=31_000)
            with self.assertRaisesRegex(Exception, "saturated"):
                analyze_optical_trace(
                    saturated,
                    sample_interval_ns=2.0,
                    pre_trigger_samples=10,
                    reference_threshold_adc=5_000,
                    reference_edge="falling",
                    target_threshold_adc=5_000,
                    target_edge="rising",
                )

    def test_optical_recipe_is_forced_to_bounded_external_remote_topology(self) -> None:
        source = yaml.safe_load(
            (REPO_ROOT / "recipes" / "ndyag_alignment_10hz.yaml").read_text(
                encoding="utf-8"
            )
        )
        source["t660"]["t660_1"]["trigger_source"] = "SYN"
        source["t660"]["t660_1"]["signals"][
            "mircat_db9_pin_4_process_trigger"
        ] = {
            "delay": "0ns",
            "width": "10us",
            "polarity": "positive",
            "termination": "50OHM",
            "enabled": True,
        }
        source["t660"]["t660_2"]["channels"]["A"] = {
            "delay": "0ns",
            "width": "10us",
            "polarity": "positive",
            "termination": "50OHM",
            "enabled": True,
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "malicious_optical.yaml"
            path.write_text(yaml.safe_dump(source), encoding="utf-8")
            effective = _load_and_validate_optical_recipe(path, expected_rate_hz=10)
        self.assertEqual(effective["t660"]["t660_1"]["trigger_source"], "EXT")
        self.assertEqual(effective["t660"]["t660_2"]["trigger_source"], "REM")
        self.assertFalse(
            effective["t660"]["t660_1"]["signals"][
                "mircat_db9_pin_4_process_trigger"
            ]["enabled"]
        )
        self.assertFalse(effective["t660"]["t660_2"]["channels"]["A"]["enabled"])
        self.assertEqual(
            effective["timing_calibration_selected_program_ns"][
                "q_switch_delay_ns"
            ],
            179830.0,
        )

    def test_consolidated_table_has_all_required_categories_and_derivations(self) -> None:
        rows = _synthetic_measurement_rows()
        with tempfile.TemporaryDirectory() as temp:
            outputs = consolidate_results(
                rows,
                steps=list(MEASUREMENT_STEPS),
                output_dir=temp,
                optical_recipe_path="recipes/ndyag_alignment_10hz.yaml",
            )
            with Path(outputs["consolidated_csv"]).open("r", newline="", encoding="utf-8") as handle:
                consolidated = list(csv.DictReader(handle))
            self.assertEqual(len(consolidated), 15)
            ids = {row["measurement_id"] for row in consolidated}
            self.assertTrue({f"TC-{index:02d}" for index in range(1, 9)}.issubset(ids))
            self.assertTrue({f"DER-{index:02d}" for index in range(1, 5)}.issubset(ids))
            self.assertTrue({f"COR-{index:02d}" for index in range(1, 4)}.issubset(ids))
            required_columns = {
                "category",
                "measurement_id",
                "reference_event",
                "target_event",
                "physical_connection_summary",
                "uses_final_wiring",
                "splitter_used",
                "splitter_scope_correction_applied",
                "programmed_delay_range",
                "fixed_offset_intercept_ns",
                "slope_ppm",
                "jitter_std_ns",
                "combined_standard_uncertainty_ns",
                "picoscope_fixed_timebase_standard_uncertainty_ns",
                "uncertainty_terms_and_provenance",
                "use_in_timing_recipe",
                "recipe_correction_ns",
                "recipe_correction_standard_uncertainty_ns",
                "recipe_formula",
                "rsi_thesis_reporting_label",
                "notes",
            }
            self.assertTrue(required_columns.issubset(consolidated[0]))
            by_id = {row["measurement_id"]: row for row in consolidated}
            self.assertTrue(math.isnan(float(by_id["TC-01"]["threshold_sensitivity_standard_uncertainty_ns"])))
            self.assertIn(
                "threshold sensitivity not evaluated and excluded",
                by_id["TC-01"]["uncertainty_terms_and_provenance"],
            )
            self.assertFalse(math.isnan(float(by_id["TC-07"]["threshold_sensitivity_standard_uncertainty_ns"])))
            self.assertAlmostEqual(
                float(by_id["DER-02"]["picoscope_fixed_timebase_standard_uncertainty_ns"]),
                abs(float(by_id["DER-02"]["fixed_offset_intercept_ns"])) * 2e-6,
                places=12,
            )
            yaml_text = Path(outputs["derived_recipe_corrections_yaml"]).read_text(encoding="utf-8")
            self.assertIn("validation_closure", yaml_text)
            self.assertIn("hf2li_extref_arrival_to_t_chem", yaml_text)
            correction_document = yaml.safe_load(yaml_text)
            derived = correction_document["derived_recipe_corrections"]
            measurement_corrections = correction_document[
                "measurement_system_corrections"
            ]
            self.assertAlmostEqual(
                measurement_corrections[
                    "scope_installed_step7_geometry_covariance_ns2"
                ],
                -measurement_corrections["scope_correction_standard_uncertainty_ns"] ** 2,
                places=12,
            )
            self.assertEqual(
                derived["selected_optical_recipe_programmed_delays_ns"],
                {"fire": 0.0, "q_switch": 179830.0, "fire_to_q_switch": 179830.0},
            )
            self.assertAlmostEqual(
                derived[
                    "hf2li_extref_arrival_to_t_chem_selected_recipe_ns_TC04_plus_TC05_plus_TC07"
                ],
                179985.15,
                places=6,
            )
            self.assertAlmostEqual(
                derived[
                    "hf2li_extref_arrival_to_t_chem_selected_recipe_ns_TC06_plus_TC07_direct_validation"
                ],
                179955.1,
                places=6,
            )
            self.assertAlmostEqual(
                derived[
                    "hf2li_extref_arrival_to_t_chem_selected_recipe_dual_derivation_closure_ns_direct_minus_component"
                ],
                -30.05,
                places=6,
            )
            self.assertAlmostEqual(
                derived[
                    "hf2li_extref_arrival_to_t_chem_selected_recipe_dual_derivation_closure_standard_uncertainty_ns"
                ],
                derived[
                    "hf2li_extref_arrival_to_qswitch_selected_recipe_validation_closure_standard_uncertainty_ns"
                ],
                places=12,
            )

    def test_fake_hardware_run_prompts_before_outputs_and_never_publishes(self) -> None:
        events: list[str] = []
        hardware_states: list[str] = []
        fail_final_safe_idle = {"enabled": False}
        fail_pico_cleanup = {"enabled": False}

        class FakeManager:
            def apply_recipe(self, recipe, *, output_path):
                name = Path(recipe).stem if isinstance(recipe, (str, Path)) else str(recipe.get("measurement_id") or recipe.get("name"))
                events.append(f"apply:{name}")
                path = Path(output_path)
                if fail_final_safe_idle["enabled"] and path.name == "999_safe_idle_final.json":
                    raise RuntimeError("simulated final safe idle failure")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"matches_recipe": True, "name": name}), encoding="utf-8")
                return {"matches_recipe": True}

        class FakePico:
            def __init__(self):
                self.capture_settings = {}

            def open_unit(self):
                events.append("pico:open")

            def apply_capture_settings(self):
                pass

            def validate_sample_timing(self):
                return {
                    "timebase": int(self.capture_settings.get("timebase", 1)),
                    "sample_interval_ns": 1000.0,
                    "max_samples": 1_000_000,
                }

            def capture_block(self, raw_path, *, after_arm=None):
                path = Path(raw_path)
                if after_arm is not None:
                    after_arm()
                delay = (
                    int(path.name.split("delay_")[1].split("ns_")[0])
                    if "delay_" in path.name
                    else 0
                )
                optical = "step_7_" in str(path)
                beam_blocked = "beam_blocked_control" in path.name
                reference_falling = any(
                    token in str(path)
                    for token in ("step_5_", "step_7_", "step_8_")
                )
                target_falling = any(
                    token in str(path)
                    for token in ("step_4_", "step_5_", "step_6_", "step_8_")
                )
                _write_fake_capture(
                    path,
                    delay_ns=delay,
                    reference_falling=reference_falling,
                    target_falling=target_falling,
                    optical=optical,
                    beam_blocked=beam_blocked,
                )
                return {"raw_data_file": str(path)}

            def stop(self):
                events.append("pico:stop")
                if fail_pico_cleanup["enabled"]:
                    raise RuntimeError("simulated PicoScope stop failure")

            def close_unit(self):
                events.append("pico:close")
                if fail_pico_cleanup["enabled"]:
                    raise RuntimeError("simulated PicoScope close failure")

        class FakeRemoteController:
            def __init__(self):
                self.count = 0

            def open(self):
                self.count = 0

            def reset_counters(self):
                self.count = 0

            def fire_once(self):
                self.count += 1

            def read_counts(self):
                return {"t660_1": self.count, "t660_2": self.count}

            def close(self):
                pass

        def prompt(message: str) -> str:
            if message.startswith("Type REVIEWED"):
                answer = "REVIEWED TIMING PLAN"
            elif message.startswith("Type READY"):
                answer = message.split("Type ", 1)[1].split(" when", 1)[0]
            elif message.startswith("Type OUTPUTS") or message.startswith("Type OUTPUT ROUTING"):
                answer = message.split("Type ", 1)[1].split(" to confirm", 1)[0]
            elif message.startswith("Type BEAM BLOCKED"):
                answer = "BEAM BLOCKED CONTROL READY STEP 7"
            elif message.startswith("Type BEAM UNBLOCKED"):
                answer = "BEAM UNBLOCKED PREVIEW READY STEP 7"
            elif message.startswith("Type OPTICAL PREVIEW"):
                answer = "OPTICAL PREVIEW ACCEPTED STEP 7"
            elif message.startswith("Type FINAL CABLING"):
                answer = "FINAL CABLING RESTORED SAFE"
            else:
                raise AssertionError(message)
            events.append(f"prompt:{answer}")
            return answer

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "calibration") as temp:
            run_dir = Path(temp) / "unique_run"
            run_dir.mkdir()
            workflow = TimingCalibrationProcedure(
                operator="Test",
                inventory=self.inventory,
                timing_manager_factory=lambda *args, **kwargs: FakeManager(),
                pico_factory=lambda *args, **kwargs: FakePico(),
                remote_shot_controller_factory=lambda *args, **kwargs: FakeRemoteController(),
            )
            workflow.write_plan(
                run_dir,
                shot_count=1,
                reduced_set_rationale="fake-device integration test",
                photodetector_response_delay_ns=0.0,
                photodetector_response_uncertainty_ns=0.2,
                **_step7_provenance_kwargs(),
            )
            summary = workflow.run(
                run_dir=run_dir,
                execution_scope="COMPLETE",
                shot_count=1,
                reduced_set_rationale="fake-device integration test",
                photodetector_response_delay_ns=0.0,
                photodetector_response_uncertainty_ns=0.2,
                **_step7_provenance_kwargs(),
                prompt=prompt,
                emit=lambda message: None,
                hardware_state_callback=hardware_states.append,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(hardware_states, ["OPEN_ATTEMPT", "OPENED"])
            self.assertIn("RUN_LOCAL_ONLY", summary["publication_status"])
            self.assertEqual(
                summary["optical_exposure_audit"]["remote_trigger_commands"],
                3,
            )
            self.assertEqual(
                summary["optical_exposure_audit"]["accepted_measurement_traces"],
                1,
            )
            self.assertEqual(
                [item["label"] for item in summary["optical_exposure_audit"]["segments"]],
                ["beam_blocked_control", "preview", "measurement"],
            )
            observed_intervals = summary["optical_exposure_audit"][
                "observed_inter_shot_intervals_s"
            ]
            self.assertEqual(len(observed_intervals), 2)
            self.assertGreaterEqual(min(observed_intervals), 0.099)
            self.assertFalse((Path(temp) / "calibration").exists())
            for step in MEASUREMENT_STEPS:
                prompt_index = events.index(f"prompt:READY {step.setup_id}")
                recipe_events = [
                    index
                    for index, event in enumerate(events)
                    if event == f"apply:{step.measurement_id}"
                ]
                if step.optical:
                    recipe_events = [
                        index
                        for index, event in enumerate(events)
                        if event == "apply:ndyag_alignment_10hz"
                    ]
                self.assertTrue(recipe_events)
                self.assertLess(prompt_index, recipe_events[0])
            optical_apply = events.index("apply:ndyag_alignment_10hz")
            self.assertGreater(optical_apply, 0)
            self.assertEqual(events[-2:], ["pico:stop", "pico:close"])

            fail_final_safe_idle["enabled"] = True
            fail_pico_cleanup["enabled"] = True
            failed_run_dir = Path(temp) / "final_safe_failure_run"
            failed_run_dir.mkdir()
            failed_workflow = TimingCalibrationProcedure(
                operator="Test",
                inventory=self.inventory,
                timing_manager_factory=lambda *args, **kwargs: FakeManager(),
                pico_factory=lambda *args, **kwargs: FakePico(),
                remote_shot_controller_factory=lambda *args, **kwargs: FakeRemoteController(),
            )
            failed_workflow.write_plan(
                failed_run_dir,
                shot_count=1,
                reduced_set_rationale="final-safe failure integration test",
                photodetector_response_delay_ns=0.0,
                photodetector_response_uncertainty_ns=0.2,
                **_step7_provenance_kwargs(),
            )
            with self.assertRaisesRegex(Exception, "SAFE-IDLE STOP/OFF"):
                failed_workflow.run(
                    run_dir=failed_run_dir,
                    execution_scope="COMPLETE",
                    shot_count=1,
                    reduced_set_rationale="final-safe failure integration test",
                    photodetector_response_delay_ns=0.0,
                    photodetector_response_uncertainty_ns=0.2,
                    **_step7_provenance_kwargs(),
                    prompt=prompt,
                    emit=lambda message: None,
                )
            self.assertFalse((failed_run_dir / "workflow_summary.json").exists())

def _step7_provenance_kwargs() -> dict[str, object]:
    return {
        "photodetector_response_source": "unit-test characterization record",
        "photodetector_identifier": "PD-TEST-001",
        "photodetector_cable_identifier": "PD-CABLE-TEST-001",
        "photodetector_characterization_date": "2026-01-01",
        "photodetector_path_description": "sample-equivalent unit-test path",
        "photodetector_maximum_latency_ns": 20_000.0,
        "sample_path_standard_uncertainty_ns": 0.1,
        "step7_load_match_method": "50-ohm matched dummy load with high-Z probe",
        "step7_load_match_standard_uncertainty_ns": 0.1,
        "measurement_assembly_record": "splitter S1; E_A A1; E_B B1; Q cable Q1; monitor M1",
    }


def _synthetic_measurement_rows() -> list[dict]:
    rows: list[dict] = []
    offsets = {f"TC-{index:02d}": float(index * 10) for index in range(1, 10)}
    for step in MEASUREMENT_STEPS:
        delays = DEFAULT_SEPARATIONS_NS if step.sweep_delays else (0,)
        for delay in delays:
            for shot in range(2):
                if step.measurement_id == "MS-00A":
                    measured = 7.0 + shot * 0.1
                elif step.measurement_id == "MS-00B":
                    measured = -1.0 + shot * 0.1
                elif step.measurement_id == "MS-00C":
                    # Raw installed orientation = scope(3.05) + installed geometry(5).
                    measured = 8.05 + shot * 0.1
                elif step.measurement_id == "TC-07":
                    # desired 70 ns; raw = desired + scope(3.05) - installed geometry(5)
                    measured = 68.05 + shot * 0.1
                else:
                    # Desired corrected = delay + fixed; add the 3.05 ns scope skew.
                    measured = delay + offsets[step.measurement_id] + 3.05 + shot * 0.1
                rows.append(
                    {
                        "measurement_id": step.measurement_id,
                        "setup_id": step.setup_id,
                        "programmed_delay_ns": int(delay),
                        "measured_separation_ns": measured,
                        "sample_interval_ns": 2.0,
                        "photodetector_threshold_sensitivity_standard_uncertainty_ns": (
                            0.2 if step.measurement_id == "TC-07" else ""
                        ),
                        "raw_trace_path": f"raw/{step.setup_id}/{delay}_{shot}.csv",
                    }
                )
    return rows


def _write_trace(path: Path, *, reference_falling: bool, target_index: int, target_level: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_index", "ch_a_adc", "ch_b_adc"])
        for index in range(80):
            ch_a = 10_000 if (reference_falling and index < 10) else 0
            if not reference_falling:
                ch_a = 10_000 if index >= 10 else 0
            ch_b = target_level if index >= target_index else 0
            writer.writerow([index, ch_a, ch_b])


def _write_fake_capture(
    path: Path,
    *,
    delay_ns: int,
    reference_falling: bool,
    target_falling: bool,
    optical: bool,
    beam_blocked: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    reference_index = 10
    target_index = 20 if optical else reference_index + int(delay_ns / 1000)
    total = max(100, target_index + 20)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_index", "ch_a_adc", "ch_b_adc"])
        for index in range(total):
            ch_a = (
                10_000 if index < reference_index else 0
            ) if reference_falling else (
                10_000 if index >= reference_index else 0
            )
            if beam_blocked:
                ch_b = 0
            elif optical or not target_falling:
                ch_b = 10_000 if index >= target_index else 0
            else:
                ch_b = 10_000 if index < target_index else 0
            writer.writerow([index, ch_a, ch_b])


if __name__ == "__main__":
    unittest.main()
