"""Legacy Day 8 electrical acquisition helpers and trace analysis.

The complete operator-guided Step 0-9 procedure is implemented in
``control_app.workflows.timing_calibration_procedure``.  This module remains the
shared low-level analyzer and preserves compatibility with earlier Day 8 runs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import bisect
from copy import deepcopy
import csv
import json
import math
import statistics
from xml.sax.saxutils import escape

import yaml

from control_app.config_loader import (
    ConfigInventory,
    REPO_ROOT,
    load_config_inventory,
    load_hardware_config,
)
from control_app.devices.picoscope_service import PicoScopeService
from control_app.workflows.picoscope_settings_test import (
    capture_settings_from_recipe,
    load_recipe as load_picoscope_recipe,
    validate_capture_settings,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


DEFAULT_SEPARATIONS_NS = (0, 100, 1_000, 10_000, 100_000, 1_000_000)
DEFAULT_SHOT_COUNT = 100
PAIR_MIN_PRETRIGGER_NS = {
    # This pair compares the T660-2 trigger pulse to a T660-1 output.
    # Keep more reference history visible because the output can correspond
    # to the immediately preceding visible trigger edge in the capture.
    "t660_1_trigger_to_pump_fire": 250_000.0,
}
PAIR_CLOCK_OVERRIDES = {
    # A continuous 2 MHz CHD train can trigger T660-1 again before a long
    # T660-1 delay has elapsed, which makes the 1 ms point ambiguous. Use a
    # sparse source train for this cross-unit trigger measurement so the
    # captured CHD edge is the trigger that produces the T660-1 output.
    "t660_1_trigger_to_pump_fire": {
        "t660_2": {
            "frequency": "500Hz",
            "shots": 0,
        },
    },
}
LASER_DRIVING_KEYWORDS = ("ndyag", "q_switch", "fire", "mircat", "laser", "opo")
ARTICLE_ROOT_CANDIDATES = (
    Path("/mnt/c/Users/Chris/Documents/UC Davis/SETI/Thesis/Article 1 - Review of Scientific Instruments"),
    Path(r"C:\Users\Chris\Documents\UC Davis\SETI\Thesis\Article 1 - Review of Scientific Instruments"),
)


@dataclass(frozen=True)
class CriticalPair:
    """One electrical timing pair that must be captured for Day 8."""

    pair_id: str
    reference_signal: str
    target_signal: str
    role: str
    scope_reference_channel: str = "A"
    scope_target_channel: str = "B"
    reference_edge: str = "rising"
    target_edge: str = "rising"


CRITICAL_PAIRS = (
    CriticalPair(
        pair_id="hf2li_extref_to_hf2li_daq_trigger",
        reference_signal="hf2li_extref",
        target_signal="hf2li_daq_trigger",
        role="HF2LI external reference to HF2LI DAQ trigger",
    ),
    CriticalPair(
        pair_id="hf2li_extref_to_qcl_probe_trigger",
        reference_signal="hf2li_extref",
        target_signal="mircat_trig_in",
        role="HF2LI external reference to QCL/probe trigger",
    ),
    CriticalPair(
        pair_id="t660_1_trigger_to_pump_fire",
        reference_signal="t660_1_trig_in",
        target_signal="ndyag_fire",
        role="T660-1 trigger input to pump fire trigger",
    ),
    CriticalPair(
        pair_id="pump_fire_to_q_switch",
        reference_signal="ndyag_fire",
        target_signal="ndyag_q_switch",
        role="Pump fire trigger to Q-switch trigger",
    ),
    CriticalPair(
        pair_id="t6601_ch_a_to_ch_c_channel_skew",
        reference_signal="ndyag_fire",
        target_signal="mircat_db9_pin_4_process_trigger",
        role="T660-1 CH A to CH C channel-skew measurement",
    ),
    CriticalPair(
        pair_id="t6601_ch_a_to_ch_d_channel_skew",
        reference_signal="ndyag_fire",
        target_signal="mircat_db9_pin_5_laser_output_on_off",
        role="T660-1 CH A to CH D channel-skew measurement",
    ),
)

DIAGNOSTIC_PAIRS = (
    CriticalPair(
        pair_id="t6602_ch_a_to_ch_b_channel_skew",
        reference_signal="hf2li_extref",
        target_signal="mircat_trig_in",
        role="T660-2 CH A to CH B diagnostic channel-skew measurement",
    ),
    CriticalPair(
        pair_id="t6602_ch_a_to_ch_c_channel_skew",
        reference_signal="hf2li_extref",
        target_signal="hf2li_daq_trigger",
        role="T660-2 CH A to CH C diagnostic channel-skew measurement",
    ),
    CriticalPair(
        pair_id="t6602_ch_a_to_ch_d_channel_skew",
        reference_signal="hf2li_extref",
        target_signal="t660_1_trig_in",
        role="T660-2 CH A to CH D diagnostic channel-skew measurement",
    ),
)


class Day8TimingCalibrationError(RuntimeError):
    """Raised when the Day 8 timing calibration cannot run or fails."""


class Day8TimingCalibration:
    """Program real timing hardware, capture Pico traces, and export timing offsets."""

    def __init__(
        self,
        *,
        operator: str,
        inventory: ConfigInventory | None = None,
        config_path: str | Path | None = None,
        command_log: TextIO | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(config_path, write_files=False)
        self.config_path = Path(self.inventory.config_path)
        self.command_log = command_log
        self.hardware_config, _, _ = load_hardware_config(self.config_path)

    def validate_plan(
        self,
        *,
        separations_ns: list[int] | None = None,
        shot_count: int = DEFAULT_SHOT_COUNT,
        reduced_set_rationale: str | None = None,
        pair_ids: list[str] | None = None,
        include_diagnostic_pairs: bool = False,
    ) -> dict[str, Any]:
        """Validate the Day 8 timing plan without opening hardware."""

        separations = list(separations_ns or DEFAULT_SEPARATIONS_NS)
        pairs = self._selected_pairs(
            pair_ids,
            include_diagnostic_pairs=include_diagnostic_pairs,
        )
        self._validate_reduced_set(separations, shot_count, reduced_set_rationale)
        self._validate_pair_signals(pairs)
        return {
            "timestamp_utc": _utc_now(),
            "operator": self.operator,
            "config_hash": self.inventory.config_hash,
            "separations_ns": separations,
            "shot_count": shot_count,
            "reduced_set_rationale": reduced_set_rationale,
            "critical_pairs": [self._pair_identity(pair) for pair in pairs],
            "route_identity": self.route_identity(pairs),
            "status": "VALIDATED_PREHARDWARE",
        }

    def route_identity(self, pairs: list[CriticalPair] | None = None) -> dict[str, Any]:
        """Return route, cable, polarity, edge, and time-zero conventions."""

        selected_pairs = pairs or list(CRITICAL_PAIRS)
        picoscope_connectors = self.hardware_config.get("picoscope_connectors") or {}
        return {
            "config_hash": self.inventory.config_hash,
            "config_path": self.inventory.config_path,
            "time_zero_convention": (
                "For each pair, time zero is the configured edge on PicoScope channel A. "
                "Measured separation is channel B target edge time minus channel A reference edge time."
            ),
            "positive_delay_convention": "Positive residual means the target edge arrived later than programmed.",
            "scope_channels": {
                "channel_a": picoscope_connectors.get("channel_a"),
                "channel_b": picoscope_connectors.get("channel_b"),
                "external_trigger": picoscope_connectors.get("external_trigger"),
                "external_trigger_role": (
                    "Pico EXT is not required for Day 8 when no splitter is available. "
                    "The Day 8 workflow triggers internally from PicoScope channel A and "
                    "then measures CH B edge time minus the recorded CH A edge time."
                ),
            },
            "direct_ttl_routes": self.inventory.timing_routes.get("direct_ttl_destinations", {}),
            "arduino_mux_status": {
                "active": False,
                "note": (
                    "Arduino MUX is bypassed; Day 8 timing signals are captured through "
                    "direct PicoScope/HF2LI wiring only."
                ),
            },
            "critical_pairs": [self._pair_identity(pair) for pair in selected_pairs],
            "uncertainty_budget_terms": [
                "PicoScope sample interval and interpolation limit",
                "edge-threshold sensitivity",
                "cable and connector skew between compared routes",
                "T660 programmed delay/readback precision",
                "shot-to-shot jitter estimated from repeated captures",
            ],
        }

    def run(
        self,
        *,
        run_dir: str | Path,
        picoscope_recipe_path: str | Path = "recipes/picoscope_settings_test.yaml",
        separations_ns: list[int] | None = None,
        shot_count: int = DEFAULT_SHOT_COUNT,
        pair_ids: list[str] | None = None,
        reduced_set_rationale: str | None = None,
        confirm_safe_electrical_routing: bool = False,
        article_root: str | Path | None = None,
        command_log_paths: list[str] | None = None,
        diagnostic_only: bool = False,
        include_diagnostic_pairs: bool = False,
    ) -> dict[str, Any]:
        """Run real Day 8 timing acquisition and write calibration artifacts."""

        if not confirm_safe_electrical_routing:
            raise Day8TimingCalibrationError(
                "Safe electrical routing confirmation is required before enabling timing outputs."
            )
        separations = list(separations_ns or DEFAULT_SEPARATIONS_NS)
        pairs = self._selected_pairs(
            pair_ids,
            include_diagnostic_pairs=include_diagnostic_pairs,
        )
        self._validate_reduced_set(separations, shot_count, reduced_set_rationale)
        self._validate_pair_signals(pairs)

        run_path = Path(run_dir)
        if not run_path.is_absolute():
            run_path = REPO_ROOT / run_path
        run_path.mkdir(parents=True, exist_ok=True)
        raw_dir = run_path / "raw_pico_traces"
        readback_dir = run_path / "timing_readbacks"
        raw_dir.mkdir(parents=True, exist_ok=True)
        readback_dir.mkdir(parents=True, exist_ok=True)

        recipe, resolved_pico_recipe = load_picoscope_recipe(picoscope_recipe_path)
        base_capture_settings = _settings_with_channel_a_trigger(capture_settings_from_recipe(recipe))
        device_config = self.inventory.devices.get("picoscope")
        if not isinstance(device_config, dict):
            raise Day8TimingCalibrationError("picoscope missing from hardware_configuration.yaml")
        validate_capture_settings(base_capture_settings, device_config)

        route_identity_path = run_path / "route_identity.json"
        route_identity = self.route_identity(pairs)
        _write_json(route_identity_path, route_identity)

        timing_manager = TimingRecipeManager(self.inventory, command_log=self.command_log)
        pico = PicoScopeService(device_config, base_capture_settings, command_log=self.command_log)
        rows: list[dict[str, Any]] = []
        raw_paths: list[str] = []
        readback_paths: list[str] = [str(route_identity_path)]
        base_timing_validation: dict[str, Any] | None = None
        capture_profiles: dict[str, dict[str, Any]] = {}
        try:
            base_readback_path = readback_dir / "timing_calibration_recipe_readback.json"
            timing_manager.apply_recipe(
                REPO_ROOT / "recipes" / "timing_calibration.yaml",
                output_path=base_readback_path,
            )
            readback_paths.append(str(base_readback_path))

            pico.open_unit()
            pico.apply_capture_settings()
            base_timing_validation = pico.validate_sample_timing()
            base_sample_interval_ns = float(base_timing_validation["sample_interval_ns"])

            for pair in pairs:
                for separation_ns in separations:
                    capture_settings = _capture_settings_for_separation(
                        base_capture_settings,
                        separation_ns=separation_ns,
                        sample_interval_ns=base_sample_interval_ns,
                        min_pretrigger_ns=PAIR_MIN_PRETRIGGER_NS.get(pair.pair_id),
                    )
                    validate_capture_settings(capture_settings, device_config)
                    pico.capture_settings = capture_settings
                    pico.apply_capture_settings()
                    timing_validation = pico.validate_sample_timing()
                    sample_interval_ns = float(timing_validation["sample_interval_ns"])
                    _validate_capture_window(
                        capture_settings,
                        sample_interval_ns=sample_interval_ns,
                        separations_ns=[separation_ns],
                    )
                    capture_profiles[str(separation_ns)] = {
                        "capture_settings": capture_settings,
                        "sample_timing_validation": timing_validation,
                        "capture_span_ns": _capture_span_ns(
                            capture_settings,
                            sample_interval_ns=sample_interval_ns,
                        ),
                        "post_trigger_span_ns": _post_trigger_span_ns(
                            capture_settings,
                            sample_interval_ns=sample_interval_ns,
                        ),
                    }
                    timing_recipe = self._build_pair_recipe(
                        pair,
                        programmed_separation_ns=separation_ns,
                    )
                    readback_path = (
                        readback_dir
                        / f"{pair.pair_id}_sep_{_delay_slug(separation_ns)}_recipe_readback.json"
                    )
                    timing_manager.apply_recipe(timing_recipe, output_path=readback_path)
                    readback_paths.append(str(readback_path))

                    for shot_index in range(shot_count):
                        raw_path = (
                            raw_dir
                            / pair.pair_id
                            / f"sep_{_delay_slug(separation_ns)}_shot_{shot_index:03d}.csv"
                        )
                        capture_summary = pico.capture_block(raw_path)
                        raw_paths.append(str(raw_path))
                        measurement = analyze_pico_trace(
                            raw_path,
                            sample_interval_ns=sample_interval_ns,
                            threshold_adc=int(capture_settings.get("pulse_count_threshold_adc", 5000)),
                            programmed_separation_ns=separation_ns,
                            reference_edge=pair.reference_edge,
                            target_edge=pair.target_edge,
                        )
                        rows.append(
                            {
                                "timestamp_utc": _utc_now(),
                                "operator": self.operator,
                                "config_hash": self.inventory.config_hash,
                                "pair_id": pair.pair_id,
                                "role": pair.role,
                                "reference_signal": pair.reference_signal,
                                "target_signal": pair.target_signal,
                                "programmed_separation_ns": separation_ns,
                                "shot_index": shot_index,
                                "measured_separation_ns": measurement["measured_separation_ns"],
                                "residual_ns": measurement["residual_ns"],
                                "reference_edge_time_ns": measurement["reference_edge_time_ns"],
                                "target_edge_time_ns": measurement["target_edge_time_ns"],
                                "expected_target_edge_time_ns": measurement[
                                    "expected_target_edge_time_ns"
                                ],
                                "target_edge_selection_error_ns": measurement[
                                    "target_edge_selection_error_ns"
                                ],
                                "reference_edge_count": measurement["reference_edge_count"],
                                "target_edge_count": measurement["target_edge_count"],
                                "reference_edge": pair.reference_edge,
                                "target_edge": pair.target_edge,
                                "threshold_adc": measurement["threshold_adc"],
                                "sample_interval_ns": sample_interval_ns,
                                "picoscope_timebase": int(capture_settings["timebase"]),
                                "picoscope_total_samples": int(capture_settings["total_samples"]),
                                "picoscope_pre_trigger_samples": int(
                                    capture_settings["pre_trigger_samples"]
                                ),
                                "picoscope_capture_span_ns": _capture_span_ns(
                                    capture_settings,
                                    sample_interval_ns=sample_interval_ns,
                                ),
                                "raw_trace_path": str(raw_path),
                                "capture_summary": json.dumps(capture_summary, sort_keys=True),
                            }
                        )
        finally:
            try:
                pico.stop()
            finally:
                pico.close_unit()
            safe_idle_path = readback_dir / "safe_idle_after_day8_timing_readback.json"
            try:
                timing_manager.apply_recipe(REPO_ROOT / "recipes" / "safe_idle.yaml", output_path=safe_idle_path)
                readback_paths.append(str(safe_idle_path))
            except Exception as exc:  # noqa: BLE001 - caller records exact safe-state failure
                if self.command_log is not None:
                    self.command_log.write(f"{_utc_now()} day8 safe_idle failed: {exc}\n")
                    self.command_log.flush()

        if not rows:
            raise Day8TimingCalibrationError("No timing rows were acquired")

        per_shot_csv = run_path / "timing_pair_results.csv"
        _write_rows(per_shot_csv, rows)
        readback_paths.append(str(per_shot_csv))

        calibration_csv = REPO_ROOT / "calibration" / "timing_calibration.csv"
        offsets_yaml = REPO_ROOT / "calibration" / "timing_offsets.yaml"
        current_calibration_rows, _ = aggregate_timing_rows(
            rows,
            route_identity=route_identity,
            reduced_set_rationale=reduced_set_rationale,
        )
        if diagnostic_only:
            calibration_rows = current_calibration_rows
            calibration_csv = run_path / "timing_calibration_summary.csv"
            offsets_yaml = run_path / "timing_offsets_diagnostic.yaml"
            offsets = _offsets_from_calibration_rows(
                calibration_rows,
                route_identity=route_identity,
                reduced_set_rationale=reduced_set_rationale,
                config_hash=self.inventory.config_hash,
            )
            offsets["diagnostic_only"] = True
            offsets["note"] = (
                "Diagnostic channel-skew data only. Do not use these rows as final "
                "experiment route timing offsets."
            )
            _write_rows(calibration_csv, calibration_rows)
            _write_yaml(offsets_yaml, offsets)
            article_outputs: dict[str, str] = {}
            readback_paths.extend([str(calibration_csv), str(offsets_yaml)])
        else:
            calibration_rows = _merge_calibration_rows(calibration_csv, current_calibration_rows)
            offsets = _offsets_from_calibration_rows(
                calibration_rows,
                route_identity=route_identity,
                reduced_set_rationale=reduced_set_rationale,
                config_hash=self.inventory.config_hash,
            )
            _write_rows(calibration_csv, calibration_rows)
            _write_yaml(offsets_yaml, offsets)
            article_outputs = export_article_outputs(
                calibration_rows,
                article_root=article_root,
            )
            readback_paths.extend([str(calibration_csv), str(offsets_yaml)])
            readback_paths.extend(article_outputs.values())

        summary = {
            "timestamp_utc": _utc_now(),
            "operator": self.operator,
            "config_hash": self.inventory.config_hash,
            "picoscope_recipe_path": str(resolved_pico_recipe),
            "picoscope_settings": base_capture_settings,
            "picoscope_capture_profiles": capture_profiles,
            "sample_timing_validation": base_timing_validation,
            "sample_timing_validations": {
                separation: profile["sample_timing_validation"]
                for separation, profile in capture_profiles.items()
            },
            "separations_ns": separations,
            "shot_count": shot_count,
            "reduced_set_rationale": reduced_set_rationale,
            "diagnostic_only": diagnostic_only,
            "route_identity_path": str(route_identity_path),
            "per_shot_csv": str(per_shot_csv),
            "timing_calibration_csv": str(calibration_csv),
            "timing_offsets_yaml": str(offsets_yaml),
            "article_outputs": article_outputs,
            "raw_data_paths": raw_paths,
            "device_readback_paths": readback_paths,
            "command_log_paths": command_log_paths or [],
            "status": "PASS",
        }
        _write_json(run_path / "workflow_summary.json", summary)
        return summary

    def _selected_pairs(
        self,
        pair_ids: list[str] | None,
        *,
        include_diagnostic_pairs: bool = False,
    ) -> list[CriticalPair]:
        if not pair_ids:
            return list(CRITICAL_PAIRS)
        pairs = {pair.pair_id: pair for pair in CRITICAL_PAIRS}
        if include_diagnostic_pairs:
            pairs.update({pair.pair_id: pair for pair in DIAGNOSTIC_PAIRS})
        missing = [pair_id for pair_id in pair_ids if pair_id not in pairs]
        if missing:
            raise Day8TimingCalibrationError("Unknown Day 8 timing pair(s): " + ", ".join(missing))
        return [pairs[pair_id] for pair_id in pair_ids]

    def _validate_pair_signals(self, pairs: list[CriticalPair]) -> None:
        for pair in pairs:
            for signal in (pair.reference_signal, pair.target_signal):
                if signal not in self.inventory.signal_map:
                    raise Day8TimingCalibrationError(
                        f"Signal {signal!r} is not defined in hardware_configuration.yaml"
                    )

    def _validate_reduced_set(
        self,
        separations_ns: list[int],
        shot_count: int,
        reduced_set_rationale: str | None,
    ) -> None:
        if shot_count <= 0:
            raise Day8TimingCalibrationError("shot_count must be positive")
        expected = list(DEFAULT_SEPARATIONS_NS)
        reduced = shot_count != DEFAULT_SHOT_COUNT or separations_ns != expected
        if reduced and not reduced_set_rationale:
            raise Day8TimingCalibrationError(
                "A reduced Day 8 timing set requires an approved rationale."
            )

    def _pair_identity(self, pair: CriticalPair) -> dict[str, Any]:
        reference = self._signal_identity(pair.reference_signal)
        target = self._signal_identity(pair.target_signal)
        return {
            **asdict(pair),
            "reference_route": reference,
            "target_route": target,
            "laser_driving_output_present": self._is_laser_driving(pair.reference_signal)
            or self._is_laser_driving(pair.target_signal),
            "polarity": "positive TTL unless hardware readback reports otherwise",
            "scope_cabling_requirement": (
                f"Connect {pair.reference_signal} to PicoScope channel {pair.scope_reference_channel}; "
                f"connect {pair.target_signal} to PicoScope channel {pair.scope_target_channel}. "
                "The Day 8 workflow uses PicoScope channel A as the internal trigger."
            ),
        }

    def _signal_identity(self, signal: str) -> dict[str, Any]:
        mapping = self.inventory.signal_map[signal]
        direct_key = f"{mapping['device']}_channel_{mapping['channel'].lower()}"
        return {
            "signal": signal,
            "device": mapping["device"],
            "channel": mapping["channel"],
            "direct_destination": (
                self.inventory.timing_routes.get("direct_ttl_destinations", {}).get(direct_key)
            ),
        }

    def _build_pair_recipe(
        self,
        pair: CriticalPair,
        *,
        programmed_separation_ns: int,
    ) -> dict[str, Any]:
        units: dict[str, dict[str, Any]] = {}
        reference = self.inventory.signal_map[pair.reference_signal]
        target = self.inventory.signal_map[pair.target_signal]
        for mapping, signal, delay_ns in (
            (reference, pair.reference_signal, 0),
            (target, pair.target_signal, programmed_separation_ns),
        ):
            self._add_signal_to_recipe(units, mapping, signal, delay_ns)
        for mapping in (reference, target):
            self._add_trigger_source_if_needed(units, mapping["device"])
        for unit, clock in PAIR_CLOCK_OVERRIDES.get(pair.pair_id, {}).items():
            if unit in units:
                units[unit]["clock"] = dict(clock)
        return {
            "name": f"day8_{pair.pair_id}_{_delay_slug(programmed_separation_ns)}",
            "description": "Day 8 electrical timing calibration recipe generated from hardware_configuration.yaml.",
            "approved_laser_safety_condition": True,
            "day8_electrical_timing_only": True,
            "laser_emission_commands_sent": False,
            "t660": units,
        }

    def _add_signal_to_recipe(
        self,
        units: dict[str, dict[str, Any]],
        mapping: dict[str, str],
        signal: str,
        delay_ns: int,
    ) -> None:
        unit = mapping["device"]
        channel = mapping["channel"]
        unit_recipe = units.setdefault(
            unit,
            {
                "stop_first": True,
                "trigger_source": self._trigger_source_for_unit(unit),
                "force_eod": True,
                "start": True,
                "channels": {},
            },
        )
        unit_recipe["channels"][channel] = {
            "delay": f"{int(delay_ns)}ns",
            "width": "150ns",
            "polarity": "positive",
            "termination": "50OHM",
            "enabled": True,
            "signal": signal,
        }

    def _add_trigger_source_if_needed(self, units: dict[str, dict[str, Any]], unit: str) -> None:
        unit_config = self.inventory.t660_devices.get(unit, {})
        trigger_input = unit_config.get("trigger_input")
        if not isinstance(trigger_input, dict):
            return
        source_unit = str(trigger_input.get("source_device") or "")
        source_channel = str(trigger_input.get("source_channel") or "").upper()
        if not source_unit or not source_channel:
            return
        signal = str((self.inventory.t660_devices.get(source_unit, {}).get("channel_map") or {}).get(source_channel, source_channel))
        self._add_signal_to_recipe(
            units,
            {"device": source_unit, "channel": source_channel},
            signal,
            0,
        )

    def _trigger_source_for_unit(self, unit: str) -> str:
        unit_config = self.inventory.t660_devices.get(unit, {})
        if isinstance(unit_config.get("trigger_input"), dict):
            return "EXT"
        return "SYN"

    @staticmethod
    def _is_laser_driving(signal: str) -> bool:
        lowered = signal.lower()
        return any(keyword in lowered for keyword in LASER_DRIVING_KEYWORDS)


def analyze_pico_trace(
    raw_csv_path: str | Path,
    *,
    sample_interval_ns: float,
    threshold_adc: int,
    programmed_separation_ns: float = 0.0,
    reference_edge: str = "rising",
    target_edge: str = "rising",
    target_selection_tolerance_ns: float | None = None,
) -> dict[str, Any]:
    """Measure edge separation from one real PicoScope trace CSV."""

    samples_a: list[int] = []
    samples_b: list[int] = []
    with Path(raw_csv_path).open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            samples_a.append(int(row["ch_a_adc"]))
            samples_b.append(int(row["ch_b_adc"]))
    if not samples_a or not samples_b:
        raise Day8TimingCalibrationError(f"No samples found in {raw_csv_path}")
    reference_indices = _edge_indices(samples_a, threshold_adc, reference_edge)
    target_indices = _edge_indices(samples_b, threshold_adc, target_edge)
    reference_index, target_index, target_error_ns = _select_edge_pair(
        reference_indices,
        target_indices,
        sample_interval_ns=sample_interval_ns,
        programmed_separation_ns=programmed_separation_ns,
        tolerance_ns=target_selection_tolerance_ns,
        raw_csv_path=raw_csv_path,
    )
    reference_time_ns = reference_index * sample_interval_ns
    target_time_ns = target_index * sample_interval_ns
    measured = target_time_ns - reference_time_ns
    residual = measured - programmed_separation_ns
    return {
        "raw_csv_path": str(raw_csv_path),
        "threshold_adc": threshold_adc,
        "sample_interval_ns": sample_interval_ns,
        "programmed_separation_ns": programmed_separation_ns,
        "reference_edge_sample": reference_index,
        "target_edge_sample": target_index,
        "reference_edge_time_ns": reference_time_ns,
        "target_edge_time_ns": target_time_ns,
        "expected_target_edge_time_ns": reference_time_ns + programmed_separation_ns,
        "target_edge_selection_error_ns": target_error_ns,
        "reference_edge_count": len(reference_indices),
        "target_edge_count": len(target_indices),
        "measured_separation_ns": measured,
        "residual_ns": residual,
    }


def aggregate_timing_rows(
    rows: list[dict[str, Any]],
    *,
    route_identity: dict[str, Any],
    reduced_set_rationale: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aggregate per-shot timing rows into calibration tables and offsets YAML."""

    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["pair_id"]), int(row["programmed_separation_ns"]))
        grouped.setdefault(key, []).append(row)

    calibration_rows: list[dict[str, Any]] = []
    offsets: dict[str, Any] = {
        "schema_version": "0.1",
        "generated_utc": _utc_now(),
        "config_hash": rows[0]["config_hash"],
        "time_zero_convention": route_identity["time_zero_convention"],
        "positive_delay_convention": route_identity["positive_delay_convention"],
        "reduced_set_rationale": reduced_set_rationale,
        "pairs": {},
    }

    for (pair_id, separation_ns), group in sorted(grouped.items()):
        measured = [float(row["measured_separation_ns"]) for row in group]
        residuals = [float(row["residual_ns"]) for row in group]
        mean_measured = statistics.fmean(measured)
        mean_residual = statistics.fmean(residuals)
        jitter = statistics.stdev(residuals) if len(residuals) > 1 else 0.0
        sample_interval = float(group[0]["sample_interval_ns"])
        row = {
            "pair_id": pair_id,
            "role": group[0]["role"],
            "reference_signal": group[0]["reference_signal"],
            "target_signal": group[0]["target_signal"],
            "programmed_separation_ns": separation_ns,
            "shot_count": len(group),
            "mean_measured_separation_ns": mean_measured,
            "mean_residual_ns": mean_residual,
            "jitter_std_ns": jitter,
            "min_residual_ns": min(residuals),
            "max_residual_ns": max(residuals),
            "sample_interval_ns": sample_interval,
            "bounded_uncertainty_ns": max(abs(mean_residual), jitter, sample_interval),
            "source_first_raw_trace": group[0]["raw_trace_path"],
        }
        calibration_rows.append(row)
        pair_offsets = offsets["pairs"].setdefault(pair_id, {"separations": {}})
        pair_offsets["role"] = group[0]["role"]
        pair_offsets["reference_signal"] = group[0]["reference_signal"]
        pair_offsets["target_signal"] = group[0]["target_signal"]
        pair_offsets["separations"][str(separation_ns)] = {
            "mean_measured_separation_ns": mean_measured,
            "mean_residual_ns": mean_residual,
            "jitter_std_ns": jitter,
            "shot_count": len(group),
            "bounded_uncertainty_ns": row["bounded_uncertainty_ns"],
            "source_first_raw_trace": group[0]["raw_trace_path"],
        }
    return calibration_rows, offsets


def export_article_outputs(
    calibration_rows: list[dict[str, Any]],
    *,
    article_root: str | Path | None = None,
) -> dict[str, str]:
    """Export Day 8 tables and plots only under the Article 1 RSI folder."""

    root = Path(article_root) if article_root is not None else _default_article_root()
    tables_dir = root / "Tables"
    figures_dir = root / "Figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    calibration_table = tables_dir / "Day8_Timing_Calibration_Table.csv"
    uncertainty_table = tables_dir / "Day8_Timing_Uncertainty_Budget.csv"
    residual_plot = figures_dir / "Day8_Timing_Residuals.svg"
    jitter_plot = figures_dir / "Day8_Timing_Jitter.svg"

    _write_rows(calibration_table, calibration_rows)
    _write_rows(uncertainty_table, _uncertainty_rows(calibration_rows))
    _write_svg_plot(
        residual_plot,
        calibration_rows,
        y_field="mean_residual_ns",
        title="Day 8 Timing Residuals",
        y_label="Mean residual (ns)",
    )
    _write_svg_plot(
        jitter_plot,
        calibration_rows,
        y_field="jitter_std_ns",
        title="Day 8 Timing Jitter",
        y_label="Jitter standard deviation (ns)",
    )
    return {
        "timing_calibration_table": str(calibration_table),
        "uncertainty_budget_table": str(uncertainty_table),
        "residual_plot": str(residual_plot),
        "jitter_plot": str(jitter_plot),
    }


def _uncertainty_rows(calibration_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in calibration_rows:
        rows.append(
            {
                "pair_id": row["pair_id"],
                "programmed_separation_ns": row["programmed_separation_ns"],
                "shot_count": row["shot_count"],
                "sample_interval_ns": row["sample_interval_ns"],
                "mean_residual_ns": row["mean_residual_ns"],
                "jitter_std_ns": row["jitter_std_ns"],
                "bounded_uncertainty_ns": row["bounded_uncertainty_ns"],
                "uncertainty_terms": (
                    "sample interval/interpolation; threshold sensitivity; cable skew; "
                    "T660 delay precision; shot-to-shot jitter"
                ),
                "source_first_raw_trace": row["source_first_raw_trace"],
            }
        )
    return rows


def _merge_calibration_rows(
    calibration_csv: str | Path,
    current_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge current pair/separation rows with existing aggregate rows."""

    target = Path(calibration_csv)
    existing: list[dict[str, Any]] = []
    if target.exists():
        with target.open("r", newline="", encoding="utf-8") as handle:
            existing = list(csv.DictReader(handle))
    current_keys = {
        (str(row["pair_id"]), str(row["programmed_separation_ns"]))
        for row in current_rows
    }
    merged = [
        row
        for row in existing
        if (str(row.get("pair_id")), str(row.get("programmed_separation_ns"))) not in current_keys
    ]
    merged.extend(current_rows)
    return sorted(
        merged,
        key=lambda row: (str(row["pair_id"]), int(float(row["programmed_separation_ns"]))),
    )


def _offsets_from_calibration_rows(
    calibration_rows: list[dict[str, Any]],
    *,
    route_identity: dict[str, Any],
    reduced_set_rationale: str | None,
    config_hash: str,
) -> dict[str, Any]:
    offsets: dict[str, Any] = {
        "schema_version": "0.1",
        "generated_utc": _utc_now(),
        "config_hash": config_hash,
        "time_zero_convention": route_identity["time_zero_convention"],
        "positive_delay_convention": route_identity["positive_delay_convention"],
        "reduced_set_rationale": reduced_set_rationale,
        "pairs": {},
    }
    for row in calibration_rows:
        pair_offsets = offsets["pairs"].setdefault(str(row["pair_id"]), {"separations": {}})
        pair_offsets["role"] = row["role"]
        pair_offsets["reference_signal"] = row["reference_signal"]
        pair_offsets["target_signal"] = row["target_signal"]
        separation = str(int(float(row["programmed_separation_ns"])))
        pair_offsets["separations"][separation] = {
            "mean_measured_separation_ns": float(row["mean_measured_separation_ns"]),
            "mean_residual_ns": float(row["mean_residual_ns"]),
            "jitter_std_ns": float(row["jitter_std_ns"]),
            "shot_count": int(float(row["shot_count"])),
            "bounded_uncertainty_ns": float(row["bounded_uncertainty_ns"]),
            "source_first_raw_trace": row["source_first_raw_trace"],
        }
    return offsets


def _write_svg_plot(
    path: str | Path,
    rows: list[dict[str, Any]],
    *,
    y_field: str,
    title: str,
    y_label: str,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    width = 1200
    height = 640
    left = 90
    right = 35
    top = 60
    bottom = 150
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [float(row[y_field]) for row in rows]
    min_y = min(values)
    max_y = max(values)
    if min_y == max_y:
        pad = max(abs(min_y) * 0.1, 1.0)
        min_y -= pad
        max_y += pad
    else:
        pad = (max_y - min_y) * 0.1
        min_y -= pad
        max_y += pad
    denom = max_y - min_y

    points = []
    for index, row in enumerate(rows):
        x = left + (plot_width * index / max(len(rows) - 1, 1))
        y = top + plot_height - ((float(row[y_field]) - min_y) / denom * plot_height)
        points.append((x, y, row))

    palette = ["#1f6feb", "#2da44e", "#d1242f", "#8250df", "#bf8700", "#0969da"]
    pair_colors: dict[str, str] = {}
    for row in rows:
        pair = str(row["pair_id"])
        if pair not in pair_colors:
            pair_colors[pair] = palette[len(pair_colors) % len(palette)]

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="640" viewBox="0 0 1200 640">',
        '<rect width="1200" height="640" fill="#ffffff"/>',
        f'<text x="{width / 2}" y="30" text-anchor="middle" font-family="Arial" font-size="22" fill="#111111">{escape(title)}</text>',
        f'<text x="28" y="{top + plot_height / 2}" text-anchor="middle" font-family="Arial" font-size="15" fill="#111111" transform="rotate(-90 28 {top + plot_height / 2})">{escape(y_label)}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#444444"/>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#444444"/>',
    ]
    for step in range(5):
        frac = step / 4
        y = top + plot_height - frac * plot_height
        value = min_y + frac * denom
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#dddddd"/>')
        lines.append(f'<text x="{left - 10}" y="{y + 5:.2f}" text-anchor="end" font-family="Arial" font-size="12" fill="#333333">{value:.3g}</text>')

    by_pair: dict[str, list[tuple[float, float, dict[str, Any]]]] = {}
    for point in points:
        by_pair.setdefault(str(point[2]["pair_id"]), []).append(point)
    for pair_id, pair_points in by_pair.items():
        color = pair_colors[pair_id]
        polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y, _ in pair_points)
        lines.append(f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2"/>')
        for x, y, row in pair_points:
            label = f"{row['pair_id']} {row['programmed_separation_ns']} ns"
            lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}"><title>{escape(label)}</title></circle>')

    for index, (x, _, row) in enumerate(points):
        label = str(row["programmed_separation_ns"])
        if index == 0 or index == len(points) - 1 or index % max(len(DEFAULT_SEPARATIONS_NS), 1) == 0:
            lines.append(f'<text x="{x:.2f}" y="{top + plot_height + 24}" text-anchor="middle" font-family="Arial" font-size="11" fill="#333333">{escape(label)}</text>')

    legend_x = left
    legend_y = height - 90
    for index, (pair_id, color) in enumerate(pair_colors.items()):
        y = legend_y + index * 18
        lines.append(f'<rect x="{legend_x}" y="{y - 10}" width="12" height="12" fill="{color}"/>')
        lines.append(f'<text x="{legend_x + 18}" y="{y}" font-family="Arial" font-size="12" fill="#111111">{escape(pair_id)}</text>')
    lines.append('<text x="650" y="610" text-anchor="middle" font-family="Arial" font-size="13" fill="#111111">Programmed separation groups, ns</text>')
    lines.append("</svg>")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _edge_indices(samples: list[int], threshold_adc: int, edge: str) -> list[float]:
    normalized = edge.lower()
    if normalized not in {"rising", "falling"}:
        raise Day8TimingCalibrationError(f"Unsupported edge definition {edge!r}")
    edges: list[float] = []
    for index in range(1, len(samples)):
        previous = samples[index - 1]
        current = samples[index]
        if normalized == "rising":
            crossed = previous < threshold_adc <= current
        else:
            crossed = previous > threshold_adc >= current
        if crossed:
            span = current - previous
            if span == 0:
                edges.append(float(index))
            else:
                edges.append((index - 1) + ((threshold_adc - previous) / span))
    if edges:
        return edges
    raise Day8TimingCalibrationError(
        f"No {normalized} edge crossed threshold {threshold_adc} ADC counts"
    )


def _select_edge_pair(
    reference_indices: list[float],
    target_indices: list[float],
    *,
    sample_interval_ns: float,
    programmed_separation_ns: float,
    tolerance_ns: float | None,
    raw_csv_path: str | Path,
) -> tuple[float, float, float]:
    if not reference_indices or not target_indices:
        raise Day8TimingCalibrationError(f"Missing reference or target edge in {raw_csv_path}")
    tolerance = float(tolerance_ns if tolerance_ns is not None else max(100.0, 10.0 * sample_interval_ns))
    programmed_samples = programmed_separation_ns / sample_interval_ns
    best: tuple[float, float, float] | None = None
    for reference_index in reference_indices:
        expected_target_index = reference_index + programmed_samples
        insert_at = bisect.bisect_left(target_indices, expected_target_index)
        for candidate_position in (insert_at - 1, insert_at):
            if candidate_position < 0 or candidate_position >= len(target_indices):
                continue
            target_index = target_indices[candidate_position]
            error_ns = abs((target_index - expected_target_index) * sample_interval_ns)
            if best is None or error_ns < best[0]:
                best = (error_ns, reference_index, target_index)
    if best is None:
        raise Day8TimingCalibrationError(f"No comparable edge pair found in {raw_csv_path}")
    error_ns, reference_index, target_index = best
    if error_ns > tolerance:
        raise Day8TimingCalibrationError(
            "No target edge matched the programmed separation in "
            f"{raw_csv_path}; best error was {error_ns:.3f} ns for "
            f"{programmed_separation_ns:.3f} ns programmed separation. "
            "Increase PicoScope capture span or inspect the T660 output."
        )
    return reference_index, target_index, error_ns


def _capture_settings_for_separation(
    base_capture_settings: dict[str, Any],
    *,
    separation_ns: int,
    sample_interval_ns: float,
    min_pretrigger_ns: float | None = None,
) -> dict[str, Any]:
    settings = deepcopy(base_capture_settings)
    pre_trigger_samples = int(settings.get("pre_trigger_samples", 0))
    if min_pretrigger_ns is not None:
        pre_trigger_samples = max(
            pre_trigger_samples,
            math.ceil(float(min_pretrigger_ns) / sample_interval_ns),
        )
        settings["pre_trigger_samples"] = pre_trigger_samples
    total_samples = int(settings.get("total_samples", 0))
    margin_ns = _capture_window_margin_ns(sample_interval_ns)
    required_post_trigger_samples = math.ceil((separation_ns + margin_ns) / sample_interval_ns)
    required_total_samples = pre_trigger_samples + required_post_trigger_samples
    if required_total_samples > total_samples:
        settings["total_samples"] = _round_up(required_total_samples, 1_000)
    return settings


def _capture_window_margin_ns(sample_interval_ns: float) -> float:
    return max(10_000.0, 50.0 * sample_interval_ns)


def _round_up(value: int, increment: int) -> int:
    return ((value + increment - 1) // increment) * increment


def _capture_span_ns(capture_settings: dict[str, Any], *, sample_interval_ns: float) -> float:
    return int(capture_settings.get("total_samples", 0)) * sample_interval_ns


def _post_trigger_span_ns(capture_settings: dict[str, Any], *, sample_interval_ns: float) -> float:
    total_samples = int(capture_settings.get("total_samples", 0))
    pre_trigger_samples = int(capture_settings.get("pre_trigger_samples", 0))
    return max(total_samples - pre_trigger_samples, 0) * sample_interval_ns


def _validate_capture_window(
    capture_settings: dict[str, Any],
    *,
    sample_interval_ns: float,
    separations_ns: list[int],
) -> None:
    post_trigger_span_ns = _post_trigger_span_ns(
        capture_settings,
        sample_interval_ns=sample_interval_ns,
    )
    largest_separation_ns = max(separations_ns) if separations_ns else 0
    margin_ns = _capture_window_margin_ns(sample_interval_ns)
    if largest_separation_ns + margin_ns > post_trigger_span_ns:
        raise Day8TimingCalibrationError(
            "PicoScope post-trigger capture span is too short for the requested Day 8 timing set: "
            f"{post_trigger_span_ns:.0f} ns available after trigger, "
            f"{largest_separation_ns} ns requested. "
            "Use a longer PicoScope capture profile."
        )


def _write_rows(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise Day8TimingCalibrationError(f"No rows to write for {target}")
    fieldnames = list(rows[0].keys())
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def _write_json(path: str | Path, data: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _write_yaml(path: str | Path, data: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    return target


def _settings_with_channel_a_trigger(settings: dict[str, Any]) -> dict[str, Any]:
    """Return a capture-settings copy that triggers internally from channel A."""

    copied = json.loads(json.dumps(settings))
    trigger = copied.setdefault("external_trigger", {})
    trigger["source"] = "A"
    trigger["direction"] = int(trigger.get("direction", 2))
    trigger["direction_name"] = "rising"
    return copied


def _delay_slug(delay_ns: int) -> str:
    return str(int(delay_ns)).replace("-", "m") + "ns"


def _default_article_root() -> Path:
    for candidate in ARTICLE_ROOT_CANDIDATES:
        if candidate.exists():
            return candidate
    return ARTICLE_ROOT_CANDIDATES[-1]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
