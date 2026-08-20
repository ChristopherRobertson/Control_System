"""Report whether all connection-derived WM-01 entry fields are resolved."""

from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.devices.coherent_wavemaster_service import (
    CoherentWaveMasterService,
)


def main() -> int:
    meter = CoherentWaveMasterService.from_config()
    gaps = meter.phase_entry_gaps()
    print(
        json.dumps(
            {
                "phase_id": "WM-01",
                "status": "BLOCKED" if gaps else "READY_FOR_PHASE_APPROVAL",
                "value_required_fields": gaps,
                "note": (
                    "Resolving fields does not authorize WM-01, power application, "
                    "laser emission, or phase advancement."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 2 if gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
