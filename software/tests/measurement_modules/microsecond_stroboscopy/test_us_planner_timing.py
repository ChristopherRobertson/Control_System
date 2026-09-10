"""Installed-device planning with independent Auto/manual controls, no evidence gates."""
from copy import deepcopy
from dataclasses import replace
import json
import math

import pytest

from control_app.devices.t660_service import T660Service
from control_app.measurement_modules.microsecond_stroboscopy.planner import (
    InstalledCapabilities, Qualification, acquisition_signature, build_plan,
    capabilities_from_readbacks, resolve_settings,
)
from control_app.measurement_modules.microsecond_stroboscopy.settings import (
    StroboscopySettings, default_settings, information_delay_grid,
    literature_coverage_example_us, local_spectral_window,
)
from control_app.measurement_modules.microsecond_stroboscopy.timing import compile_timing


def compact(mode="single"):
    s = default_settings(mode)
    return replace(s, spectral_points=s.spectral_points[:1], delays_us=(-100., 25., 250., 1000.), averages=2)


def manual(settings, section, **values):
    return replace(settings, **{section: replace(getattr(settings, section), **values)},
        manual_overrides=tuple(sorted(set(settings.manual_overrides) | {f"{section}.{name}" for name in values})))


def readback_menu(mode="single"):
    profile = {"orders": [1, 2, 4], "timeconstants_by_order": {1: [8e-6, 10e-6], 2: [10e-6], 4: [20e-6]},
               "rates_sps": [57565.78947368421, 115131.57894736842, 230263.15789473685]}
    result = {"verified": True, "timing_rate_sps": 230263.15789473685,
              "enabled_streams": [0, 2, 3] if mode == "dual" else [0, 2]}
    return {**result, "sample": profile, "reference": deepcopy(profile)} if mode == "dual" else {**result, **profile}


@pytest.mark.parametrize("mode", ["single", "dual"])
def test_us_planner_default_is_real_hardware_with_no_scientific_evidence_gate(mode):
    s = default_settings(mode)
    p = build_plan(s)
    assert s.execution_mode == "hardware"
    assert s.condition_profile_id == "" and not s.identity.sample_id
    assert p.readiness.valid and p.hardware_ready and not p.readiness.blockers
    assert any("readbacks" in text for text in p.warnings)
    assert not p.settings.response.qualified
    assert p.budget.event_count == 5*10*2
    assert p.budget.total_frame_count == sum(b.physical_frame_count for b in p.blocks)
    assert p.budget.memory_bytes > p.budget.storage_bytes > 0
    assert p.budget.preliminary_s == p.budget.sequential_blank_s == 0


def test_us_planner_schema_roundtrip_and_independent_serialized_settings():
    s, other = default_settings(), default_settings("dual")
    data = s.to_dict()
    data["response"]["hf2_order"] = 7
    assert s.response.hf2_order == other.response.hf2_order == 1
    assert StroboscopySettings.from_dict(json.loads(json.dumps(s.to_dict()))) == s
    with pytest.raises(ValueError, match="Unknown"):
        StroboscopySettings.from_dict({"legacy_phase_scan": True})


@pytest.mark.parametrize("condition", ["", "77K-Mb-G-F", "RT-Mb-R-K", "arbitrary old condition"])
def test_us_planner_historical_condition_temperature_evidence_never_changes_raw_plan(condition):
    s = compact()
    old = replace(s, condition_profile_id=condition,
        identity=replace(s.identity, measured_temperature_k=77., temperature_record_id="old temperature"),
        reset=replace(s.reset, equivalent_state_verified=False, equivalence_record_id=""),
        controls=replace(s.controls, require_dark=True, dark_record_id="", artifact_record_ids=()),
        promoted_bundle_ids=(), calibration_ids=())
    p = build_plan(old, qualification={"experiment_id":"other", "condition_profile_ids":["other"]})
    assert p.hardware_ready and not p.readiness.blockers
    assert acquisition_signature(old) == acquisition_signature(s)
    assert p.settings.identity.temperature_record_id == "old temperature"
    assert not any(b.requires_reset_equivalence for b in p.blocks)


def test_us_planner_irf_grid_nonuniform_and_literature_not_fit_defaults():
    grid = information_delay_grid(response_width_us=20, recovery_limit_us=10000)
    assert grid[0] < 0 and grid[-1] == pytest.approx(10000)
    assert len(set(round(b-a, 6) for a,b in zip(grid,grid[1:]))) > 3
    assert literature_coverage_example_us()["approximate_component_times_us"] == [185., 1000.]
    assert 185. not in default_settings().delays_us


def test_us_planner_local_spectral_window_keeps_full_axis():
    points = local_spectral_window(1940,1941,.3)
    assert points[-1].wavenumber_cm1 == 1941 and len(points) == 5
    with pytest.raises(ValueError): local_spectral_window(1941,1940,.1)


@pytest.mark.parametrize("delay", [-100., 0., 25.123456, 1000.])
def test_us_planner_complete_deterministic_signed_delay_schedule(delay):
    s = replace(compact(),delays_us=(-100.,0.,25.123456,1000.))
    p = compile_timing(s,[delay])
    assert p.to_dict() == compile_timing(s,[delay]).to_dict()
    assert p.physical_frame_count == 3 and p.pump_event_count == 1
    assert p.train_count == p.frame_repeat_count == 0
    assert all(not c["enabled"] for i in (0,2) for c in p.frames[i]["channels"].values())
    assert p.frames[1]["channels"]["A"]["enabled"] and p.frames[1]["channels"]["B"]["enabled"]
    assert not p.frames[1]["channels"]["C"]["enabled"] and not p.frames[1]["channels"]["D"]["enabled"]
    e=p.events[0]
    assert e.selected_delay_us == pytest.approx(delay,abs=.000006)
    assert e.q_command_time_s-e.pump_command_time_s == pytest.approx(s.timing.fire_to_q_us*1e-6)
    assert e.aperture_stop_s-e.aperture_start_s == pytest.approx(s.response.integration_aperture_s)


def test_us_planner_no_implicit_multi_event_split():
    with pytest.raises(ValueError,match="one declared event"):
        compile_timing(compact(),[-100,25])


def test_us_planner_pump_off_disables_first_pulse_not_only_train_count():
    p=compile_timing(compact(),[25],pumped=False)
    assert p.pump_event_count == 0
    assert all(not c["enabled"] for f in p.frames for c in f["channels"].values())
    assert all(p.t6601_recipe["channels"][c]["enabled"] for c in "ABC")


def test_us_planner_quantizes_frame_upward_and_frequency_to_supported_quantum():
    s=manual(compact(),"timing",probe_rate_hz=1_000_000.007,event_interval_s=.0100000001)
    p=compile_timing(s,[25])
    assert p.input_frequency_hz == 1_000_000 and p.predivider == 10001
    assert p.frame_period_s >= s.timing.event_interval_s


@pytest.mark.parametrize("changes,match", [
    ({"probe_width_ns":400},"duty"), ({"probe_rate_hz":17_000_000},"16 MHz"),
    ({"timing_quantum_ns":.001},"10 ps"), ({"event_interval_s":.0001},"does not fit"),
    ({"event_interval_s":5000},"predivider"), ({"frame_capacity":2},"three frames"),
])
def test_us_planner_impossible_manual_requests_remain_errors(changes,match):
    p=build_plan(manual(compact(),"timing",**changes))
    assert any(match in message for message in p.errors)


def test_us_planner_subresponse_delay_steps_warn_without_gate():
    p=build_plan(replace(compact(),delays_us=(-100.,0.,.001,25.,1000.)))
    assert not p.errors and any("do not improve" in message for message in p.warnings)


def test_us_planner_auto_uses_actual_independent_menus_and_preserves_manual_field():
    s=manual(compact("dual"),"response",hf2_order=4,reference_time_constant_s=10e-6)
    p=build_plan(s,readback_menu("dual"))
    assert not p.errors
    assert p.settings.response.hf2_order == 4 and p.settings.response.hf2_time_constant_s == 20e-6
    assert p.settings.response.reference_time_constant_s == 10e-6
    assert p.settings.response.sample_rate_sps in readback_menu("dual")["sample"]["rates_sps"]
    assert p.settings.response.timing_rate_sps == 230263.15789473685
    assert p.settings.manual_overrides == s.manual_overrides
    assert any("filters/latencies differ" in message for message in p.warnings)


def test_us_planner_return_one_advanced_control_to_auto_keeps_other_override():
    cap=readback_menu("dual")
    s=manual(compact("dual"),"response",hf2_order=4,reference_order=4)
    s=replace(s,manual_overrides=("response.reference_order",))
    resolved=resolve_settings(s,cap)
    assert resolved.response.hf2_order == 1 and resolved.response.reference_order == 4
    timer=manual(s,"timing",probe_width_ns=150,probe_rate_hz=2e6)
    timer=replace(timer,manual_overrides=tuple(p for p in timer.manual_overrides if p!="timing.probe_width_ns"))
    resolved=resolve_settings(timer,cap)
    assert resolved.timing.probe_width_ns == 100 and resolved.timing.probe_rate_hz == 2e6


def test_us_planner_actual_manual_invalid_filter_and_throughput_are_not_approved_away():
    s=compact("dual")
    p=build_plan(manual(s,"response",hf2_order=8),readback_menu("dual"))
    assert any("not accepted" in message for message in p.errors)
    p=build_plan(manual(s,"response",sample_rate_sps=250000,reference_rate_sps=250000,timing_rate_sps=250000))
    assert any("700" in message for message in p.errors)
    p=build_plan(manual(s,"response",sample_demodulator=1))
    assert any("sample demodulator 0" in message for message in p.errors)


def test_us_planner_actual_probe_readbacks_drive_auto_and_manual_is_independent():
    cap=readback_menu()
    cap["timing_settings"]={"probe_rate_hz":500000.,"probe_width_ns":200.}
    p=build_plan(manual(compact(),"timing",probe_width_ns=100.),cap)
    assert p.settings.timing.probe_rate_hz == 500000 and p.settings.timing.probe_width_ns == 100


def test_us_planner_optional_blank_preliminary_have_separate_complete_budgets():
    s=compact()
    run,blank,pre=(build_plan(s,kind=kind) for kind in ("run","blank","preliminary"))
    assert not any(b.kind in ("blank_control","preliminary") for b in run.blocks)
    assert blank.budget.blank_control_event_count == len(s.delays_us)*s.averages
    assert blank.budget.event_count == pre.budget.event_count == 0
    assert pre.budget.preliminary_s > 0 and run.budget.preliminary_s == 0
    assert build_plan(compact("dual"),kind="blank").errors


def test_us_planner_finishes_wavelength_and_counterbalances_delay_order():
    p=build_plan(default_settings())
    pumped=[b for b in p.blocks if b.kind=="pumped"]
    assert [b.wavelength_index for b in pumped] == sorted(b.wavelength_index for b in pumped)
    first=[b.delay_us for b in pumped if b.wavelength_index==0 and b.average_index==0]
    second=[b.delay_us for b in pumped if b.wavelength_index==0 and b.average_index==1]
    assert first == list(reversed(second))


def test_us_planner_event_spacing_is_physical_minimum_not_fabricated_reset_approval():
    p=build_plan(replace(compact(),event_spacing_s=.5))
    assert not p.errors and p.settings.reset.recovery_wait_s < .5
    assert not p.settings.reset.equivalent_state_verified
    assert build_plan(replace(compact(),event_spacing_s=.05)).errors
    bad=manual(compact(),"reset",recovery_wait_s=0,verification_duration_s=.001)
    assert any("10 Hz" in message for message in build_plan(bad).errors)


def test_us_planner_estimated_protocol_and_native_overhead_cannot_shorten_wait_or_approve_cadence():
    s=compact()
    slower=replace(s,budget=replace(s.budget,acquisition_guard_s_per_block=5,
        native_protocol_seconds_per_block=6,capture_protocol_seconds_per_block=7,
        upload_fixed_seconds_per_block=8))
    assert resolve_settings(s).reset.recovery_wait_s == resolve_settings(slower).reset.recovery_wait_s
    bad=manual(slower,"reset",recovery_wait_s=0,verification_duration_s=.001)
    assert any("10 Hz" in message for message in build_plan(bad).errors)


def test_us_planner_duration_storage_include_all_run_controls_and_final_retention():
    p=build_plan(compact("dual")); b=p.budget; values=b.to_dict()
    assert b.wall_clock_s == pytest.approx(sum(v for k,v in values.items() if k.endswith("_s") and k!="wall_clock_s"))
    for name in ("upload_s","protocol_s","baseline_s","pump_blocked_s","recovery_s","reset_verification_s","post_run_verification_s","retrieval_s","restoration_s","saving_s","analysis_s"):
        assert values[name]>0
    assert b.preliminary_s == b.sequential_blank_s == 0
    assert b.storage_bytes > sum(block.capture_duration_s for block in p.blocks)*p.settings.response.sample_rate_sps*56
    assert not b.open_ended_actions


def test_us_planner_storage_limit_never_silently_reduces_averages():
    s=compact(); p=build_plan(replace(s,budget=replace(s.budget,maximum_storage_bytes=100)))
    assert any("storage" in message for message in p.errors)
    assert p.settings.averages == s.averages


def test_us_planner_signatures_ignore_historical_metadata_but_retain_physical_settings():
    s=compact()
    changed=replace(s,condition_profile_id="77K-Mb-G-F",identity=replace(s.identity,sample_id="old",measured_temperature_k=77.),
        promoted_bundle_ids=("old",),calibration_ids=("old",),value_selections=(),
        budget=replace(s.budget,maximum_memory_bytes=10**10),
        spectral_points=tuple(replace(p,label="renamed",role="band") for p in s.spectral_points))
    assert acquisition_signature(s)==acquisition_signature(changed)
    assert acquisition_signature(s)!=acquisition_signature(manual(s,"response",hf2_order=4))
    assert acquisition_signature(acquisition_signature(s))==acquisition_signature(s)


def test_us_planner_stationary_control_signature_can_reuse_changed_grid_and_averages():
    s=compact()
    changed=replace(s,averages=99,delays_us=(-100,10,20,3000),event_spacing_s=3,
        response=replace(s.response,integration_aperture_s=50e-6),
        timing=replace(s.timing,event_interval_s=.03,fire_to_q_us=250))
    for kind in ("blank","preliminary"):
        assert acquisition_signature(s,kind=kind)==acquisition_signature(changed,kind=kind)
        assert acquisition_signature(acquisition_signature(s),kind=kind)==acquisition_signature(s,kind=kind)
    assert acquisition_signature(s)!=acquisition_signature(changed)


def test_us_planner_connected_readbacks_do_not_fabricate_missing_nodes():
    s=compact(); nodes={}
    for i in range(6):
        for name,value in (("enable",int(i in (0,2))),("order",1),("timeconstant",8e-6),
                           ("rate",s.response.timing_rate_sps if i==2 else s.response.sample_rate_sps)):
            nodes[f"/devtest/demods/{i}/{name}"]={"value":value}
    rb={"hf2li_device":"devtest","hf2li":{"nodes":nodes}}
    caps=capabilities_from_readbacks(s,rb)
    assert caps.data["verified"]
    assert not build_plan(s,caps).errors
    del nodes["/devtest/demods/5/enable"]
    assert not capabilities_from_readbacks(s,rb).data["verified"]


def test_us_planner_connected_replan_preserves_configured_auto_timing_without_fabricating_missing_fields():
    s=compact(); nodes={}
    for i in range(6):
        for name,value in (("enable",int(i in (0,2))),("order",1),("timeconstant",8e-6),
                           ("rate",s.response.timing_rate_sps if i==2 else s.response.sample_rate_sps)):
            nodes[f"/devtest/demods/{i}/{name}"]={"value":value}
    rb={"hf2li_device":"devtest","hf2li":{"nodes":nodes},
        "actual_settings":{"timing":{"probe_rate_hz":500000.,"probe_width_ns":200.}}}
    caps=capabilities_from_readbacks(s,rb)
    p=build_plan(s,caps)
    assert p.settings.timing.probe_rate_hz == 500000. and p.settings.timing.probe_width_ns == 200.
    assert "timing.fire_to_q_us" not in caps.data["actual_values"]
    assert p.values["timing.probe_rate_hz"]["actual"] == 500000.
    assert "observed electrical" in p.observable and "calibrated optical arrival" not in p.observable


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


def test_us_planner_budget_covers_actual_t660_line_delays_and_subscribed_native_overhead():
    class CountRoundTrips(LocalFrameTransport):
        def __init__(self):
            super().__init__()
            self.depth=self.round_trips=0
        def command(self,command,**kwargs):
            if not self.depth:
                self.round_trips+=1
            self.depth+=1
            try:
                return super().command(command,**kwargs)
            finally:
                self.depth-=1
    s=compact(); p=build_plan(s); driver=CountRoundTrips()
    event=next(b.timing_program for b in p.blocks if b.physical_frame_count)
    event.upload(driver)
    assert driver.round_trips == 33+event.physical_frame_count
    frame_blocks=sum(bool(b.physical_frame_count) for b in p.blocks)
    assert p.budget.upload_s >= frame_blocks*driver.round_trips*.04
    observations=sum(not b.physical_frame_count for b in p.blocks)+sum(b.reset_verification_s>0 for b in p.blocks)
    assert p.budget.protocol_s == pytest.approx(frame_blocks*.4+observations*.08)
    native_duration=sum(b.capture_duration_s+b.reset_verification_s for b in p.blocks)+frame_blocks*(.04+.26)
    rate=p.settings.response.sample_rate_sps+p.settings.response.timing_rate_sps
    assert native_duration*rate <= p.budget.native_sample_count <= math.ceil(native_duration*rate)+1


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
