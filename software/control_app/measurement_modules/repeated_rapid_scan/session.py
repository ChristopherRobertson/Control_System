"""Per-tab data reuse compatibility; optional metadata never authorizes a run."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from collections.abc import Mapping
from decimal import Decimal
import math

UI_OVERRIDE_FIELDS = ("scan_speed_cm1_s", "sample_rate_hz", "sample_filter_order",
                      "sample_filter_timeconstant_s", "probe_frequency_hz", "mircat_pulse_width_ns")
UI_REFERENCE_OVERRIDE_FIELDS = ("reference_rate_hz", "reference_filter_order", "reference_filter_timeconstant_s")
ANALYSIS_WINDOW_FIELDS = ("band_windows_cm1", "offband_windows_cm1")


def normalize_ui_settings(value, mode=None):
    """Migrate UI requests; removed engineering controls become provenance only.

    This is intentionally separate from native run loading and the backend
    settings model. Existing intent preserves independent Auto choices. A legacy
    settings document without intent preserves its accessible explicit values.
    """
    from .settings import AcquisitionIntent, RepeatedRapidScanSettings
    from .planner import resolve_intent_settings

    source = deepcopy(value.to_dict() if hasattr(value,"to_dict") else dict(value))
    source_mode = source.get("mode",mode or "single")
    if mode is not None and source_mode != mode:
        raise ValueError("Settings belong to another detector mode")
    defaults = RepeatedRapidScanSettings(mode=source_mode).to_dict()
    visible = UI_OVERRIDE_FIELDS + (UI_REFERENCE_OVERRIDE_FIELDS if source_mode == "dual" else ())
    allowed = visible + ANALYSIS_WINDOW_FIELDS
    metadata = ("condition","execution","schema_version","experiment_id","value_source",
                "calibration_ids","instrument_state_id")
    data = deepcopy(defaults)
    for key in metadata + allowed:
        if key in source:
            data[key] = deepcopy(source[key])
    history = deepcopy(source.get("historical_ui_settings",{}))
    if not isinstance(history,Mapping):
        raise ValueError("historical_ui_settings must be a mapping")
    history = dict(history)
    previous_migration = history.get("ui_controls_version") == 2
    removed = deepcopy(history.get("removed_settings",{}))
    excluded = set(metadata + allowed + ("mode","acquisition_intent","manual_overrides","historical_ui_settings"))
    derived = {"measured_scan_period_s","phase_offsets_s","post_scans","scan_start_cm1","scan_stop_cm1","repeats"}
    def plain(item):
        if isinstance(item,Mapping): return {key:plain(part) for key,part in item.items()}
        if isinstance(item,(tuple,list)): return [plain(part) for part in item]
        return item
    for key, item in source.items():
        if key in excluded or (previous_migration and key in derived):
            continue
        if key not in defaults or plain(item) != plain(defaults[key]):
            removed.setdefault(key,deepcopy(item))
    raw_manual = source.get("manual_overrides",{})
    if not isinstance(raw_manual,Mapping):
        raise ValueError("manual_overrides must be a mapping")
    removed_manual = deepcopy(history.get("removed_manual_overrides",{}))
    for key,item in raw_manual.items():
        if key not in allowed:
            removed_manual.setdefault(key,deepcopy(item))
    manual = {key:deepcopy(item) for key,item in raw_manual.items() if key in allowed and item is not None}
    intent = source.get("acquisition_intent")
    if not intent:
        condition = source.get("condition",defaults["condition"])
        period = source.get("measured_scan_period_s",defaults["measured_scan_period_s"])
        scans = source.get("post_scans",defaults["post_scans"])
        intent = AcquisitionIntent(sample_name=condition.get("sample_id","Sample"),
            spectral_min_cm1=source.get("scan_start_cm1",defaults["scan_start_cm1"]),
            spectral_max_cm1=source.get("scan_stop_cm1",defaults["scan_stop_cm1"]),
            observation_duration_s=float(Decimal(str(period))*Decimal(str(scans))),
            phase_count=len(source.get("phase_offsets_s",defaults["phase_offsets_s"])),
            repeats=source.get("repeats",defaults["repeats"])).to_dict()
        for key in allowed:
            if key in source and key not in raw_manual and source[key] is not None:
                manual[key] = deepcopy(source[key])
    history["ui_controls_version"] = 2
    if removed: history["removed_settings"] = removed
    if removed_manual: history["removed_manual_overrides"] = removed_manual
    data["historical_ui_settings"] = history
    data["manual_overrides"] = manual
    data["acquisition_intent"] = deepcopy(intent)
    return resolve_intent_settings(intent,mode=source_mode,base_settings=data,overrides=manual).to_dict()

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
    return {"experiment_id":"repeated_rapid_scan", "schema_version":1,"mode":mode,"mircat_qcl":1,
            "acquisition":{key:deepcopy(settings[key]) for key in names if key in settings and settings[key] is not None},
            "directions":tuple(settings.get("directions", ())),
            "sample_identity":{key:condition.get(key) for key in ("sample_id","preparation_id","cell_id","position_id")
                               if condition.get(key) not in _UNASSIGNED},
            "instrument_changes":relevant_changes}


def record_contract(record):
    """Migrate legacy full-state records as data, without any approval state."""
    observed_qcl = record.get("readbacks", {}).get("mircat_pulse", {}).get("qcl")
    direct = record.get("compatibility_contract")
    if isinstance(direct, Mapping) and direct:
        result = deepcopy(direct)
        if observed_qcl is not None:
            result["mircat_qcl"] = observed_qcl
        return result
    legacy = record.get("review_contract")
    if isinstance(legacy, Mapping) and "settings" in legacy:
        result = operational_contract(legacy["settings"],legacy.get("configuration", {}))
    else:
        settings = record.get("operation", {}).get("settings")
        if not settings:
            settings = record.get("plan", {}).get("settings")
        if not settings:
            return None
        result = operational_contract(settings)
    # Old records do not acquire a QCL1 identity just because the current engine
    # is fixed to QCL1. Preserve observed source identity or reacquire support.
    result.pop("mircat_qcl",None)
    if observed_qcl is not None:
        result["mircat_qcl"] = observed_qcl
    return result


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
