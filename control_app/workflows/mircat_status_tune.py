"""Day 5 MIRcat safe status/tune workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO
import json

from control_app.config_loader import ConfigInventory, load_config_inventory
from control_app.devices.mircat_service import MircatError, MircatService
from control_app.manifest import new_manifest, write_manifest


DEFAULT_LAMBDA_MID_CM1 = 1858.0


class MircatStatusTuneError(RuntimeError):
    """Raised when the MIRcat status/tune workflow cannot pass."""


@dataclass(frozen=True)
class MircatTuneRequest:
    """Operator-controlled MIRcat tune request."""

    wavenumber_cm1: float = DEFAULT_LAMBDA_MID_CM1
    qcl: int = 1
    tec_timeout_s: float = 120.0
    tune_timeout_s: float = 120.0
    poll_interval_s: float = 0.5
    approved_laser_safety_condition: bool = False
    allow_emission_on: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable request dictionary."""

        return asdict(self)


class MircatStatusTune:
    """Run a lab-approved safe-state MIRcat status and tune sequence."""

    def __init__(
        self,
        *,
        operator: str,
        inventory: ConfigInventory | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(config_path, write_files=False)
        self.config_path = Path(self.inventory.config_path)

    def run(
        self,
        *,
        request: MircatTuneRequest,
        run_dir: str | Path,
        command_log: TextIO | None = None,
        command_log_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute the real safe tune workflow and write Day 5 evidence files."""

        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        request_path = run_path / "mircat_tune_request.json"
        state_path = run_path / "mircat_state_readback.json"
        actual_path = run_path / "mircat_actual_wavelength_record.json"
        summary_path = run_path / "mircat_status_tune_summary.json"

        request_path.write_text(
            json.dumps(request.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        device_config = self.inventory.devices.get("mircat")
        if not isinstance(device_config, dict):
            raise MircatStatusTuneError("mircat missing from hardware configuration")

        service = MircatService(
            device_config,
            command_log=command_log,
        )
        initialized = False
        cleanup_errors: list[str] = []
        actual_record: list[dict[str, Any]] = []

        try:
            service.initialize()
            initialized = True
            initial_state = service.read_state().to_dict()

            if not initial_state.get("connected"):
                raise MircatStatusTuneError("MIRcat SDK did not report a laser connection")
            if not initial_state.get("interlock_set"):
                raise MircatStatusTuneError("MIRcat interlock is not set")
            if not initial_state.get("key_switch_set"):
                raise MircatStatusTuneError("MIRcat key switch is not set")

            service.arm()
            if not service.wait_for_tecs_ready(
                timeout_s=request.tec_timeout_s,
                poll_interval_s=request.poll_interval_s,
            ):
                raise MircatStatusTuneError(
                    f"MIRcat TECs were not ready within {request.tec_timeout_s:g} s"
                )

            service.tune_to_wavenumber(request.wavenumber_cm1, qcl=request.qcl)
            if not service.wait_for_tuned(
                timeout_s=request.tune_timeout_s,
                poll_interval_s=request.poll_interval_s,
            ):
                raise MircatStatusTuneError(
                    f"MIRcat did not report tuned within {request.tune_timeout_s:g} s"
                )

            actual = service.get_actual_wavelength()
            actual_record.append(
                {
                    "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "setpoint_cm1": request.wavenumber_cm1,
                    "preferred_qcl": request.qcl,
                    "actual": actual,
                }
            )
            if request.allow_emission_on:
                service.turn_emission_on(
                    approved_laser_safety_condition=request.approved_laser_safety_condition
                )
            else:
                service.turn_emission_off()

            cancel_status = service.cancel_manual_tune()
            service.turn_emission_off()
            service.disarm()
            final_state = service.read_state().to_dict()
            if final_state.get("emission_on"):
                raise MircatStatusTuneError("MIRcat emission remained on after cleanup")
            if final_state.get("armed"):
                raise MircatStatusTuneError("MIRcat remained armed after cleanup")

            actual_path.write_text(
                json.dumps(actual_record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(
                    {"initial_state": initial_state, "final_state": final_state},
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            summary = {
                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "operator": self.operator,
                "request": request.to_dict(),
                "status": "PASS",
                "manual_tune_cancel_return_code": cancel_status,
                "actual_wavelength_record": str(actual_path),
                "state_readback": str(state_path),
                "cleanup_errors": cleanup_errors,
            }
            summary_path.write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest = new_manifest(
                operator=self.operator,
                inventory=self.inventory,
                mircat_setpoint={
                    "value": request.wavenumber_cm1,
                    "units": "cm^-1",
                    "qcl": request.qcl,
                },
                mircat_actual_wavelength=actual,
                raw_data_paths=[str(actual_path)],
                command_log_paths=command_log_paths or [],
                device_readback_paths=[str(request_path), str(state_path), str(summary_path)],
                blocker_status={"blocked": False, "blockers": [], "next_actions": []},
            )
            write_manifest(run_path / "run_manifest.json", manifest)
            return summary
        except (MircatError, MircatStatusTuneError) as exc:
            raise MircatStatusTuneError(str(exc)) from exc
        finally:
            if initialized:
                try:
                    service.turn_emission_off()
                except Exception as exc:  # noqa: BLE001 - cleanup must record all failures
                    cleanup_errors.append(f"emission_off cleanup failed: {exc}")
                try:
                    service.disarm()
                except Exception as exc:  # noqa: BLE001
                    cleanup_errors.append(f"disarm cleanup failed: {exc}")
                try:
                    service.deinitialize()
                except Exception as exc:  # noqa: BLE001
                    cleanup_errors.append(f"deinitialize cleanup failed: {exc}")


def connection_owner_next_actions(errors: list[str]) -> list[str]:
    """Return concrete next actions for common MIRcat ownership/runtime blockers."""

    joined = " ".join(errors).lower()
    actions: list[str] = []
    if any(token in joined for token in ["initialization", "no_system", "comm_error", "own"]):
        actions.extend(
            [
                "Close the manufacturer MIRcat UI before running this check; only one process can own the MIRcat connection.",
                "Verify no stale Python or LabVIEW process still has the MIRcat SDK session open.",
            ]
        )
    actions.extend(
        [
            "Verify the MIRcat is powered, connected to Windows, and visible to the Daylight SDK.",
            "Verify the interlock and key switch are set before arming.",
            "Re-run with native Windows Python so the MIRcat SDK DLL can be loaded.",
        ]
    )
    return actions
