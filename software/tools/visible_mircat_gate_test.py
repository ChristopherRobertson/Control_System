import ctypes
from ctypes import byref, c_bool, c_float, c_uint8, c_uint32
import json
import os
import sys
import time
from datetime import datetime

import serial


T660_PORT = "COM7"
T660_BAUD = 38400
MIRCAT_DLL = r"C:\Program Files\National Instruments\LabVIEW 2025\user.lib\MIRcatSDKx64-1\MIRcatSDK.dll"
ARTIFACT_DIR = r"C:\users\chris\documents\github\control_system\artifacts"

WAVENUMBER_CM1 = 1858.0
QCL = 1
RATE_HZ = 2_000_000.0
PULSE_WIDTH_NS = 150.0
CURRENT_FALLBACK_MA = 750.0

RET_SUCCESS = 0
RET_EMISSION_ALREADY_OFF = 83
RET_EMISSION_ALREADY_ON = 85
RET_LASER_ALREADY_ARMED = 91
RET_LASER_ALREADY_DISARMED = 92

UNITS_CM1 = 2
PULSE_MODE_EXTERNAL_TRIGGER = 2
PROC_TRIG_MODE_INTERNAL = 1

log = {
    "timestamp": datetime.now().isoformat(timespec="seconds"),
    "intent": "Visible MIRcat emission-gate test: TurnEmissionOn held continuously while T660-2 CHB is toggled",
    "settings": {
        "wavenumber_cm-1": WAVENUMBER_CM1,
        "qcl": QCL,
        "t660_port": T660_PORT,
        "rate_hz": RATE_HZ,
        "pulse_width_ns": PULSE_WIDTH_NS,
        "duty_cycle": RATE_HZ * PULSE_WIDTH_NS * 1e-9,
        "mircat_pulse_mode": "external_trigger",
        "mircat_pulse_mode_value": PULSE_MODE_EXTERNAL_TRIGGER,
    },
    "events": [],
    "errors": [],
}


def stamp(message):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
    print(line, flush=True)
    log["events"].append(line)


def t660_send(ser, cmd, delay=0.04):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode("ascii"))
    ser.flush()
    time.sleep(delay)
    out = []
    t0 = time.time()
    while time.time() - t0 < 0.4:
        line = ser.readline()
        if not line:
            break
        text = line.decode(errors="replace").strip()
        if text:
            out.append(text)
    response = " | ".join(out)
    stamp(f"T660 {cmd!r} -> {response!r}")
    return response


def load_sdk():
    sdk = ctypes.CDLL(MIRCAT_DLL)
    sdk.MIRcatSDK_Initialize.restype = c_uint32
    sdk.MIRcatSDK_DeInitialize.restype = c_uint32
    sdk.MIRcatSDK_IsLaserArmed.argtypes = [ctypes.POINTER(c_bool)]
    sdk.MIRcatSDK_IsLaserArmed.restype = c_uint32
    sdk.MIRcatSDK_ArmLaser.restype = c_uint32
    sdk.MIRcatSDK_ArmDisarmLaser.restype = c_uint32
    sdk.MIRcatSDK_IsTuned.argtypes = [ctypes.POINTER(c_bool)]
    sdk.MIRcatSDK_IsTuned.restype = c_uint32
    sdk.MIRcatSDK_TuneToWW.argtypes = [c_float, c_uint8, c_uint8]
    sdk.MIRcatSDK_TuneToWW.restype = c_uint32
    sdk.MIRcatSDK_IsEmissionOn.argtypes = [ctypes.POINTER(c_bool)]
    sdk.MIRcatSDK_IsEmissionOn.restype = c_uint32
    sdk.MIRcatSDK_TurnEmissionOn.restype = c_uint32
    sdk.MIRcatSDK_TurnEmissionOff.restype = c_uint32
    sdk.MIRcatSDK_GetQCLCurrent.argtypes = [c_uint8, ctypes.POINTER(c_float)]
    sdk.MIRcatSDK_GetQCLCurrent.restype = c_uint32
    sdk.MIRcatSDK_GetQCLPulseLimits.argtypes = [
        c_uint8,
        ctypes.POINTER(c_float),
        ctypes.POINTER(c_float),
        ctypes.POINTER(c_float),
    ]
    sdk.MIRcatSDK_GetQCLPulseLimits.restype = c_uint32
    sdk.MIRcatSDK_SetQCLParams.argtypes = [c_uint8, c_float, c_float, c_float]
    sdk.MIRcatSDK_SetQCLParams.restype = c_uint32
    sdk.MIRcatSDK_SetWlTrigParams.argtypes = [
        c_uint8,
        c_uint8,
        c_float,
        c_float,
        c_float,
        c_uint8,
        c_uint32,
        c_uint32,
    ]
    sdk.MIRcatSDK_SetWlTrigParams.restype = c_uint32
    sdk.MIRcatSDK_GetWlTrigParams.argtypes = [
        ctypes.POINTER(c_uint8),
        ctypes.POINTER(c_uint8),
        ctypes.POINTER(c_float),
        ctypes.POINTER(c_float),
        ctypes.POINTER(c_float),
        ctypes.POINTER(c_uint8),
        ctypes.POINTER(c_uint32),
        ctypes.POINTER(c_uint32),
    ]
    sdk.MIRcatSDK_GetWlTrigParams.restype = c_uint32
    return sdk


def sdk_call(sdk, name, *args, ok=(RET_SUCCESS,)):
    ret = int(getattr(sdk, name)(*args))
    stamp(f"SDK {name} -> {ret}")
    if ret not in ok:
        raise RuntimeError(f"{name} returned {ret}")
    return ret


def sdk_bool(sdk, name):
    value = c_bool(False)
    ret = int(getattr(sdk, name)(byref(value)))
    stamp(f"SDK {name} -> {ret}, {value.value}")
    if ret != RET_SUCCESS:
        raise RuntimeError(f"{name} returned {ret}")
    return value.value


def poll_true(sdk, name, label, timeout_s=90):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if sdk_bool(sdk, name):
            return True
        time.sleep(0.5)
    raise TimeoutError(f"MIRcat did not report {label} before timeout")


def read_wltrig(sdk):
    pulse_mode = c_uint8()
    proc_mode = c_uint8()
    start = c_float()
    stop = c_float()
    interval = c_float()
    units = c_uint8()
    dwell = c_uint32()
    afteroff = c_uint32()
    ret = int(
        sdk.MIRcatSDK_GetWlTrigParams(
            byref(pulse_mode),
            byref(proc_mode),
            byref(start),
            byref(stop),
            byref(interval),
            byref(units),
            byref(dwell),
            byref(afteroff),
        )
    )
    stamp(
        "SDK MIRcatSDK_GetWlTrigParams -> "
        f"{ret}, pulse_mode={pulse_mode.value}, proc_mode={proc_mode.value}, "
        f"start={start.value}, stop={stop.value}, interval={interval.value}, "
        f"units={units.value}, dwell_us={dwell.value}, afteroff_us={afteroff.value}"
    )
    if ret != RET_SUCCESS:
        raise RuntimeError(f"GetWlTrigParams returned {ret}")
    log["wltrig_readback"] = {
        "pulse_mode": pulse_mode.value,
        "proc_mode": proc_mode.value,
        "start": start.value,
        "stop": stop.value,
        "interval": interval.value,
        "units": units.value,
        "dwell_us": dwell.value,
        "afteroff_us": afteroff.value,
    }
    return pulse_mode.value


def write_artifact():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    path = os.path.join(
        ARTIFACT_DIR,
        f"mircat_visible_gate_chb_toggle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    stamp(f"Artifact written: {path}")
    return path


def configure_t660(ser):
    for cmd in [
        "STOP",
        "TRIG:SOUR OFF",
        "CHAN:OFF A",
        "CHAN:OFF B",
        "CHAN:OFF C",
        "CHAN:OFF D",
        "TRIG:FREQ:SYN 2MHz",
        "TRIG:SHOTS 0",
        "CHAN:DelayWidth B",
        "CHAN:POS B",
        "TIME:DEL3 0",
        "TIME:DEL4 150ns",
        "TRIG:SOUR SYN",
    ]:
        t660_send(ser, cmd)


def configure_mircat(sdk):
    sdk_call(sdk, "MIRcatSDK_Initialize")

    current = c_float(0.0)
    ret_current = int(sdk.MIRcatSDK_GetQCLCurrent(c_uint8(QCL), byref(current)))
    stamp(f"SDK MIRcatSDK_GetQCLCurrent -> {ret_current}, {current.value} mA")
    current_ma = float(current.value) if ret_current == RET_SUCCESS and current.value > 0 else CURRENT_FALLBACK_MA
    log["mircat_current_ma_used"] = current_ma

    max_rate = c_float(0.0)
    max_width = c_float(0.0)
    max_duty = c_float(0.0)
    ret_limits = int(
        sdk.MIRcatSDK_GetQCLPulseLimits(
            c_uint8(QCL), byref(max_rate), byref(max_width), byref(max_duty)
        )
    )
    stamp(
        "SDK MIRcatSDK_GetQCLPulseLimits -> "
        f"{ret_limits}, max_rate={max_rate.value}, "
        f"max_width_ns={max_width.value}, max_duty={max_duty.value}"
    )
    if ret_limits == RET_SUCCESS:
        if RATE_HZ > max_rate.value + 1:
            raise RuntimeError(f"Requested rate {RATE_HZ} exceeds MIRcat limit {max_rate.value}")
        if PULSE_WIDTH_NS > max_width.value + 1e-6:
            raise RuntimeError(f"Requested width {PULSE_WIDTH_NS} exceeds MIRcat limit {max_width.value}")

    duty = RATE_HZ * PULSE_WIDTH_NS * 1e-9
    if duty > 0.3000001:
        raise RuntimeError(f"Requested duty cycle {duty:.6f} exceeds 30%")

    sdk_call(
        sdk,
        "MIRcatSDK_SetQCLParams",
        c_uint8(QCL),
        c_float(RATE_HZ),
        c_float(PULSE_WIDTH_NS),
        c_float(current_ma),
    )
    sdk_call(
        sdk,
        "MIRcatSDK_SetWlTrigParams",
        c_uint8(PULSE_MODE_EXTERNAL_TRIGGER),
        c_uint8(PROC_TRIG_MODE_INTERNAL),
        c_float(WAVENUMBER_CM1),
        c_float(WAVENUMBER_CM1),
        c_float(0.0),
        c_uint8(UNITS_CM1),
        c_uint32(0),
        c_uint32(0),
    )
    read_wltrig(sdk)

    if not sdk_bool(sdk, "MIRcatSDK_IsLaserArmed"):
        sdk_call(sdk, "MIRcatSDK_ArmLaser", ok=(RET_SUCCESS, RET_LASER_ALREADY_ARMED))
    poll_true(sdk, "MIRcatSDK_IsLaserArmed", "armed")
    sdk_call(sdk, "MIRcatSDK_TuneToWW", c_float(WAVENUMBER_CM1), c_uint8(UNITS_CM1), c_uint8(QCL))
    poll_true(sdk, "MIRcatSDK_IsLaserArmed", "armed after tune")
    poll_true(sdk, "MIRcatSDK_IsTuned", "tuned")
    read_wltrig(sdk)
    sdk_bool(sdk, "MIRcatSDK_IsEmissionOn")


def main():
    ser = None
    sdk = None
    initialized = False
    artifact_path = None
    try:
        stamp("Opening T660-2 and MIRcat for visible gated test")
        ser = serial.Serial(T660_PORT, T660_BAUD, timeout=0.25, write_timeout=0.5)
        configure_t660(ser)
        sdk = load_sdk()
        configure_mircat(sdk)
        initialized = True
        stamp("READY_FOR_VISIBLE_SEQUENCE: gate closed, CHB off, MIRcat armed/tuned, external trigger mode confirmed")

        for raw in sys.stdin:
            cmd = raw.strip().lower()
            if not cmd:
                continue
            try:
                if cmd == "gate_on":
                    stamp("COMMAND gate_on: opening MIRcat emission gate; CHB remains off")
                    sdk_call(sdk, "MIRcatSDK_TurnEmissionOn", ok=(RET_SUCCESS, RET_EMISSION_ALREADY_ON))
                    sdk_bool(sdk, "MIRcatSDK_IsEmissionOn")
                    stamp("DONE gate_on")
                elif cmd == "chb_on":
                    stamp("COMMAND chb_on: enabling T660-2 CHB 2 MHz / 150 ns")
                    t660_send(ser, "CHAN:ON B")
                    t660_send(ser, "START")
                    stamp("DONE chb_on")
                elif cmd == "chb_off":
                    stamp("COMMAND chb_off: disabling T660-2 CHB while MIRcat gate remains unchanged")
                    t660_send(ser, "CHAN:OFF B")
                    stamp("DONE chb_off")
                elif cmd == "shutdown":
                    stamp("COMMAND shutdown: CHB off, T660 stopped, MIRcat emission gate closed, disarm, deinitialize")
                    t660_send(ser, "CHAN:OFF B")
                    t660_send(ser, "STOP")
                    t660_send(ser, "TRIG:SOUR OFF")
                    sdk_call(
                        sdk,
                        "MIRcatSDK_TurnEmissionOff",
                        ok=(RET_SUCCESS, RET_EMISSION_ALREADY_OFF),
                    )
                    sdk_bool(sdk, "MIRcatSDK_IsEmissionOn")
                    if sdk_bool(sdk, "MIRcatSDK_IsLaserArmed"):
                        sdk_call(
                            sdk,
                            "MIRcatSDK_ArmDisarmLaser",
                            ok=(RET_SUCCESS, RET_LASER_ALREADY_DISARMED),
                        )
                    ret = int(sdk.MIRcatSDK_DeInitialize())
                    stamp(f"SDK MIRcatSDK_DeInitialize -> {ret}")
                    initialized = False
                    artifact_path = write_artifact()
                    print(f"SHUTDOWN_COMPLETE {artifact_path}", flush=True)
                    return
                else:
                    stamp(f"UNKNOWN_COMMAND {cmd!r}")
            except Exception as exc:
                log["errors"].append(repr(exc))
                stamp(f"ERROR handling {cmd!r}: {exc!r}")
                raise
    except Exception as exc:
        log["errors"].append(repr(exc))
        stamp(f"FATAL_ERROR: {exc!r}")
        raise
    finally:
        stamp("FINAL_CLEANUP")
        if ser is not None:
            try:
                for cmd in ["CHAN:OFF B", "STOP", "TRIG:SOUR OFF", "CHAN:OFF A", "CHAN:OFF C", "CHAN:OFF D"]:
                    t660_send(ser, cmd)
            except Exception as exc:
                stamp(f"T660 cleanup failed: {exc!r}")
            try:
                ser.close()
            except Exception:
                pass
        if sdk is not None and initialized:
            try:
                sdk_call(sdk, "MIRcatSDK_TurnEmissionOff", ok=(RET_SUCCESS, RET_EMISSION_ALREADY_OFF))
            except Exception as exc:
                stamp(f"Emission-off cleanup failed: {exc!r}")
            try:
                if sdk_bool(sdk, "MIRcatSDK_IsLaserArmed"):
                    sdk_call(sdk, "MIRcatSDK_ArmDisarmLaser", ok=(RET_SUCCESS, RET_LASER_ALREADY_DISARMED))
            except Exception as exc:
                stamp(f"Disarm cleanup failed: {exc!r}")
            try:
                ret = int(sdk.MIRcatSDK_DeInitialize())
                stamp(f"SDK MIRcatSDK_DeInitialize -> {ret}")
            except Exception as exc:
                stamp(f"SDK deinit cleanup failed: {exc!r}")
        if artifact_path is None:
            try:
                write_artifact()
            except Exception as exc:
                stamp(f"Artifact cleanup write failed: {exc!r}")


if __name__ == "__main__":
    main()
