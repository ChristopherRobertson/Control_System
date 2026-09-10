"""Per-tab data reuse compatibility; optional metadata never authorizes a run."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from collections.abc import Mapping
import math

_ACQUISITION_FIELDS = (
    "scan_start_cm1", "scan_stop_cm1", "measured_scan_period_s", "scan_speed_cm1_s",
    "sample_rate_hz", "sample_demodulator", "sample_input_range_v", "sample_filter_order",
    "sample_filter_timeconstant_s", "probe_frequency_hz", "probe_pulse_width_s",
    "mircat_pulse_rate_hz", "mircat_pulse_width_ns", "mircat_current_ma",
)
_REFERENCE_FIELDS = ("reference_rate_hz", "reference_demodulator", "reference_input_range_v",
                     "reference_filter_order", "reference_filter_timeconstant_s")
_UNASSIGNED = (None, "", "unassigned", "unknown")


def compatibility_conflicts(saved, requested, prefix=""):
    """Compare actual recording requirements, with explicit mismatch messages."""
    if isinstance(saved, Mapping) and isinstance(requested, Mapping):
        conflicts = []
        for key in sorted(set(saved) | set(requested)):
            name = f"{prefix}.{key}" if prefix else str(key)
            if key not in saved or key not in requested:
                conflicts.append(f"{name}: missing from {'saved record' if key not in saved else 'current plan'}")
            elif key == "sample_identity":
                for label in set(saved[key]) & set(requested[key]):
                    if saved[key][label] not in _UNASSIGNED and requested[key][label] not in _UNASSIGNED:
                        conflicts.extend(compatibility_conflicts(saved[key][label], requested[key][label], f"{name}.{label}"))
            elif key == "directions":
                missing = set(requested[key])-set(saved[key])
                if missing:
                    conflicts.append(f"{name}: saved record lacks {', '.join(sorted(missing))}")
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


def operational_contract(settings, configuration=None, calibration_records=(), sample_records=()):
    """Only settings affecting a reusable native baseline belong in this key.

    Phase count/movie duration, descriptive condition/temperature fields, notes,
    calibration promotion and approval remain provenance, not operational gates.
    """
    settings = dict(settings)
    mode = settings.get("mode", "single")
    names = _ACQUISITION_FIELDS + (_REFERENCE_FIELDS if mode == "dual" else ())
    condition = settings.get("condition", {})
    changes = (configuration or {}).get("observed_changes", {})
    relevant_changes = {key:deepcopy(value) for key,value in changes.items()
        if any(token in key.lower() for token in ("scan", "wavelength", "demod", "rate", "range", "timeconstant",
                                                "filter", "reference", "probe", "input", "oscillator", "path_balance"))}
    return {"experiment_id":"repeated_rapid_scan", "schema_version":1,"mode":mode,
            "acquisition":{key:deepcopy(settings[key]) for key in names if key in settings and settings[key] is not None},
            "directions":tuple(settings.get("directions", ())),
            "sample_identity":{key:condition.get(key) for key in ("sample_id","preparation_id","cell_id","position_id")
                               if condition.get(key) not in _UNASSIGNED},
            "instrument_changes":relevant_changes}


def record_contract(record):
    """Migrate legacy full-state records as data, without any approval state."""
    direct = record.get("compatibility_contract")
    if isinstance(direct, Mapping) and direct:
        return direct
    legacy = record.get("review_contract")
    if isinstance(legacy, Mapping) and "settings" in legacy:
        return operational_contract(legacy["settings"],legacy.get("configuration", {}))
    settings = record.get("operation", {}).get("settings")
    if not settings:
        settings = record.get("plan", {}).get("settings")
    return operational_contract(settings) if settings else None


@dataclass
class MeasurementSession:
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
        return {"observed_changes":deepcopy(self.instrument_changes)}

    def check(self, record, contract):
        if not isinstance(record, Mapping):
            self.errors = ["No native baseline record is selected"]
        else:
            saved = record_contract(record)
            self.errors = (["Saved record lacks acquisition settings needed for baseline reuse"] if saved is None
                           else compatibility_conflicts(saved,contract))
        return tuple(self.errors)
