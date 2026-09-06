# UI hardware control reference

Use [default wiring](../../instrument/default_wiring_state.md),
[hardware configuration](../../instrument/hardware_configuration.yaml), and the
selected recipe as the current route and identity authority. Opening a tab or
loading a recipe does not operate hardware or qualify a scientific setting.

## Timing and signal routes

| Output/source | Installed destination | Function |
| --- | --- | --- |
| T660-1 A | HF2LI DIO0 | Probe external reference |
| T660-1 B | MIRcat TRIG IN | Probe pulse trigger |
| T660-1 C | T660-2 TRIG IN | Event-frame clock input |
| T660-2 A | Surelite DB9 EXT pin 7 | FIRE command |
| T660-2 B | Surelite DB9 EXT pin 6 | Q-switch command |
| T660-2 C | MIRcat DB9 pin 4 | Active-low Process Trigger |
| T660-2 CLOCK OUT | T660-1 and HF2LI CLOCK IN | Separate 10 MHz frequency reference |
| MIRcat DB9 pin 1 | HF2LI DIO20 | Scan direction |
| MIRcat DB9 pin 2 | HF2LI DIO21 and PicoScope EXT | Tuned / Sweep Active |
| MIRcat DB9 pin 3 | HF2LI DIO22 | Wavelength markers |

Both T660 D outputs and HF2LI DIO1 are unwired. MIRcat DB9 pins 5, 6, and 8
are unused and unwired. Surelite EXT pins carry TTL fire/Q-switch commands;
they are not RS-232 data signals. Captured DIO bit indices are distinct from
physical connector pin numbers.

Sample and reference detector signals have separate adapter/tee networks:
sample feeds HF2LI Signal 1 In (+)/PicoScope CHA; reference feeds Signal 2
In (+)/PicoScope CHB. Both receivers stay connected. The Sweep Active EXT
branch is high impedance with DB9 pin 7 ground; cable characteristic impedance
does not authorize a 50 ohm termination. Temporary timing/IRF connections have
separate configuration records and calibration bridges.

## Operator controls

Connect to each configured device and verify identity before applying settings.
T660-1 supplies the probe/reference train; T660-2 supplies pump/process event
trains and frames. Settings are staged while trigger sources are OFF. Read back
source, channel enables, delays, widths, polarity, impedance, predivider, train
counts, and frame state before arming. Safe Idle stops both timers, disables
outputs and the frame engine, clears active burst/gate state, forces end of
delay, and records readbacks. A shot-counter reset is not a finite-output limit.

Use the focused procedures for
[detector alignment](mircat_detector_alignment_workflow.md),
[segmented sweeps](mircat_sweep_scan_workflow.md), and
[Phase Scan](phase_scan_tab.md). The Nd:YAG alignment recipe uses T660-1 C to
clock T660-2, with FIRE/Q-switch on T660-2 A/B and its Process Trigger disabled.
The pump repetition limit is 10 Hz; it does not limit the independent MIRcat
probe carrier. Alignment examples are not calibrated biological settings.

The timing-calibration DIO1 programmable-gate operation has no installed route
and must remain unavailable. Sweep-triggered acquisition uses observed Sweep
Active; a future DIO1 route requires an explicit topology and qualification,
not automatic assignment of a spare output.

## Finite acquisition and shutdown

Preload the complete bounded T660-2 frame table before acquisition. Use
channel OFF states for unpumped baseline and inactive padding frames. Train
count zero disables additional pulses, not the first pulse of an enabled channel.
Retain the expected physical frame, scan, and pump-command counts, programmed
train table, hardware readbacks, and observed events. Confirm recorder capacity
and arm acquisition before starting the sequence. Each experiment chooses its
own frame cadence and recovery schedule; Phase Scan's fixed cadence is local
to that implementation.

Sweep histories follow MIRcat Sweep Active; synchronized pump-event data
establishes the electrical event timeline. Sample-plane optical qualification
is needed for chemical time zero. Counter agreement alone never establishes
optical emission or exposure. Wait for the final programmed outputs to complete
before normal shutdown, because frame-engine completion may precede those edges.

On normal completion, abort, exception, loss, or mismatch, close emission as
required, stop both timing devices, preserve native and partial records, and
verify safe-idle/readback restoration. Do not retry scans or merge deficient
regions silently. Reserved routes remain disabled throughout.
