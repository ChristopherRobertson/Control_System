"""Report whether all connection-derived WaveMaster connection fields are resolved."""

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
    gaps = meter.connection_gaps()
    print(
        json.dumps(
            {
                "device": "wavemaster",
                "status": "BLOCKED" if gaps else "CONFIGURATION_READY",
                "value_required_fields": gaps,
                "note": (
                    "Resolving fields does not authorize WaveMaster connection, laser emission, "
                    "or scientific qualification."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 2 if gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
