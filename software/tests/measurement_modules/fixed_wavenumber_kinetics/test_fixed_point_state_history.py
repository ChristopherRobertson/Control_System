"""Optional historical metadata cannot gate normal raw acquisition."""
import json

import pytest

from control_app.measurement_host import ContextFactory
from control_app.measurement_modules.fixed_wavenumber_kinetics.planner import build_plan
from control_app.measurement_modules.fixed_wavenumber_kinetics.runner import Runner
from control_app.measurement_modules.fixed_wavenumber_kinetics.settings import Settings, Position
from control_app.measurement_modules.fixed_wavenumber_kinetics.state_history import StateHistory


@pytest.mark.parametrize("mode", ["single", "dual"])
@pytest.mark.parametrize("condition", ["", "cryo_hrp_co", "rt_hrp_co"])
def test_fixed_point_history_metadata_never_gates_raw_acquisition(tmp_path, mode, condition):
    history = tmp_path/"legacy-state-history.jsonl"
    history.write_text('{"incomplete historical record', encoding="utf-8")
    settings = Settings(mode=mode, condition_profile=condition, positions=(Position(1930.),),
        pre_observation_s=.2, post_observation_s=3., chunk_duration_s=.2,
        technical_repetitions=2, event_budget=2)
    context = ContextFactory(configuration_provider=lambda: {}, save_root_provider=lambda: tmp_path).for_experiment("fixed_wavenumber_kinetics").for_mode(mode)
    plan = build_plan(settings)
    assert plan.ready
    for _ in range(2):
        operation = context.begin_operation(settings=settings.to_dict(), hardware=False)
        result = Runner(context, history_path=history).run(operation, plan)
        assert result["status"] == "complete", result.get("error")
        assert len(result["events"]) == 2
        assert all(event["commanded_event_number"] == index+1 for index,event in enumerate(result["events"]))
        assert "state_history_check" not in result
    assert history.read_text(encoding="utf-8") == '{"incomplete historical record'


def test_fixed_point_legacy_journal_can_be_loaded_without_authority(tmp_path):
    path = tmp_path/"old.jsonl"
    row = {"record_kind": "pump_dispatch_intent", "run_id": "historical-run",
        "state": {"sample_id": "a", "preparation_id": "b", "cell_id": "c", "condition_id": "d"}}
    path.write_text(json.dumps(row)+"\n", encoding="utf-8")
    result = StateHistory(path).check(row["state"])
    assert result["previous_dispatches"] == [row]
    assert result["advisory_only"] and result["acquisition_blocked"] is False
