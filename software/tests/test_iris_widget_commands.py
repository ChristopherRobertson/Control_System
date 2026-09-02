from types import SimpleNamespace

from control_app.config_loader import ConfigInventory
from control_app.ui.contracts import WorkflowCommand
from control_app.workflows.iris_widget_commands import IrisWidgetCommandHandler


IRIS_CONFIG = {
    "minimum_aperture_mm": 1.0,
    "maximum_aperture_mm": 11.5,
    "minimum_incremental_motion_mm": 0.01,
}


def _inventory(tmp_path):
    return ConfigInventory(
        config_path=str(tmp_path / "hardware_configuration.yaml"),
        schema_version=None,
        devices={"opo_iris": dict(IRIS_CONFIG)},
        t660_devices={},
        signal_map={},
        timing_routes={},
        mux_settings={},
        mux_routes={},
        picoscope_settings={},
        warnings=[],
    )


class FakeIrisService:
    def __init__(self, current, moves, **_kwargs):
        self.current = current
        self.moves = moves
        self.closed = False

    def connect(self):
        return None

    def identify(self):
        return SimpleNamespace(serial_number="11500020")

    def get_aperture_mm(self):
        return self.current

    def set_aperture_mm(self, target, *, require_open_side_approach=True):
        self.moves.append((target, require_open_side_approach))
        self.current = target
        return target

    def close(self):
        self.closed = True


def _handler(tmp_path, monkeypatch, *, current):
    from control_app.workflows import iris_widget_commands

    monkeypatch.setattr(
        iris_widget_commands, "output_log_root", lambda: tmp_path / "logs"
    )
    moves = []
    services = []

    def factory(**kwargs):
        service = FakeIrisService(current=current, moves=moves, **kwargs)
        services.append(service)
        return service

    handler = IrisWidgetCommandHandler(
        inventory=_inventory(tmp_path), service_factory=factory
    )
    return handler, moves, services


def test_refresh_returns_current_diameter_without_motion(tmp_path, monkeypatch):
    handler, moves, services = _handler(tmp_path, monkeypatch, current=6.25)
    result = handler(
        WorkflowCommand(device_key="opo_iris", command="opo_iris.refresh_status")
    )

    assert result.status == "complete"
    assert result.data["state"]["current_diameter_mm"] == 6.25
    assert result.data["state"]["identity"] == "ELL15 S/N 11500020"
    assert moves == []
    assert services[0].closed is True


def test_step_up_uses_open_side_approach_and_returns_readback(tmp_path, monkeypatch):
    handler, moves, _services = _handler(tmp_path, monkeypatch, current=5.0)
    result = handler(
        WorkflowCommand(
            device_key="opo_iris",
            command="opo_iris.step_up",
            parameters={"step_mm": 0.1},
        )
    )

    assert result.status == "complete"
    assert moves == [(11.5, False), (5.1, True)]
    assert result.data["state"]["current_diameter_mm"] == 5.1


def test_direct_entry_moves_down_and_rejects_out_of_range(tmp_path, monkeypatch):
    handler, moves, _services = _handler(tmp_path, monkeypatch, current=8.0)
    result = handler(
        WorkflowCommand(
            device_key="opo_iris",
            command="opo_iris.set_diameter",
            parameters={"diameter_mm": "6.75"},
        )
    )
    assert result.status == "complete"
    assert moves == [(6.75, True)]

    blocked = handler(
        WorkflowCommand(
            device_key="opo_iris",
            command="opo_iris.set_diameter",
            parameters={"diameter_mm": "12"},
        )
    )
    assert blocked.status == "blocked"
    assert "1.00-11.50 mm" in blocked.message
