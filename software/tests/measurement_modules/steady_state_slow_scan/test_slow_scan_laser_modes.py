"""Mode selection uses genuine acquisition code with injected device services."""
from dataclasses import replace

import pytest

from control_app.measurement_host.presentation import StartSnapshot
from control_app.measurement_modules.steady_state_slow_scan.settings import SlowScanSettings
from control_app.measurement_modules.steady_state_slow_scan.planner import build_plan, simulation_inputs
from control_app.measurement_modules.steady_state_slow_scan.runner import SlowScanRunner, compatibility
from control_app.measurement_modules.steady_state_slow_scan.persistence import load_run
from test_slow_scan_installed import configured, worker, QCLService, HFService


@pytest.mark.parametrize("laser_mode,current", [("pulsed", 1000.), ("cw", 750.)])
def test_mode_defaults_and_plan_roundtrip(laser_mode, current):
    settings = SlowScanSettings(laser_mode=laser_mode)
    assert (settings.upper_cm1, settings.lower_cm1, settings.requested_scan_speed_cm1_s, settings.replicates) == (2050., 1650., 40., 1)
    assert settings.current_ma == current
    assert settings.repetition_rate_hz == 2_000_000.
    assert settings.pulse_width_s == 150e-9
    assert SlowScanSettings.from_dict(settings.to_dict()) == settings
    plan = build_plan(settings, simulation_inputs(settings))
    assert plan.ready, (plan.errors, plan.readiness)
    assert plan.selected["mircat_pulse_trigger_mode"] == 1
    assert plan.selected["pulse_duty_fraction"] == (pytest.approx(.30) if laser_mode == "pulsed" else None)
    assert plan.selected["hf2li"]["sample"]["oscselect"] == 1
    assert plan.selected["hf2li"]["oscillators"] == [{"index": 1, "frequency_hz": 0.}]


def test_disabled_cw_pulse_fields_do_not_govern_acquisition():
    settings = SlowScanSettings(laser_mode="cw", repetition_rate_hz=9e6, pulse_width_s=10e-6)
    plan = build_plan(settings, simulation_inputs(settings))
    assert plan.ready, (plan.errors, plan.readiness)
    assert plan.selected["pulse_duty_fraction"] is None
    assert plan.inputs.scientific_profile["qcl_pulse_params"]["1"]["pulse_width_ns"] == 1000.
    pulsed = build_plan(replace(settings, laser_mode="pulsed"), simulation_inputs(settings))
    assert any("30% duty" in error for error in pulsed.errors)


def test_controls_are_not_compatible_across_laser_modes():
    settings = SlowScanSettings()
    pulsed = build_plan(settings, simulation_inputs(settings))
    cw = build_plan(replace(settings, laser_mode="cw"), simulation_inputs(settings))
    assert compatibility(pulsed) != compatibility(cw)
    assert compatibility(cw)["settings"]["laser_mode"] == "cw"


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("laser_mode,current", [("pulsed", 1000.), ("cw", 750.)])
def test_installed_mode_runs_one_descending_scan_and_restores_every_mode_setting(tmp_path, monkeypatch, mode, laser_mode, current):
    settings = SlowScanSettings(mode=mode, laser_mode=laser_mode, lower_cm1=1900., upper_cm1=1900.4)
    context, coordinator, operation, _, draft, _, services = configured(tmp_path, monkeypatch, mode, live=True, settings_override=settings)
    original = QCLService.start_emission
    def start(self):
        assert self.laser_mode == (1 if laser_mode == "pulsed" else 2)
        assert self.pulse["current_ma"] == current
        assert self.trigger["pulse_mode"] == 1
        assert self.trigger["process_trigger_mode"] == 2
        original(self)
    monkeypatch.setattr(QCLService, "start_emission", start)
    result = SlowScanRunner(context).run(StartSnapshot(operation, "measurement", draft, {}), worker())
    assert result["status"] == "completed" and result["restoration"]["safe_verified"]
    assert len(result["sweeps"]) == 1 and result["sweeps"][0].direction == "reverse"
    qcl, hf = services["mircat"], services["hf2li"]
    assert qcl.pulse_history[0]["current_ma"] == current
    if laser_mode == "pulsed":
        assert qcl.pulse_history[0]["pulse_rate_hz"] == 2_000_000.
        assert qcl.pulse_history[0]["pulse_width_ns"] == 150.
    assert (qcl.laser_mode, qcl.temperature_c, qcl.pulse["current_ma"]) == (1, 20., 500.)
    assert hf.get_oscillator_frequency(1) == 12345.
    assert "enable B" not in services["t660_1"].calls
    assert all(not state for unit in ("t660_1", "t660_2") for state in services[unit].channels.values())
    saved = load_run(result["path"], expected_mode=mode)
    assert saved["plan"]["settings"]["laser_mode"] == laser_mode
    assert saved["plan"]["selected"]["detector_dc_response_qualified"] is False
    assert coordinator.snapshot()["state"] == "free"


@pytest.mark.parametrize("fault", ["unsupported_cw", "cw_current_limit", "wrong_mode", "nonzero_detector_frequency"])
def test_mode_specific_faults_prevent_emission_and_release_after_restoration(tmp_path, monkeypatch, fault):
    settings = SlowScanSettings(mode="dual", laser_mode="cw", lower_cm1=1900., upper_cm1=1900.4)
    context, coordinator, operation, _, draft, _, services = configured(tmp_path, monkeypatch, live=True, settings_override=settings)
    if fault == "unsupported_cw": monkeypatch.setattr(QCLService, "is_cw_allowed", lambda self, qcl: False)
    elif fault == "cw_current_limit": monkeypatch.setattr(QCLService, "get_qcl_cw_current_limits", lambda self, qcl: (0., 700.))
    elif fault == "wrong_mode":
        original = QCLService.set_qcl_operating_params
        def set_mode(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            self.laser_mode = 1
            return result
        monkeypatch.setattr(QCLService, "set_qcl_operating_params", set_mode)
    else:
        original = HFService.apply_preset
        def apply(self, preset):
            original(self, preset)
            self.nodes[f"/{self.device_id}/oscs/1/freq"]["value"] = 1.
        monkeypatch.setattr(HFService, "apply_preset", apply)
    runner = SlowScanRunner(context)
    with pytest.raises((ValueError, RuntimeError)):
        runner.run(StartSnapshot(operation, "measurement", draft, {}), worker())
    assert "start_emission" not in services["mircat"].calls
    assert runner.last_result["restoration"]["safe_verified"]
    assert coordinator.snapshot()["state"] == "free"


def test_pulsed_run_restores_preexisting_cw_mode_current_and_temperature(tmp_path, monkeypatch):
    original = QCLService.__init__
    def initialize(self, guard):
        original(self, guard)
        self.laser_mode, self.temperature_c = 2, 24.
        self.pulse["current_ma"] = 750.
    monkeypatch.setattr(QCLService, "__init__", initialize)
    context, _, operation, _, draft, _, services = configured(tmp_path, monkeypatch, live=True)
    result = SlowScanRunner(context).run(StartSnapshot(operation, "measurement", draft, {}), worker())
    assert result["status"] == "completed" and result["restoration"]["safe_verified"]
    assert (services["mircat"].laser_mode, services["mircat"].temperature_c, services["mircat"].pulse["current_ma"]) == (2, 24., 750.)
