"""Independent review and compatibility state; no widget or hardware imports."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from collections.abc import Mapping
import math


def compatibility_conflicts(saved, requested, prefix=""):
    """Compare explicit fields and report the specific mismatch, without digests."""
    if isinstance(saved, Mapping) and isinstance(requested, Mapping):
        conflicts = []
        for key in sorted(set(saved) | set(requested)):
            name = f"{prefix}.{key}" if prefix else str(key)
            if key not in saved or key not in requested:
                conflicts.append(f"{name}: missing from {'saved record' if key not in saved else 'current plan'}")
            else:
                conflicts.extend(compatibility_conflicts(saved[key], requested[key], name))
        return conflicts
    if isinstance(saved, (tuple, list)) and isinstance(requested, (tuple, list)):
        if len(saved) != len(requested):
            return [f"{prefix}: record has {len(saved)} entries; plan has {len(requested)}"]
        return [item for i, (a, b) in enumerate(zip(saved, requested))
                for item in compatibility_conflicts(a, b, f"{prefix}[{i}]")]
    if isinstance(saved, float) and isinstance(requested, float):
        equal = math.isfinite(saved) and math.isfinite(requested) and saved == requested
    else:
        equal = saved == requested
    return [] if equal else [f"{prefix}: recorded {saved!r}; current {requested!r}"]


def scientific_contract(settings, configuration, calibration_records=(), sample_records=()):
    return deepcopy({
        "experiment_id": "repeated_rapid_scan", "schema_version": 1,
        "settings": settings, "configuration": configuration,
        "calibration_records": calibration_records, "sample_records": sample_records,
    })


@dataclass
class ReviewSession:
    """Every tab constructs its own state; incompatible records remain inspectable."""
    mode: str
    blank: object = None
    background: object = None
    preliminary: object = None
    result: object = None
    calibration_records: list = field(default_factory=list)
    sample_records: list = field(default_factory=list)
    instrument_changes: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def clear(self):
        self.blank = self.background = self.preliminary = self.result = None
        self.errors.clear()

    def configuration_contract(self, configuration):
        # Host events can carry a newer readback than the persisted configuration.
        return {"configuration": deepcopy(configuration),
                "observed_changes": deepcopy(self.instrument_changes)}

    def check(self, record, contract):
        if not isinstance(record, Mapping) or "review_contract" not in record:
            self.errors = ["Record lacks the repeated rapid-scan review compatibility contract"]
        else:
            self.errors = compatibility_conflicts(record["review_contract"], contract)
        return tuple(self.errors)
