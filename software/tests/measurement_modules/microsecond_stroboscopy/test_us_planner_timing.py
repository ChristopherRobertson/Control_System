"""Independent hardware-free scientific planner and installed-protocol checks."""
from copy import deepcopy
from dataclasses import replace
import json
import math

import pytest

from control_app.devices.t660_service import T660Service
from control_app.measurement_modules.microsecond_stroboscopy.planner import (
    InstalledCapabilities, Qualification, apply_qualified_recommendations, build_plan,
    capabilities_from_readbacks, select_supported_response,
)
from control_app.measurement_modules.microsecond_stroboscopy.settings import (
    StroboscopySettings, default_settings, information_delay_grid,
    literature_coverage_example_us, local_spectral_window,
)
from control_app.measurement_modules.microsecond_stroboscopy.timing import compile_timing


def compact(mode="single"):
    s = default_settings(mode)
    return replace(s, spectral_points=s.spectral_points[:1], delays_us=(-100., 25., 250., 1000.), averages=2,
                   controls=replace(s.controls, dark_record_id="TEST-DARK"))


def qualified(s):
    return Qualification.from_dict({
        "experiment_id": "microsecond_stroboscopy", "profile_id": "TEST-QUALIFIED",
        "modes": [s.mode], "condition_profile_ids": [s.condition_profile_id],
        "wiring_id": "TEST-INSTALLED-TEE", "reset_equivalence_id": "TEST-RESET",
        "response_calibration_id": "TEST-IRF",
        "timing": {"variable_sync_to_pump_s": 10e-6, "optical_latency_calibration_id": "TEST-OPTICAL"},
        "hf2li": {"signal_inputs": {"sample": {"index": 0}}, "pll": {"enable": 1},
                  "signed_x_calibration_id": "TEST-X", "phase_shift_deg": {"0": 0, "3": 0},
                  "integrity_nodes": [{"type": "int", "path": "/test/status", "expected": 0}]},
        "timing_clock_readbacks": {"t660_1": {"clock_status": "TEST-LOCKED"}, "t660_2": {"clock_status": "TEST-MASTER"}},
        "normalization": {"dark_offsets": {
            role: {"record_id": s.controls.dark_record_id, "offset": 0.001, "standard_error": 0.0001}
            for role in ("sample", "reference") if s.mode == "dual" or role == "sample"}},
        "tune_tolerance_cm1": .05, "tune_timeout_s": 5., "settle_s": .1,
    })


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_us_planner_default_is_valid_hardware_free_and_explicitly_unqualified(mode):
    p = build_plan(default_settings(mode))
    assert p.readiness.valid
    assert not p.hardware_ready
    assert "EXAMPLE ONLY" in p.settings.operating_basis
    assert any("promoted" in text for text in p.readiness.blockers)
    assert p.budget.event_count == 5 * 10 * 2
    assert p.budget.total_frame_count == sum(b.physical_frame_count for b in p.blocks)
    assert p.budget.memory_bytes > p.budget.storage_bytes > 0  # cumulative native arrays + processing overhead


def test_us_planner_schema_roundtrip_and_independent_mutable_serialization():
    a, b = default_settings(), default_settings("dual")
    data = a.to_dict()
    data["response"]["hf2_order"] = 7
    assert a.response.hf2_order == b.response.hf2_order == 1
    assert StroboscopySettings.from_dict(json.loads(json.dumps(a.to_dict()))) == a
    with pytest.raises(ValueError, match="Unknown"):
        StroboscopySettings.from_dict({"legacy_phase_scan": True})


def test_us_planner_shared_cryogenic_identity_keeps_separate_software_branch():
    s = replace(default_settings(), condition_profile_id="77K-Mb-G-F")
    p = build_plan(s)
    assert p.condition_profile["architecture_id"] == "ARC-77-MB-NSUS"
    assert p.condition_profile["branch"] == "microsecond"
    assert s.instance_id == "microsecond_stroboscopy:single"
    assert any("temperature" in text for text in p.readiness.blockers)
    assert any("unrecovered" in text for text in p.readiness.warnings)


def test_us_planner_irf_grid_nonuniform_and_literature_optional_only():
    grid = information_delay_grid(response_width_us=20, recovery_limit_us=10000)
    assert grid[0] < 0 and grid[-1] == pytest.approx(10000)
    assert len(set(round(b-a, 6) for a, b in zip(grid, grid[1:]))) > 3
    example = literature_coverage_example_us()
    assert example["approximate_component_times_us"] == [185., 1000.]
    assert "fixed fit" in example["label"]
    assert 185. not in default_settings().delays_us


def test_us_planner_local_spectral_window_includes_endpoint_without_nominal_peak_shortcut():
    points = local_spectral_window(1940, 1941, .3)
    assert points[-1].wavenumber_cm1 == 1941
    assert len(points) == 5
    with pytest.raises(ValueError):
        local_spectral_window(1941, 1940, .1)


@pytest.mark.parametrize("delay", [-100., 0., 25.123456, 1000.])
def test_us_planner_complete_deterministic_signed_delay_schedule(delay):
    s = replace(compact(), delays_us=(-100., 0., 25.123456, 1000.))
    p = compile_timing(s, [delay])
    assert p.to_dict() == compile_timing(s, [delay]).to_dict()
    assert p.physical_frame_count == 3 and p.pump_event_count == 1
    assert p.train_count == p.frame_repeat_count == 0
    assert all(not c["enabled"] for i in (0, 2) for c in p.frames[i]["channels"].values())
    assert p.frames[1]["channels"]["A"]["enabled"] and p.frames[1]["channels"]["B"]["enabled"]
    assert not p.frames[1]["channels"]["C"]["enabled"] and not p.frames[1]["channels"]["D"]["enabled"]
    event = p.events[0]
    assert event.selected_delay_us == pytest.approx(delay, abs=0.000006)
    assert event.q_command_time_s - event.pump_command_time_s == pytest.approx(s.timing.fire_to_q_us * 1e-6)
    assert event.aperture_stop_s - event.aperture_start_s == pytest.approx(s.response.integration_aperture_s)
    assert "optical" in p.timing_origin


def test_us_planner_no_implicit_multi_event_continuous_split():
    with pytest.raises(ValueError, match="one declared event"):
        compile_timing(compact(), [-100, 25])


def test_us_planner_pump_blocked_schedule_suppresses_first_pulse_as_well_as_trains():
    p = compile_timing(compact(), [25], pumped=False)
    assert p.pump_event_count == 0
    assert all(not c["enabled"] for f in p.frames for c in f["channels"].values())
    assert all(p.t6601_recipe["channels"][c]["enabled"] for c in "ABC")


def test_us_planner_quantizes_frame_upward_and_frequency_to_supported_quantum():
    s = compact()
    s = replace(s, timing=replace(s.timing, probe_rate_hz=1_000_000.007, event_interval_s=.0100000001))
    p = compile_timing(s, [25])
    assert p.input_frequency_hz == 1_000_000
    assert p.frame_period_s >= s.timing.event_interval_s
    assert p.predivider == 10001


@pytest.mark.parametrize("changes,match", [
    ({"probe_width_ns": 400}, "duty"),
    ({"probe_rate_hz": 17_000_000}, "16 MHz"),
    ({"timing_quantum_ns": .001}, "10 ps"),
    ({"event_interval_s": .0001}, "does not fit"),
    ({"event_interval_s": 5000}, "predivider"),
    ({"frame_capacity": 2}, "three frames"),
])
def test_us_planner_impossible_requests_are_not_science_warnings(changes, match):
    s = compact()
    p = build_plan(replace(s, timing=replace(s.timing, **changes)))
    assert any(match in text for text in p.readiness.errors)


def test_us_planner_subresponse_steps_warn_but_do_not_make_hardware_impossible():
    s = replace(compact(), delays_us=(-100., 0., .001, 25., 1000.))
    p = build_plan(s)
    assert not p.errors
    assert any("do not improve" in text for text in p.warnings)


def test_us_planner_dual_independent_response_and_aggregate_stream_cap():
    s = compact("dual")
    p = build_plan(replace(s, response=replace(s.response, reference_time_constant_s=50e-6, reference_latency_s=20e-6)))
    assert not p.errors
    assert any("filters/latencies differ" in text for text in p.warnings)
    bad = build_plan(replace(s, response=replace(s.response, sample_rate_sps=250000, reference_rate_sps=250000, timing_rate_sps=250000)))
    assert any("700" in text for text in bad.errors)


def test_us_planner_complete_single_blank_precedes_review_and_all_pumped_work():
    s = compact()
    p = build_plan(s)
    kinds = [b.kind for b in p.blocks]
    assert kinds.count("blank_control") == len(s.delays_us) * s.averages
    assert max(i for i, k in enumerate(kinds) if k == "blank_control") < kinds.index("preliminary")
    assert kinds.index("preliminary") < kinds.index("pumped")
    dual = build_plan(replace(s, mode="dual"))
    assert not any(b.kind in ("sequential_blank", "blank_control") for b in dual.blocks)
    assert dual.budget.sequential_blank_s == 0


def test_us_planner_finishes_wavelength_and_counterbalances_delay_order():
    s = default_settings()
    p = build_plan(s)
    pumped = [b for b in p.blocks if b.kind == "pumped"]
    assert [b.wavelength_index for b in pumped] == sorted(b.wavelength_index for b in pumped)
    first = [b.delay_us for b in pumped if b.wavelength_index == 0 and b.average_index == 0]
    second = [b.delay_us for b in pumped if b.wavelength_index == 0 and b.average_index == 1]
    assert first == list(reversed(second))


def test_us_planner_pump_limit_is_on_actual_events_not_disabled_frame_frequency():
    s = compact()
    assert s.timing.event_interval_s == .01
    assert not build_plan(s).errors  # 100 Hz frames, one event + separate 1s recovery
    p = build_plan(replace(s, reset=replace(s.reset, recovery_wait_s=0, verification_duration_s=.001)))
    assert any("10 Hz" in text for text in p.errors)


def test_us_planner_full_duration_budget_and_storage_include_controls_and_native_timing():
    p = build_plan(compact("dual"))
    b = p.budget
    values = b.to_dict()
    assert b.wall_clock_s == pytest.approx(sum(value for key, value in values.items()
                                               if key.endswith("_s") and key != "wall_clock_s"))
    for field in ("upload_s", "preliminary_s", "baseline_s", "pump_blocked_s", "recovery_s",
                  "reset_verification_s", "retrieval_s", "restoration_s", "saving_s", "analysis_s"):
        assert values[field] > 0
    assert b.storage_bytes > sum(block.capture_duration_s for block in p.blocks) * p.settings.response.sample_rate_sps * 56
    assert b.open_ended_actions


def test_us_planner_storage_limit_is_explicit_no_silent_reduction_of_averages():
    s = compact()
    p = build_plan(replace(s, budget=replace(s.budget, maximum_storage_bytes=100)))
    assert any("storage" in text for text in p.errors)
    assert p.settings.averages == s.averages


def test_us_planner_qualified_manual_overrides_are_retained_and_outside_envelope_flagged():
    s = compact()
    data = qualified(s).to_dict()
    data["operating_settings"] = {"response": {"hf2_order": 4, "integration_aperture_s": 30e-6}}
    result = apply_qualified_recommendations(s, data, override_fields=("response.hf2_order",))
    assert result.response.hf2_order == s.response.hf2_order
    assert result.response.integration_aperture_s == 30e-6
    data["valid_ranges"] = {"response": {"hf2_time_constant_s": [10e-6, 1e-3]}}
    p = build_plan(s, qualification=data)
    assert p.settings.response.hf2_time_constant_s == s.response.hf2_time_constant_s
    assert any("outside" in text for text in p.readiness.blockers)


def test_us_planner_wrong_profile_and_actual_readback_never_look_promoted():
    s = compact()
    q = qualified(s).to_dict()
    q["condition_profile_ids"] = ["77K-Mb-G-F"]
    caps = InstalledCapabilities.from_dict({"verified": True, "actual_values": {"response.sample_rate_sps": 115131.5789}})
    p = build_plan(s, caps, q)
    assert any("condition" in text for text in p.readiness.blockers)
    item = p.values["response.sample_rate_sps"]
    assert item["requested"] == 115000 and item["actual"] == 115131.5789


def readback_menu(mode="single"):
    profile = {"orders": [1, 2, 4], "timeconstants_by_order": {1: [8e-6, 10e-6], 2: [10e-6], 4: [20e-6]},
               "rates_sps": [57565.78947368421, 115131.57894736842, 230263.15789473685]}
    result = {"verified": True, "timing_rate_sps": 230263.15789473685,
              "enabled_streams": [0, 2, 3] if mode == "dual" else [0, 2]}
    return {**result, "sample": profile, "reference": deepcopy(profile)} if mode == "dual" else {**result, **profile}


def test_us_planner_connected_menu_requires_actual_rate_and_auto_choice_is_explicit():
    s, cap = compact("dual"), readback_menu("dual")
    p = build_plan(s, cap)
    assert any("rate" in text and "readback" in text for text in p.readiness.blockers)
    assert p.settings.response.sample_rate_sps == 115000  # no silent quantization
    chosen = select_supported_response(s, cap)
    assert chosen.response.sample_rate_sps == 115131.57894736842
    assert chosen.response.reference_rate_sps == 115131.57894736842
    assert chosen.response.timing_rate_sps == 230263.15789473685
    selected_plan = build_plan(chosen, cap)
    assert selected_plan.values["response.sample_rate_sps"]["requested"] == 115000
    assert selected_plan.values["response.sample_rate_sps"]["selected"] == 115131.57894736842
    assert StroboscopySettings.from_dict(chosen.to_dict()) == chosen
    assert not any(issue.code.startswith(("manual_rate", "timing_rate", "capability_menu")) for issue in selected_plan.readiness.issues)
    manual = select_supported_response(s, cap, preserve_fields=("sample_rate_sps",))
    assert manual.response.sample_rate_sps == 115000


def test_us_planner_connected_rejected_filter_order_wrong_demod_and_extra_streams():
    s, cap = compact(), readback_menu()
    p = build_plan(replace(s, response=replace(s.response, hf2_order=8)), cap)
    assert any("not accepted" in text for text in p.errors)
    p = build_plan(replace(s, response=replace(s.response, sample_demodulator=1)), cap)
    assert any("sample demodulator 0" in text for text in p.errors)
    cap["enabled_streams"] = [0, 1, 2]
    assert any("active streams" in text for text in build_plan(s, cap).readiness.blockers)


def test_us_planner_native_readback_capability_translation_preserves_missing_enables():
    s = compact()
    nodes = {}
    for i in range(6):
        for name, value in (("enable", int(i in (0, 2))), ("order", 1), ("timeconstant", 8e-6),
                            ("rate", s.response.timing_rate_sps if i == 2 else s.response.sample_rate_sps)):
            nodes[f"/devtest/demods/{i}/{name}"] = {"value": value}
    readbacks = {"hf2li_device": "devtest", "hf2li": {"nodes": nodes}}
    caps = capabilities_from_readbacks(s, readbacks)
    p = build_plan(s, caps)
    assert not any(issue.code.startswith(("installed_readbacks", "capability_menu", "manual_rate", "timing_rate")) for issue in p.readiness.issues)
    del nodes["/devtest/demods/5/enable"]
    assert not capabilities_from_readbacks(s, readbacks).data["verified"]


@pytest.mark.parametrize("role,field,value,code", [
    ("sample", "record_id", "WRONG-DARK", "dark_record_sample"),
    ("reference", "record_id", "", "dark_record_reference"),
    ("sample", "offset", math.nan, "dark_offset_sample"),
    ("reference", "offset", None, "dark_offset_reference"),
    ("reference", "standard_error", -1, "dark_uncertainty_reference"),
    ("sample", "standard_error", math.inf, "dark_uncertainty_sample"),
])
def test_us_planner_dark_qualification_matches_each_selected_detector(role, field, value, code):
    s = compact("dual")
    profile = qualified(s).to_dict()
    profile["normalization"]["dark_offsets"][role][field] = value
    p = build_plan(s, qualification=profile)
    assert code in [issue.code for issue in p.readiness.issues if issue.severity == "blocker"]
    assert not p.errors  # Acquisition readiness failure, not impossible hardware.


def test_us_planner_dark_roles_required_only_when_requested():
    s = compact("dual")
    profile = qualified(s).to_dict()
    del profile["normalization"]["dark_offsets"]["reference"]
    assert "dark_record_reference" in [issue.code for issue in build_plan(s, qualification=profile).readiness.issues]
    no_dark = replace(s, controls=replace(s.controls, require_dark=False))
    assert not any(issue.code.startswith(("dark_record_", "dark_offset_", "dark_uncertainty_"))
                   for issue in build_plan(no_dark, qualification=profile).readiness.issues)


class LocalFrameTransport(T660Service):
    """Real pending-field implementation, injected no-I/O line transport."""
    def __init__(self):
        super().__init__("t660_2", {})
        self.values, self.pending, self.stored, self.lines = {}, {}, [], []

    def command(self, command, *, expect_response=True, delay_s=.04):
        if ";" in command:
            return ";".join(self.command(part) for part in command.split(";"))
        command = command.lstrip(":")
        self.lines.append(command)
        if command == "FEATure:FRAMe?":
            return "1"
        if command.endswith("?"):
            return self.values.get(command[:-1], "0")
        key, _, value = command.partition(" ")
        self.values[key] = value
        if key.startswith("TIME:QUEue") or key.startswith("CHANnel:QUEue"):
            pending_key = key + (value.split(",")[0] if "," in value else "")
            self.pending[pending_key] = value
        if key == "TFRame:STORe":
            self.stored.append(deepcopy(self.pending))
        return "OK"


def test_us_planner_actual_pending_field_upload_acknowledges_all_frames_without_arming():
    p, service, progress = compile_timing(compact(), [25]), LocalFrameTransport(), []
    receipt = p.upload(service, progress=lambda done, total: progress.append((done, total)))
    assert progress == [(0, 3), (1, 3), (2, 3), (3, 3)]
    assert receipt["acknowledged"]["physical_frame_count"] == 3
    assert all(len(f) == 20 for f in service.stored)
    assert service.stored[1]["CHANnel:QUEue:MODeA"] == "A, ON"
    assert service.stored[2]["CHANnel:QUEue:MODeA"] == "A, OFF"
    assert "TFRame:STArt" not in service.lines and "START" not in service.lines
    # OFF -> pumped -> OFF needs only changed fields after complete first frame.
    assert sum("TIME:QUEue" in line or "CHANnel:QUEue" in line for line in service.lines) < 60


def test_us_planner_upload_cancellation_preserves_inhibited_partial_table():
    p, service = compile_timing(compact(), [25]), LocalFrameTransport()
    def stop():
        if service.stored:
            raise InterruptedError("operator cancellation")
    with pytest.raises(InterruptedError):
        p.upload(service, cancel_check=stop)
    assert len(service.stored) == 1
    assert not any("TFRame:STArt" == line for line in service.lines)


def test_us_planner_upload_receipt_mismatch_blocks_arming():
    class BadReceipt:
        def preload_frame_table(self, *_args, **_kwargs):
            return {"physical_frame_count": 2, "readback": {}}
    with pytest.raises(ValueError, match="acknowledged"):
        compile_timing(compact(), [25]).upload(BadReceipt())
