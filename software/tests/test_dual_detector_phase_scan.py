"""Dual HF2 settings are checked with configuration-only fakes and retained records."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from control_app.workflows.dual_detector_phase_scan import (
    DualDetectorPhaseScanSettings, DualHF2Capabilities, ENABLED_STREAMS,
    SOURCE_RECORD, build_dual_detector_phase_scan_plan, detector_assignments,
    select_dual_hf2_settings,
)
from control_app.workflows.regular_phase_scan import HF2Capabilities, build_regular_phase_scan_plan
from control_app.workflows.phase_scan import PhaseScanPlanError
from test_regular_phase_scan import ConfigurationOnlyHF2


def test_dual_plan_reuses_signed_regular_geometry_and_preserves_fire_timing():
    dual = build_dual_detector_phase_scan_plan()
    single = build_regular_phase_scan_plan()
    assert dual.total_scans == single.total_scans == 322
    assert dual.capture_window == single.capture_window
    assert dual.first_phase_delay_us == single.first_phase_delay_us
    assert dual.last_phase_delay_us == single.last_phase_delay_us
    assert dual.frame_period_s == single.frame_period_s
    assert dual.to_dict()["sequence"]["fire_to_qswitch_us"] == 250
    assert dual.to_dict()["method"] == "dual_detector_phase_scan"
    assert "blank" not in dual.to_dict()["sequence"]
    assert "delta_absorbance" in dual.to_dict()["normalization"]
    assert dual.capacity["estimated_retained_bytes"] > single.capacity["estimated_retained_bytes"]


def test_assignments_match_maintained_wiring_and_retained_actual_nodes():
    root = Path(__file__).resolve().parents[2]
    path = root / SOURCE_RECORD
    if not path.exists():
        pytest.skip("Retained optional local readback is unavailable")
    nodes = json.loads(path.read_text())["nodes"]
    selection = build_dual_detector_phase_scan_plan().hf2_selection
    roles = detector_assignments()
    assert roles["sample"]["input"] == 0
    assert roles["reference"]["input"] == 1
    assert roles["reference"]["demodulator"] == 3
    for role in ("sample", "reference"):
        channel = selection[role]
        base = f"/dev18500/demods/{channel['demodulator']}"
        for key, node in (("adcselect", "adcselect"), ("rate_sps", "rate"),
                          ("timeconstant_s", "timeconstant"), ("order", "order")):
            assert channel[key] == nodes[f"{base}/{node}"]["value"]
    assert not selection["capability_verified"]


def test_supported_values_and_overrides_remain_detector_specific():
    original = DualHF2Capabilities()
    ref = replace(original.reference, orders=(2,), timeconstants_by_order={2: (8.1e-6, 30e-6)},
                  rates_sps=(14391.447368421053, 57565.78947368421))
    caps = replace(original, reference=ref)
    requested = {"sample_order": 4, "reference_order": 2,
                 "reference_timeconstant_s": 8.1e-6, "reference_rate_sps": ref.rates_sps[1]}
    selection = select_dual_hf2_settings(DualDetectorPhaseScanSettings(), caps, requested)
    assert selection["reference"]["order"] == 2
    assert selection["sample"]["order"] == 4
    assert selection["requested"] == requested
    assert selection["reference"]["rate_sps"] == ref.rates_sps[1]
    assert selection["differential_filter_delay_s"] == pytest.approx(4*4.999538607626059e-5-2*8.1e-6)
    assert selection["temporal_resolution_s"] > max(selection[r]["temporal_resolution_s"] for r in ("sample", "reference"))
    with pytest.raises(PhaseScanPlanError, match="Reference.*unsupported"):
        select_dual_hf2_settings(DualDetectorPhaseScanSettings(), caps, {"reference_rate_sps": 28782.894736842107})


def test_capabilities_roundtrip_keeps_both_profiles_and_rejects_single():
    caps = DualHF2Capabilities()
    copy = DualHF2Capabilities.from_dict(json.loads(json.dumps(caps.to_dict())))
    assert copy.sample == caps.sample
    assert copy.reference == caps.reference
    assert copy.enabled_streams == ENABLED_STREAMS
    with pytest.raises(PhaseScanPlanError, match="separate sample and reference"):
        DualHF2Capabilities.from_dict(HF2Capabilities().to_dict())
    with pytest.raises(PhaseScanPlanError, match="single-detector"):
        build_dual_detector_phase_scan_plan(build_regular_phase_scan_plan().settings)


@pytest.mark.parametrize("change", [
    {"enabled_streams": (0, 2)},
    {"reference": HF2Capabilities()},
    {"reference": replace(HF2Capabilities(), enabled_streams=ENABLED_STREAMS, device_id="other")},
    {"reference": replace(HF2Capabilities(), enabled_streams=ENABLED_STREAMS, timing_rate_sps=1)},
])
def test_missing_or_mismatched_three_stream_profile_is_rejected(change):
    with pytest.raises(PhaseScanPlanError):
        build_dual_detector_phase_scan_plan(capabilities=replace(DualHF2Capabilities(), **change))


@pytest.mark.parametrize("override", [{"reference_rate_sps": 460526.3157894737},
                                      {"reference_order": True}, {"reference_timeconstant_s": -1},
                                      {"reference_rate_sps": float("nan")}])
def test_invalid_reference_overrides_raise_actionable_plan_error(override):
    with pytest.raises(PhaseScanPlanError, match="Reference|reference|Filter|Time"):
        build_dual_detector_phase_scan_plan(overrides=override)


def test_all_three_stream_transfer_limits_and_advisory_memory():
    caps = DualHF2Capabilities()
    fastest = replace(caps.sample, rates_sps=(230263.15789473685,))
    caps = replace(caps, sample=fastest, reference=fastest, max_retained_bytes=1)
    plan = build_dual_detector_phase_scan_plan(capabilities=caps)
    assert plan.hf2_selection["combined_rate_sps"] < 700000
    assert plan.capacity["warning"].startswith("Warning:")
    assert plan.capacity["retention_budget_is_advisory"]
    assert plan.capacity["estimated_retained_bytes"] == (
        plan.capacity["estimated_uncompressed_payload_bytes"] + plan.capacity["metadata_allowance_bytes"])
    with pytest.raises(PhaseScanPlanError, match="capacity"):
        build_dual_detector_phase_scan_plan(capabilities=replace(caps,
            reference=replace(fastest, rates_sps=(460526.3157894737,))))


@pytest.mark.parametrize("changes", [{"scan_speed_cm1_s": 0}, {"pump_repetition_rate_hz": 3},
                                     {"phase_delay_us": 0}, {"post_pump_ms": -1}])
def test_shared_parameter_validation_runs_before_dual_filter_resolution(changes):
    with pytest.raises(PhaseScanPlanError):
        build_dual_detector_phase_scan_plan(replace(DualDetectorPhaseScanSettings(), **changes))


class ThreeStreamHF2(ConfigurationOnlyHF2):
    """Reference readbacks differ only while all three actual streams are enabled."""
    def _set_node(self, method, path, value):
        active = tuple(i for i in range(6) if self.nodes[f"/fake/demods/{i}/enable"])
        if path.endswith("/3/rate") and value != 1000 and active == ENABLED_STREAMS:
            ladder = [115131.57894736843 / 2**i for i in range(15)]
            value = min(ladder, key=lambda x: abs(x-value))
        super()._set_node(method, path, value)


def test_connected_discovery_probes_both_actual_streams_and_restores_every_node():
    service = ThreeStreamHF2()
    original = service.nodes.copy()
    found = service.discover_dual_phase_scan_capabilities()
    assert service.nodes == original
    assert found["enabled_streams"] == ENABLED_STREAMS
    assert found["sample"]["enabled_streams"] == found["reference"]["enabled_streams"] == ENABLED_STREAMS
    assert max(found["sample"]["rates_sps"]) == pytest.approx(230263.15789473685)
    assert max(found["reference"]["rates_sps"]) == pytest.approx(115131.57894736843)
    caps = DualHF2Capabilities.from_dict(found)
    assert caps.reference.rates_sps != caps.sample.rates_sps
    assert caps.verified
    assert any(row["node"].endswith("/3/order") for row in caps.readback_records)
    assert all("/demods/" in node for node, _ in service.writes)


def test_dual_discovery_restores_after_reference_failure():
    class BrokenReference(ThreeStreamHF2):
        def _set_node(self, method, path, value):
            if path.endswith("/3/rate") and value == 230000:
                raise RuntimeError("reference transfer unavailable")
            return super()._set_node(method, path, value)
    service = BrokenReference()
    original = service.nodes.copy()
    with pytest.raises(RuntimeError, match="reference transfer unavailable"):
        service.discover_dual_phase_scan_capabilities()
    assert service.nodes == original
