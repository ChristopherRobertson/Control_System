"""Matched-sequence single-detector records for the regular Phase Scan tab.

Native records are immutable and contain the measured coordinates.  The saved
surface is an explicitly supported interpolation, never a baseline fit or a
smoothed spectrum.  No digest is used to accept a blank or load a run.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
import csv
import json

import numpy as np

from control_app.workflows.phase_scan import PhaseScanEvent
from control_app.workflows.phase_scan_data import (
    DETECTOR_INPUT, SINGLE_DETECTOR_MODE, Spectrum, _reconstruct_entries,
    absorbance, compatible_readbacks, interpolate_spectrum, load_native,
    save_native, utc_now, write_json,
)

SCHEMA_VERSION = "regular-phase-scan/1.0"
ANALYSIS_VERSION = "sequence-matched-absorbance/1.0"


def selected_hf2_configuration(selection):
    """Only acquisition values belong in compatibility, not capability history."""
    if not isinstance(selection, dict):
        return selection
    selected = selection.get("selected", selection)
    keys = ("order", "filter_order", "timeconstant_s", "time_constant_s",
            "sample_rate_sps", "rate_sps", "timing_rate_sps", "enabled_streams")
    return {key: deepcopy(selected[key]) for key in keys if key in selected}


def experiment_contract(plan):
    """Freeze cadence, complete phase sequence, trajectory, probe and HF2LI."""
    return {
        "settings": asdict(plan.settings), "scan_count": plan.total_scans,
        "frame_period_s": plan.frame_period_s,
        "first_phase_delay_us": plan.first_phase_delay_us,
        "last_phase_delay_us": plan.last_phase_delay_us,
        "fire_to_qswitch_us": 250.0,
        "hf2li_selected": selected_hf2_configuration(getattr(plan, "hf2_selection", {})),
        "detector_mode": SINGLE_DETECTOR_MODE, "detector_input": DETECTOR_INPUT,
    }


def compatibility_conflicts(left, right, prefix=""):
    """Return specific changed or absent fields, with readback rounding tolerance."""
    if isinstance(left, dict) and isinstance(right, dict):
        conflicts = []
        for key in sorted(set(left) | set(right)):
            name = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                conflicts.append(f"{name}: missing from {'saved blank' if key not in left else 'requested experiment'}")
            else:
                conflicts.extend(compatibility_conflicts(left[key], right[key], name))
        return conflicts
    if compatible_readbacks(left, right):
        return []
    return [f"{prefix}: blank {left!r}; requested {right!r}"]


def stable_device_configuration(readback):
    """Compare effective hardware settings while retaining all native readbacks."""
    fields = ("hf2li_device", "hf2li_detector_settings", "detector_mode", "detector_input",
              "qcls", "segments", "t660_1_probe_rate_hz_readback", "capture_window",
              "effective_pump_repetition_rate_hz", "fire_to_qswitch_us", "probe_recipe")
    result = {key: readback[key] for key in fields if key in readback}
    if "capture_window" in result:
        result["capture_window"] = {key: value for key, value in result["capture_window"].items() if key != "basis"}
    if "segments" in result:
        result["segments"] = [{key: segment[key] for key in ("qcl", "start_cm1", "stop_cm1")}
                              for segment in result["segments"]]
    resolution = readback.get("hf2li_resolution", {})
    if "actual" in resolution:
        result["hf2li_actual"] = resolution["actual"]
    return result


@dataclass
class BackgroundSequence:
    records: list[tuple[PhaseScanEvent, Spectrum]]
    native: dict
    settings: dict
    device_settings: dict
    path: Path

    @property
    def spectrum(self):
        """The first blank is for the preliminary spectrum only."""
        return self.records[0][1]


def validate_blank_sequence(records, plan=None):
    if not records:
        raise ValueError("Buffer blank has no scan records")
    if plan is not None and len(records) != plan.total_scans:
        raise ValueError(f"Buffer blank has {len(records)} scans; the sample sequence requires {plan.total_scans}")
    for position, (event, spectrum) in enumerate(records):
        spectrum.validate()
        if event.scan_index != position:
            raise ValueError(f"Buffer blank sequence position {position}: missing, duplicate or reordered scan")
        if (event.pump_enabled or spectrum.pump_time_s is not None or
                spectrum.metadata.get("record_role") != "buffer_blank"):
            raise ValueError(f"Buffer blank scan {position + 1} contains a pump event or is not a buffer blank")
        if spectrum.detector_mode != SINGLE_DETECTOR_MODE:
            raise ValueError("Regular phase scanning requires the HF2LI CH1 SIG IN + detector")
        if spectrum.metadata.get("wavenumber_basis") not in {"measured", "controller_markers"}:
            raise ValueError("A compatible blank requires measured wavelength or identified controller markers")
        if np.isfinite(spectrum.normalization_signal()).sum() < 2:
            raise ValueError(f"Buffer blank scan {position + 1} has fewer than two positive CH1 samples")
        if plan is not None:
            expected = plan.event_at(position)
            if (event.repetition, event.phase_index, event.phase_delay_us) != (
                    expected.repetition, expected.phase_index, expected.phase_delay_us):
                raise ValueError(f"Buffer blank scan {position + 1} has a different signed phase schedule")
    return records


def reconstruct_sequence(records, background, plan, *, cancel=None):
    """Pair sample i with blank i on measured wavelengths before taking log10."""
    validate_blank_sequence(background.records, plan)
    if [event for event, _ in records] != [plan.event_at(i) for i in range(plan.total_scans)]:
        raise ValueError("Sample sequence contains missing, duplicate, reordered or unexpected phase records")
    grid_blank = background.spectrum
    wn = np.sort(np.asarray(grid_blank.wavenumber_cm1))
    wn = wn[np.linspace(0, len(wn)-1, min(len(wn), 1024), dtype=int)]
    entries, pumped, per_scan = [], [], []
    for (event, spectrum), (blank_event, blank) in zip(records, background.records):
        if cancel:
            cancel()
        if event.scan_index != blank_event.scan_index:
            raise ValueError("Sample and blank scan sequence positions differ")
        values = interpolate_spectrum(spectrum, absorbance(spectrum, blank), wn)
        per_scan.append(values)
        if event.pump_enabled:
            if spectrum.pump_time_s is None or not np.isfinite(spectrum.pump_time_s):
                raise ValueError(f"Sample scan {event.scan_index + 1} has no observed electrical pump sync")
            if spectrum.metadata.get("pump_time_basis") not in {"measured", "electrical_sync", "aux_input"}:
                raise ValueError("Commanded phase delays cannot replace measured pump timestamps")
            age = interpolate_spectrum(spectrum,
                                       np.asarray(spectrum.sample_time_s) - spectrum.pump_time_s, wn)
            entries.append((event, age, values))
            pumped.append(spectrum)
        elif spectrum.pump_time_s is not None:
            raise ValueError("An unpumped sample baseline contains a pump event")
    # Use the baseline inside this continuous run for delta A; keep the earlier
    # preliminary review as a separately identified acquisition.
    baseline = per_scan[0]
    result = _reconstruct_entries(entries, pumped, grid_blank, plan, cancel=cancel)
    result.update({
        "schema_version": SCHEMA_VERSION, "analysis_version": ANALYSIS_VERSION,
        "normalization": "-log10(CH1 sample scan i / CH1 buffer blank scan i), measured wavelength matched",
        "background_matching": "sequence_position_and_measured_wavelength",
        "background_source": str(background.path),
        "delta_absorbance": result["absorbance"] - baseline[None, :],
        "baseline_absorbance": baseline, "per_scan_absorbance": np.asarray(per_scan),
        "scan_index": np.asarray([event.scan_index for event, _ in records], dtype=np.int64),
        "baseline_record_id": records[0][1].metadata.get("record_id"),
        "time_label": "Time relative to electrical pump sync (s)",
        "optical_pump_arrival_calibrated": False,
        "completion_status": "COMPLETE", "publication_eligible": False,
    })
    result["limitations"] = [text for text in result["limitations"]
        if "not pump-induced delta" not in text]
    result["limitations"].extend([
        "Delta absorbance subtracts the separate unpumped sample baseline acquired at sequence position zero.",
        "Matched sequential blanks assume reproducible sequence-dependent source/detector drift; nonrepeatable drift remains.",
        "Time zero is electrical pump sync; optical pump arrival has not been calibrated.",
    ])
    return validate_reconstruction(result)


class RegularScanStore:
    """One raw artifact after shutdown; incomplete and cleanup records survive."""
    def __init__(self, root, kind, plan):
        self.kind = kind
        self.id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + kind
        self.path = Path(root) / "Phase Scan" / datetime.now(UTC).strftime("%Y-%m-%d") / self.id
        self.path.mkdir(parents=True, exist_ok=False)
        self.compress_raw = True
        self.record_count = 0
        write_json(self.path / "run.json", {
            "schema_version": SCHEMA_VERSION, "run_id": self.id, "kind": kind,
            "created_utc": utc_now(), "plan": plan.to_dict(),
            "experiment_contract": experiment_contract(plan),
            "normalization": "CH1 sample scan i / measured-wavelength-matched CH1 buffer blank scan i",
            "native_source": "raw/acquisition.npz", "publication_eligible": False,
        })

    def save_block(self, records, *, native):
        path = self.path / "raw" / "acquisition.npz"
        save_native(path, {"schema_version": SCHEMA_VERSION,
                          "records": [{"event": asdict(e), **payload} for e, payload in records],
                          "native": native})
        self.record_count = len(records)
        with (self.path / "scan_index.jsonl").open("x", encoding="utf-8") as handle:
            for index, (event, _) in enumerate(records):
                handle.write(json.dumps({"event": asdict(event), "path": "raw/acquisition.npz",
                                         "record_index": index}) + "\n")
        return path

    def finish(self, status, **details):
        write_json(self.path / "result.json", {
            "status": status, "record_count": self.record_count, "finished_utc": utc_now(), **details})


def _record_directory(path):
    path = Path(path)
    if path.is_dir():
        return path
    if path.name == "acquisition.npz" and path.parent.name == "raw":
        return path.parent.parent
    if path.name in {"run.json", "result.json"}:
        return path.parent
    raise ValueError("Select a phase-scan run directory, run.json or raw/acquisition.npz")


def load_background_sequence(path, plan=None):
    directory = _record_directory(path)
    manifest = json.loads((directory / "run.json").read_text(encoding="utf-8-sig"))
    status = json.loads((directory / "result.json").read_text(encoding="utf-8-sig"))
    session = status.get("experiment_session") or {}
    session_closed = False
    if session.get("interstage_verified") and session.get("restoration_deferred"):
        close_path = directory / "experiment_session_close.json"
        if close_path.is_file():
            closed = json.loads(close_path.read_text(encoding="utf-8-sig"))
            session_closed = (closed.get("session_id") == session.get("session_id")
                              and closed.get("safe_verified") is True and not closed.get("error"))
    if (status.get("status") != "COMPLETE" or manifest.get("kind") != "background"
            or (status.get("safe_shutdown_and_restoration_verified") is False and not session_closed)
            or status.get("errors") or status.get("error") or status.get("cleanup_error")):
        raise ValueError("Select a completed buffer-blank acquisition with successful restoration")
    raw_path = directory / "raw" / "acquisition.npz"
    raw = load_native(raw_path)
    records = [(PhaseScanEvent(**r["event"]), Spectrum.from_dict(r["spectrum"])) for r in raw["records"]]
    if status.get("record_count") != len(records):
        raise ValueError("Saved blank result count differs from the retained sequence")
    if not manifest.get("experiment_contract"):
        return _import_retained_full_blank(directory, manifest, raw, records, plan)
    validate_blank_sequence(records, plan)
    contract = manifest["experiment_contract"]
    if contract.get("scan_count") != len(records):
        raise ValueError("Saved blank frozen scan count differs from its retained records")
    if plan is not None:
        conflicts = compatibility_conflicts(contract, experiment_contract(plan))
        if conflicts:
            raise ValueError("Saved blank is incompatible: " + "; ".join(conflicts))
    readback = raw["native"].get("device_settings", {})
    if not readback.get("hf2li_device") or not readback.get("hf2li_detector_settings"):
        raise ValueError("Saved blank has no verified HF2LI device/settings readback")
    return BackgroundSequence(records, raw["native"], contract, readback, raw_path)


def _import_retained_full_blank(directory, manifest, raw, records, requested_plan):
    """Read-only migration from complete retained phase experiments.

    Legacy request files said 0.3 s even for later 10 Hz sequences. Only the
    retained timing-table predivider, frame period and actual sequence can
    establish cadence. Missing evidence is a conflict, never filled by defaults.
    """
    from control_app.workflows.regular_phase_scan import (
        HF2Capabilities, RegularPhaseScanSettings, build_regular_phase_scan_plan,
    )
    from control_app.workflows.regular_phase_scan_acquisition import regular_event_timing

    try:
        preflight = json.loads((directory / "acquisition_preflight.json").read_text(encoding="utf-8-sig"))
        cleanup = json.loads((directory / "cleanup.json").read_text(encoding="utf-8-sig"))
        if cleanup.get("safe_state_verified") is not True or cleanup.get("errors"):
            raise ValueError("retained blank safe shutdown did not verify")
        blocks = raw["native"]["blocks"]
        if len(blocks) != 1 or raw["native"].get("partial_blocks"):
            raise ValueError("retained blank is not one completed continuous sequence")
        block = blocks[0]
        table = block["timing_table"]
        if table["acquisition_frame_count"] != len(records):
            raise ValueError("retained timing-table acquisition count differs from the saved scans")
        input_rate = float(table["input_frequency_hz"])
        period = int(table["readback"]["predivider"]) / input_rate
        if not compatible_readbacks(period, table["frame_period_s"]):
            raise ValueError("retained timing-table predivider and measured cadence disagree")
        settings_data = dict(manifest["plan"]["settings"])
        settings_data.update(pump_repetition_rate_hz=1/period, rest_period_s=period)
        settings = RegularPhaseScanSettings(**settings_data)
        if not compatible_readbacks(settings.probe_repetition_rate_hz, input_rate):
            raise ValueError("retained probe clock differs from the timing-table input clock")
        readback = deepcopy(raw["native"]["device_settings"])
        device = readback["hf2li_device"]
        nodes = readback["hf2li_detector_settings"]
        actual = {key: nodes[f"/{device}/demods/{index}/{node}"]["value"]
                  for key, index, node in (("order", 0, "order"), ("timeconstant_s", 0, "timeconstant"),
                                           ("rate_sps", 0, "rate"), ("timing_rate_sps", 2, "rate"))}
        enabled = tuple(index for index in range(6) if nodes[f"/{device}/demods/{index}/enable"]["value"])
        if enabled != (0, 2):
            raise ValueError("retained blank enabled streams differ from CH1 and DIO only")
        caps = HF2Capabilities(device_id=device, orders=(int(actual["order"]),),
            timeconstants_by_order={int(actual["order"]): (float(actual["timeconstant_s"]),)},
            rates_sps=(float(actual["rate_sps"]),), timing_rate_sps=float(actual["timing_rate_sps"]),
            enabled_streams=enabled, source=str(directory), verified=False)
        # Build exactly the recorded schedule using accepted actual values, then
        # compare it with the requested experiment if one was supplied.
        retained_plan = build_regular_phase_scan_plan(settings, capabilities=caps)
        validate_blank_sequence(records, retained_plan)
        contract = experiment_contract(retained_plan)
        if requested_plan is not None:
            conflicts = compatibility_conflicts(contract, experiment_contract(requested_plan))
            if conflicts:
                raise ValueError("; ".join(conflicts))
        frames = preflight["timing_recipe"]["frame_tables"]
        if len(frames) != 1 or len(frames[0]) != len(records):
            raise ValueError("retained signed frame schedule is incomplete or partitioned")
        for position, ((event, spectrum), frame) in enumerate(zip(records, frames[0])):
            expected_frame, _ = regular_event_timing(event)
            if frame != expected_frame:
                raise ValueError(f"retained Process Trigger/FIRE/Q-switch schedule differs at sequence position {position}")
            source = spectrum.metadata["acquisition_settings"]
            for key in ("probe_repetition_rate_hz", "probe_pulse_width_ns", "mircat_internal_repetition_rate_hz",
                        "mircat_internal_pulse_width_ns", "start_wavenumber_cm1", "stop_wavenumber_cm1", "scan_speed_cm1_s"):
                if not compatible_readbacks(source[key], getattr(settings, key)):
                    raise ValueError(f"retained scan {position + 1} acquisition setting {key} differs")
            for key in ("hf2li_device", "hf2li_detector_settings"):
                if not compatible_readbacks(spectrum.metadata[key], readback[key]):
                    raise ValueError(f"retained scan {position + 1} {key} readback differs")
            profile = spectrum.metadata["scan_profile"]
            if not (compatible_readbacks(profile["start_cm1"], settings.start_wavenumber_cm1)
                    and compatible_readbacks(profile["stop_cm1"], settings.stop_wavenumber_cm1)):
                raise ValueError(f"retained scan {position + 1} measured trajectory readbacks differ")
        if not block["mircat_trigger_checks"] or any(check["mismatch"] or
                check["readback"]["pulse_mode"] != 2 or check["readback"]["process_trigger_mode"] != 2
                for check in block["mircat_trigger_checks"]):
            raise ValueError("retained probe/process triggering did not verify as external")
        qcl = block["mircat_internal_settings_after_block_setup"]
        if (not compatible_readbacks(qcl["pulse_rate_hz"], settings.mircat_internal_repetition_rate_hz)
                or not compatible_readbacks(qcl["pulse_width_ns"], settings.mircat_internal_pulse_width_ns)
                or not compatible_readbacks(qcl["current_ma"], 750.)):
            raise ValueError("retained MIRcat internal pulse/current readbacks differ")
        readback.update({"hf2li_resolution": {"requested": {}, "selected": retained_plan.hf2_selection, "actual": actual},
            "detector_mode": SINGLE_DETECTOR_MODE, "detector_input": DETECTOR_INPUT,
            "qcls": preflight["qcls"], "segments": [block["scan_profile"]],
            "capture_window": preflight["capture_window"], "t660_1_probe_rate_hz_readback": input_rate,
            "effective_pump_repetition_rate_hz": 1/period, "fire_to_qswitch_us": 250.,
            "probe_recipe": preflight["timing_recipe"]["probe_clock"]})
        # Adapt field names in memory only and retain their original values.
        for _, spectrum in records:
            spectrum.metadata["source_acquisition_settings"] = deepcopy(spectrum.metadata["acquisition_settings"])
            spectrum.metadata["acquisition_settings"] = deepcopy(contract)
            spectrum.metadata["imported_source"] = str(directory / "raw/acquisition.npz")
        return BackgroundSequence(records, raw["native"], contract, readback, directory / "raw/acquisition.npz")
    except (KeyError, TypeError, OSError) as exc:
        raise ValueError(f"Saved blank lacks complete cadence, signed sequence, probe or HF2LI readback evidence: {exc}") from exc


def validate_reconstruction(result):
    wn, times = (np.asarray(result[key], dtype=float) for key in ("wavenumber_cm1", "time_s"))
    values = np.asarray(result["absorbance"], dtype=float)
    if (wn.ndim != 1 or times.ndim != 1 or not len(wn) or not len(times)
            or not np.all(np.isfinite(wn)) or not np.all(np.isfinite(times))
            or not np.all(np.diff(wn) > 0) or not np.all(np.diff(times) > 0)):
        raise ValueError("Reconstruction axes must be finite and strictly increasing")
    if values.shape != (len(times), len(wn)) or np.isinf(values).any():
        raise ValueError("Reconstruction values do not match the saved axes, or contain infinity")
    for name in ("delta_absorbance", "standard_error", "repetition_count"):
        if name in result and np.asarray(result[name]).shape != values.shape:
            raise ValueError(f"Saved {name} does not match the reconstruction axes")
    if "baseline_absorbance" in result and np.asarray(result["baseline_absorbance"]).shape != wn.shape:
        raise ValueError("Saved unpumped baseline does not match the wavelength axis")
    return result


def load_regular_run(path):
    """Load current runs and retained phase surfaces without rewriting evidence."""
    path = Path(path)
    if path.is_dir():
        candidates = [path / "processed" / "reconstruction.npz", path / "analysis" / "paired_reconstruction.npz",
                      path / "analysis" / "absorbance_and_change.npz", path / "reconstruction.npz"]
        path = next((candidate for candidate in candidates if candidate.exists()), None)
        if path is None:
            raise ValueError("No saved phase-scan reconstruction in the selected directory")
    result = load_native(path)
    if path.name in {"paired_reconstruction.npz", "absorbance_and_change.npz"}:
        for companion in (path.parent / "paired_reconstruction.npz", path.parent / "absorbance_and_change.npz"):
            if companion != path and companion.exists():
                extra = load_native(companion)
                if (not np.array_equal(result["wavenumber_cm1"], extra["wavenumber_cm1"])
                        or not np.array_equal(result["time_s"], extra["time_s"])):
                    raise ValueError("Saved phase surface and delta-absorbance companion axes differ")
                result.update(extra)
    result.setdefault("source_path", str(path))
    result.setdefault("time_label", "Time relative to electrical pump sync (s)")
    result.setdefault("pump_reference_bases", ["electrical_sync"])
    return validate_reconstruction(result)


def save_regular_reconstruction_csv(path, result):
    """Export the quantitative grid; missing cells remain literal NaN."""
    validate_reconstruction(result)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    shape = np.asarray(result["absorbance"]).shape
    missing = np.full(shape, np.nan)
    delta = result.get("delta_absorbance", missing)
    uncertainty = result.get("standard_error", missing)
    counts = result.get("repetition_count", missing)
    baseline = result.get("baseline_absorbance", np.full(shape[1], np.nan))
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["wavenumber_cm-1", "time_from_electrical_pump_sync_s", "absorbance",
                         "delta_absorbance", "unpumped_baseline_absorbance", "standard_error",
                         "repetition_count", "supported", "background_source"])
        for row, time_s in enumerate(result["time_s"]):
            for column, wn in enumerate(result["wavenumber_cm1"]):
                value = result["absorbance"][row, column]
                writer.writerow([wn, time_s, value, delta[row, column], baseline[column],
                                 uncertainty[row, column], counts[row, column], bool(np.isfinite(value)),
                                 result.get("background_source", "")])
