# UI Hardware Control Reference

This document summarizes the hardware configuration and command sequences verified during the June 2026 control-session work. It is intended as a reference for building the system UI and for separating hardware state controls from experiment workflow controls.

## Verified Hardware Map

| Device | Port / API | Verified identity | UI role |
| --- | --- | --- | --- |
| T660-2 | `COM7`, `38400` baud | `HTI,T660-2,00431,28E660-1-1.7` | Master timing generator |
| T660-1 | `COM3`, `38400` baud | `HTI,T660-1,00369,28E660-1-1.7` | Nd:YAG fire/Q-switch timing |
| MIRcat | `COM9` through MIRcat SDK | `MIRcat-QT-Z-2100`, serial `10524` | Probe laser |
| HF2LI | LabOne API server `127.0.0.1:8005`, device `dev18500` | `dev18500` | Lock-in and DAQ |

The confirmed timing wiring to use in the UI is:

| T660-2 channel | Destination | Purpose |
| --- | --- | --- |
| `A` | HF2LI DIO 0 | HF2LI external reference |
| `B` | MIRcat TRIG IN | MIRcat external pulse/trigger candidate |
| `C` | HF2LI DIO 1 | HF2LI DAQ trigger |
| `D` | T660-1 trigger input | Triggers the Nd:YAG timing chain |

The confirmed T660-1 usage is:

| T660-1 channel | Destination | Purpose |
| --- | --- | --- |
| `A` | Nd:YAG Fire input | Surelite fire TTL |
| `B` | Nd:YAG Q-switch input | Surelite Q-switch TTL |
| `C` | MIRcat DB9 pin 4 | Process Trigger control |
| `D` | Disconnected | Unused; no configured signal or destination |

These T660 TTL timing lines are direct point-to-point routes. They are not routed through the Arduino MUX. In `hardware_configuration.yaml`, this route truth belongs under `timing_routes`, not under the PicoScope device identity.

The Arduino MUX is disabled and bypassed until the MUX inputs are rewired and requalified. The old MUX route table is intentionally empty because HF2LI `DIO16-DIO22` inputs do not mirror to HF2LI `DIO9-DIO15` outputs. The PicoScope owns only Pico identity, driver/API paths, supported capture capabilities, editable capture recipes, and `picoscope_connectors` metadata. PicoScope settings/capture checks must use direct wiring and must not require MUX route selection.

The PicoScope device configuration contains Pico identity, driver/API paths, supported capture capabilities, and recipe references only. Scenario-specific capture settings are stored in editable `recipes/picoscope_*.yaml` files and recorded in run manifests with the hardware configuration hash.

## Runtime Environment

Run hardware-control scripts from Windows Python, not WSL Python, when using LabOne and serial devices:

```text
C:\Users\Chris\AppData\Local\Programs\Python\Python312\python.exe
```

The LabOne Python package used successfully was installed at:

```python
sys.path.insert(0, r"C:\Users\Chris\AppData\Local\Temp\zhinst_26_4")
```

The MIRcat SDK DLL used successfully was:

```text
C:\Program Files\National Instruments\LabVIEW 2025\user.lib\MIRcatSDKx64-1\MIRcatSDK.dll
```

## T660 Command Pattern

Use P500-style commands. A known-good setup pattern for T660-2 is:

```text
STOP
TRIG:SOUR OFF
CHAN:OFF A
CHAN:OFF B
CHAN:OFF C
CHAN:OFF D
TRIG:FREQ:SYN 2MHz
TRIG:SHOTS 0
TRIG:SOUR SYN
```

For 2 MHz / 150 ns timing on a channel, use delay-width mode and positive polarity. Example for Channel B:

```text
CHAN:DelayWidth B
CHAN:POS B
TIME:DEL3 0
TIME:DEL4 150ns
```

For Channel A, use `TIME:DEL1` and `TIME:DEL2`. For Channel C, use `TIME:DEL5` and `TIME:DEL6`. The DAQ trigger used a 2 ms Channel C width:

```text
CHAN:DelayWidth C
CHAN:POS C
TIME:DEL5 0
TIME:DEL6 2ms
```

Always stop and disable all channels on cleanup:

```text
STOP
TRIG:SOUR OFF
CHAN:OFF A
CHAN:OFF B
CHAN:OFF C
CHAN:OFF D
```

## MIRcat Control Model

The MIRcat SDK constants verified in the session:

| SDK value | Meaning |
| --- | --- |
| `MIRcatSDK_UNITS_CM1 = 2` | Wavenumber units |
| `MIRcatSDK_PULSE_MODE_INTERNAL = 1` | Internal pulse timing |
| `MIRcatSDK_PULSE_MODE_EXTERNAL_TRIGGER = 2` | One optical pulse per external TTL rising edge |
| `MIRcatSDK_PULSE_MODE_EXTERNAL_PASSTHRU = 3` | Output follows external TTL, bounded by MIRcat limits |
| `MIRcatSDK_PROC_TRIG_MODE_INTERNAL = 1` | Internal process trigger |

The working MIRcat pulse settings were:

```text
QCL: 1
Wavenumber: 1858 cm^-1
Pulse rate: 2,000,000 Hz
Pulse width: 150 ns
Duty cycle: 30%
Current: 750 mA
```

Readback limits during testing:

```text
Max pulse rate: 3,000,000 Hz
Max pulse width: about 1005 ns
```

The UI should treat `TurnEmissionOn` as opening the MIRcat emission gate. In internal mode the laser can emit immediately after this call. In external trigger or external passthrough mode, `TurnEmissionOn` is still required, but it does not itself start optical pulses; the external TTL pulses start the optical emission after the gate is open. For external trigger workflows, the UI should display both states separately:

```text
MIRcat emission gate: ON/OFF from MIRcat SDK
External trigger source: T660 channel state and frequency
```

For external trigger/passthrough workflows, the UI must enforce this order:

1. Configure MIRcat external trigger or passthrough mode.
2. Arm and tune MIRcat.
3. Call `TurnEmissionOn` and verify `IsEmissionOn == True`.
4. Start the T660 TTL sequence.
5. Stop the T660 TTL sequence.
6. Call `TurnEmissionOff`, then disarm/deinitialize when finished.

### Reliable Internal MIRcat Sequence

The internal pulse sequence was confirmed to turn emission on successfully after these checks:

1. Safe-off T660 channels.
2. `MIRcatSDK_Initialize`.
3. `MIRcatSDK_ClearSystemError`, then verify `GetSystemErrorWord == 0`.
4. Read QCL current, temperature, set temperature, and operating mode.
5. `SetQCLParams(QCL=1, 2_000_000 Hz, 150 ns, 750 mA)`.
6. `SetWlTrigParams(pulse_mode=1, proc_mode=1, start=1858, stop=1858, interval=0, units=2, dwell=0, afteroff=0)`.
7. Verify `GetWlTrigParams` reports `pulse_mode=1`.
8. `ArmLaser`.
9. Poll `IsLaserArmed` until `True`.
10. Verify `AreTECsAtSetTemperature == True`.
11. `TuneToWW(1858, CM^-1, QCL=1)`.
12. Poll `IsLaserArmed` and `IsTuned` until both are `True`.
13. Reassert/read back internal pulse mode.
14. `TurnEmissionOn`.
15. Hold for requested duration.
16. `TurnEmissionOff`, disarm, deinitialize.

The verified internal emission artifact is:

```text
artifacts/mircat_internal_trigger_retry_2MHz_150ns_10s_20260610_163259.json
```

In that run:

```text
TurnEmissionOn -> 0
Emission window: 16:32:47 to 16:32:57
TurnEmissionOff -> 0
Final armed: False
Final emission: False
```

One earlier internal-mode attempt returned `82` (`MIRcatSDK_RET_EMISSION_ON_FAILURE`). The successful retry differed by clearing system errors, checking TEC readiness, and reasserting/reading back internal trigger mode after tuning. The UI should expose failure code `82` with a recovery action: safe-off, clear errors, recheck TECs, reassert mode, retry only if operator approves.

### External MIRcat Trigger Status

External trigger operation was confirmed after the physical CHB-to-MIRcat cable was reconnected and the MIRcat emission gate was already open from the Daylight GUI. The key finding is that the MIRcat can report its emission gate as on while waiting for external TTL pulses; it will not actually produce externally timed optical pulses until valid TTL triggers arrive at `TRIG IN`.

Verified external trigger readback:

```text
pulse_mode=2
proc_mode=1
start=1858.0
stop=1858.0
units=2
```

The final successful no-API T660 run used:

```text
T660-2 Channel B -> MIRcat TRIG IN
Frequency: 2 MHz
Pulse high time: 150 ns
T660 CHB polarity: positive
T660 CHB termination: 50OHM
No MIRcat API calls during the TTL run
```

Artifact:

```text
artifacts/t6602_chb_2MHz_150ns_after_cable_reconnect_20260611_102052.json
```

Earlier failed external-trigger tests were caused by the physical trigger cable being unplugged, not by the T660 command sequence. The visible gate test remains useful as a UI/operator workflow because it clearly separates the MIRcat emission-gate state from the T660 trigger state:

```text
16:25:21 emission gate ON, CHB off
16:25:53 CHB on, 2 MHz / 150 ns
16:26:24 CHB off
16:26:54 CHB on again
16:27:21 shutdown
```

Visible gate test artifact:

```text
artifacts/mircat_visible_gate_chb_toggle_20260610_162722.json
```

UI implication: external trigger mode should be available as a production workflow, but the UI must not start T660 CHB until the MIRcat emission gate is already on. The UI should also make cabling status/operator confirmation explicit because an unplugged trigger cable produces the same controller readbacks but no optical output.

## HF2LI LabOne Configuration

Use LabOne API server:

```python
s = zi.ziDAQServer("127.0.0.1", 8005, 1)
DEV = "dev18500"
```

External reference was configured with PLL0 using DIO0:

```python
s.setInt(f"/{DEV}/dios/0/drive", 0)
s.setInt(f"/{DEV}/plls/0/enable", 0)
s.setInt(f"/{DEV}/plls/0/adcselect", 4)      # DIO0
s.setDouble(f"/{DEV}/plls/0/freqcenter", 2_000_000.0)
s.setInt(f"/{DEV}/plls/0/harmonic", 1)
s.setInt(f"/{DEV}/plls/0/order", 4)
s.setInt(f"/{DEV}/plls/0/adcthreshold", 0)
s.setInt(f"/{DEV}/plls/0/enable", 1)
```

The successful demodulator mapping was:

| HF2LI demod | Signal input | Purpose |
| --- | --- | --- |
| `demods/0` | Signal Input 1 | Detector channel 1 |
| `demods/3` | Signal Input 2 | Detector channel 2 |

Demodulator settings used:

```python
for demod, adc in [(0, 0), (3, 1)]:
    s.setInt(f"/{DEV}/demods/{demod}/enable", 1)
    s.setInt(f"/{DEV}/demods/{demod}/adcselect", adc)
    s.setInt(f"/{DEV}/demods/{demod}/oscselect", 0)
    s.setInt(f"/{DEV}/demods/{demod}/harmonic", 1)
    s.setInt(f"/{DEV}/demods/{demod}/order", 4)
    s.setDouble(f"/{DEV}/demods/{demod}/timeconstant", 0.001)
    s.setDouble(f"/{DEV}/demods/{demod}/rate", 2000.0)
    s.setInt(f"/{DEV}/demods/{demod}/trigger", 0)
```

DAQ trigger was configured on DIO1 through `sample.dio`:

```python
mod = s.dataAcquisitionModule()
mod.set("device", DEV)
mod.set("type", 2)
mod.set("triggernode", f"/{DEV}/demods/0/sample.dio")
mod.set("bits", 2)
mod.set("bitmask", 2)
mod.set("edge", 1)
mod.set("duration", 5.0)
mod.set("delay", 0.0)
mod.set("count", 1)
mod.set("endless", 0)
mod.set("grid/mode", 4)
mod.set("grid/cols", 10000)
```

Subscribe to individual fields, not the whole sample node:

```python
for path in [
    f"/{DEV}/demods/0/sample.x",
    f"/{DEV}/demods/0/sample.y",
    f"/{DEV}/demods/0/sample.r",
    f"/{DEV}/demods/3/sample.x",
    f"/{DEV}/demods/3/sample.y",
    f"/{DEV}/demods/3/sample.r",
]:
    mod.subscribe(path)
```

Important: the HF2LI must receive and lock to the reference before MIRcat lasing and before DAQ triggering. The successful sequence started MIRcat internal emission, started T660-2 Channel A as the 2 MHz external reference, waited for PLL lock plus 2 seconds settle time, then fired T660-2 Channel C to trigger the DAQ.

Successful HF2LI/MIRcat artifact:

```text
artifacts/hf2li_mircat_api_internal_t660_daq_trigger_20260610_155400.json
artifacts/hf2li_mircat_api_internal_t660_daq_trigger_20260610_155400.csv
artifacts/hf2li_mircat_api_internal_t660_daq_trigger_20260610_155400.npz
```

Good detector data from that run:

```text
Signal Input 1 R mean: 0.2448 V
Signal Input 1 R max:  0.2478 V
Signal Input 2 R mean: 0.4612 V
Signal Input 2 R max:  0.4651 V
DAQ records: 10,000 samples per subscribed field
DAQ duration: 5 s
Demod rate: 2,000 Sa/s
```

Earlier external-trigger runs produced only microvolt-scale detector readings. The UI should treat millivolt/volt detector response as the validation condition for successful lasing, not only MIRcat `IsEmissionOn`.

## Proven MIRcat + HF2LI Workflow

This is the workflow that should be implemented first in the UI because it produced valid detector data:

1. Safe-off T660-2 and T660-1.
2. Configure MIRcat internal pulse mode at 2 MHz / 150 ns / 1858 cm^-1.
3. Arm MIRcat and poll `IsLaserArmed`.
4. Verify TECs at set temperature.
5. Tune MIRcat and verify `IsTuned`.
6. Start MIRcat emission with `TurnEmissionOn`.
7. Start T660-2 Channel A at 2 MHz / 150 ns to HF2LI DIO0.
8. Configure HF2LI PLL0 external reference from DIO0.
9. Wait for PLL lock, then wait an additional settle period.
10. Arm the HF2LI DAQ module.
11. Pulse T660-2 Channel C to HF2LI DIO1 for the DAQ trigger.
12. Read and save HF2LI DAQ data.
13. Stop MIRcat emission, disarm/deinitialize.
14. Stop T660-2 and turn off all channels.

## Proven MIRcat External Trigger Workflow

Use this workflow when T660-2 Channel B drives MIRcat optical pulse timing:

1. Confirm the physical cable is connected: `T660-2 CHB -> MIRcat TRIG IN`.
2. Configure MIRcat external trigger mode (`pulse_mode=2`) or external passthrough mode (`pulse_mode=3`), depending on the desired optical timing behavior.
3. Configure MIRcat pulse parameters, for example 2 MHz / 150 ns / 1858 cm^-1 / 750 mA.
4. Arm MIRcat and poll `IsLaserArmed` until `True`.
5. Tune MIRcat and verify `IsTuned == True`.
6. Open the MIRcat emission gate with `TurnEmissionOn`.
7. Verify `IsEmissionOn == True`.
8. Configure T660-2 CHB:

```text
TRIG:FREQ:SYN 2MHz
TRIG:SHOTS 0
CHAN:DelayWidth B
CHAN:POS B
CHAN:50OHM B
TIME:DEL3 0
TIME:DEL4 150ns
TRIG:SOUR SYN
```

9. Start the T660-2 CHB pulse train:

```text
CHAN:ON B
START
```

10. Stop the T660 pulse train before closing the MIRcat gate:

```text
CHAN:OFF B
STOP
TRIG:SOUR OFF
```

11. Close MIRcat emission with `TurnEmissionOff`, then disarm/deinitialize if the experiment is complete.

Important: in external trigger/passthrough mode, `TurnEmissionOn` must happen before the TTL sequence starts. The TTL sequence then controls when externally timed optical pulses occur.

## Nd:YAG / Surelite Workflow

The Surelite Nd:YAG was successfully fired under DAT mode 2 control using the T660 chain:

```text
T660-2 Channel D -> T660-1 trigger input
T660-1 Channel A -> Nd:YAG Fire
T660-1 Channel B -> Nd:YAG Q-switch
```

The 10 Hz maximum repetition-rate constraint applies to the Nd:YAG path, not the MIRcat. The UI should enforce `<= 10 Hz` for Nd:YAG fire controls and should keep MIRcat timing limits separate.

The UI should expose Nd:YAG controls as an armed sequence, not as raw channel toggles:

```text
Configure T660-1 Fire/Q-switch timings
Configure T660-2 Channel D trigger
Confirm repetition rate <= 10 Hz
Start burst / fire N shots
Stop and safe-off both T660s
```

The exact Fire/Q-switch delays should be stored as a named Nd:YAG preset after they are extracted from the Surelite DAT mode 2 procedure and T660 programming guide. The session verified the control architecture and firing ability, but this reference document does not encode those timing constants.

## UI State And Safety Requirements

The UI should model each device as a state machine and should require state readbacks before enabling next-step controls:

| UI state | Required readback |
| --- | --- |
| MIRcat initialized | `MIRcatSDK_Initialize -> 0` |
| MIRcat armed | poll `IsLaserArmed == True` |
| MIRcat tuned | `IsTuned == True` |
| TEC ready | `AreTECsAtSetTemperature == True` |
| MIRcat emission active | `IsEmissionOn == True` |
| HF2LI reference locked | PLL lock indicator true |
| DAQ ready | DAQ module executed and waiting |
| T660 safe | trigger source `OFF`, channels commanded `OFF` |

Recommended UI controls:

| Control | Behavior |
| --- | --- |
| `Safe Off All` | Stop T660-2, stop T660-1, channel-off all outputs, MIRcat emission off, MIRcat disarm/deinit if connected |
| `Initialize Devices` | Connect serial/API devices and show identity/readback |
| `Arm MIRcat` | Arm and poll until `IsLaserArmed` |
| `Tune MIRcat` | Tune only after armed; then verify armed and tuned |
| `MIRcat Internal Emission Test` | Use the reliable internal sequence above |
| `MIRcat External Trigger Run` | Open emission gate, verify `IsEmissionOn`, then start T660-2 CHB |
| `External Trigger Diagnostic` | Gate-on plus CHB toggle with visible timestamped announcements |
| `Acquire HF2LI Data` | Require PLL locked before DAQ trigger can be sent |
| `Fire Nd:YAG Burst` | Enforce shot count and repetition-rate cap |

Every hardware action should be timestamped and written to an artifact JSON. For operator-visible tests, the UI should show a countdown and a live event log before commands such as `TurnEmissionOn`, `CHAN:ON B`, `CHAN:OFF B`, and `TurnEmissionOff`.

## Known Failure Modes

| Symptom | Likely cause / interpretation | UI response |
| --- | --- | --- |
| `TurnEmissionOn -> 82` | MIRcat emission-on failure | Safe-off, clear system error, verify TECs/mode/tune, retry only with operator approval |
| `IsEmissionOn == True` but no detector/photochromic response | Controller gate is open but laser may not be optically lasing | Require detector validation; do not rely only on `IsEmissionOn` |
| External trigger mode readback correct but no lasing | T660 TTL is not reaching MIRcat, cabling is wrong, or emission gate was not opened before TTL started | Require cable confirmation, verify `IsEmissionOn`, then scope/check CHB at MIRcat end |
| HF2LI readings microvolt-scale | Laser not optically reaching detectors or DAQ window missed signal | Show warning and require revalidation |
| LabOne cannot connect from WSL Python | Windows loopback/API binding issue | Use Windows Python |
| COM port access denied | Port still held by another process | Show port owner/retry guidance; ensure UI has exclusive connection |
