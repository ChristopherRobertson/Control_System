"""Validate controller-reported marker coordinates without claiming calibration."""
from __future__ import annotations

from copy import deepcopy
import math
from numbers import Integral, Real


def _integer(value, low, high):
    return isinstance(value, Integral) and not isinstance(value, bool) and low <= value <= high


def _positive(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _close(a, b):
    # SDK coordinates are float32; this covers its rounding, not wavelength accuracy.
    return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-6)


def _coordinates(observation):
    readback = observation.get("readback")
    if not isinstance(readback, dict):
        raise ValueError("Controller marker readback is missing")
    channel = readback.get("channel")
    units = readback.get("units")
    count = readback.get("num_triggers")
    start, stop, interval = (readback.get(key) for key in ("start", "stop", "interval"))
    if (observation.get("source") != "MIRcatSDK_GetWlTrigChanParams" or
            not _integer(channel, 1, 255) or observation.get("channel") != channel or
            not _integer(units, 1, 2) or not _integer(count, 2, 65535) or
            not all(_positive(value) for value in (start, stop, interval)) or start == stop):
        raise ValueError("Invalid per-channel controller marker identity")
    direction = 1 if stop > start else -1
    coordinates = [float(start + direction * interval * i) for i in range(count)]
    if not _close(coordinates[-1], stop) or not all(value > 0 for value in coordinates):
        raise ValueError("Controller marker count/interval does not identify its endpoints")
    return readback, coordinates if units == 2 else [10000. / value for value in coordinates]


def controller_marker_identity(record, observed_marker_count):
    """Return checked controller labels, or None when no usable SDK readback exists.

    Successful but contradictory readbacks raise ValueError. Explicitly unavailable
    optional API observations provide no identities and cannot establish a basis.
    All configured observations, when available, must agree with the final setup
    readback. No nominal-count-only fallback is performed here.
    """
    observations = record.get("mircat_marker_channel_checks")
    if not observations:
        return None
    if not isinstance(observations, (list, tuple)) or any(not isinstance(item, dict) for item in observations):
        raise ValueError("Invalid controller marker observations")
    final = [item for item in observations if item.get("context") in {"after_sweep_setup", "after_block_setup"}]
    if not final or final[-1].get("available") is not True:
        return None
    latest = final[-1]
    readback, coordinates = _coordinates(latest)
    if not _integer(observed_marker_count, 2, 65535) or observed_marker_count != readback["num_triggers"]:
        raise ValueError("Observed wavelength-marker count differs from controller readback")
    for item in observations:
        if item.get("context") == "configured" and item.get("available") is True:
            previous, previous_coordinates = _coordinates(item)
            if (previous["channel"] != readback["channel"] or previous["units"] != readback["units"] or
                    len(previous_coordinates) != len(coordinates) or
                    not all(_close(a, b) for a, b in zip(previous_coordinates, coordinates))):
                raise ValueError("Controller marker settings changed between configuration and sweep setup")
    profile = record.get("scan_profile") or {}
    if profile.get("qcl") is not None and profile["qcl"] != readback["channel"]:
        raise ValueError("Controller marker channel differs from the captured QCL")
    for key, actual in (("start_cm1", coordinates[0]), ("stop_cm1", coordinates[-1])):
        if key in profile and (not _positive(profile[key]) or not _close(profile[key], actual)):
            raise ValueError(f"Controller marker {key} differs from the scan profile")
    if "marker_interval_cm1" in profile:
        interval = profile["marker_interval_cm1"]
        if not _positive(interval) or any(not _close(abs(b-a), interval) for a, b in zip(coordinates, coordinates[1:])):
            raise ValueError("Controller marker interval differs from the scan profile")
    return {"wavenumbers_cm1": coordinates, "wavenumber_basis": "controller_markers",
            "provisional": True, "independently_calibrated": False,
            "marker_identity_basis": {"source": "MIRcatSDK_GetWlTrigChanParams",
                                      "channel": int(readback["channel"]),
                                      "context": latest["context"],
                                      "timestamp_utc": latest.get("timestamp_utc"),
                                      "readback": deepcopy(readback)}}
