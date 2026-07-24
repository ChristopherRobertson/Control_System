"""Complete, operator-guided timing calibration for the pump-probe system.

The workflow is deliberately split into a reviewable plan and an explicit
hardware execution.  Hardware execution safe-idles before every cable change,
prints the complete setup, waits for the required phrase, and keeps all raw and
derived artifacts inside one unique run directory.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, TextIO
import csv
import hashlib
import json
import math
import statistics
import time
import uuid

import yaml

from control_app.config_loader import (
    ConfigInventory,
    REPO_ROOT,
    load_config_inventory,
)
from control_app.devices.picoscope_service import PicoScopeService
from control_app.devices.t660_service import T660Service
from control_app.workflows.timing_trace_analysis import (
    DEFAULT_SEPARATIONS_NS,
    DEFAULT_SHOT_COUNT,
    TimingCalibrationError,
    analyze_pico_trace,
)
from control_app.workflows.picoscope_settings_test import (
    capture_settings_from_recipe,
    validate_capture_settings,
)
from control_app.workflows.timing_recipe_manager import TimingRecipeManager


DIRECT_TRIGGER_RATE_HZ = 100
T660_1_TRIGGER_RATE_HZ = 10
PICOSCOPE_TIMEBASE_ACCURACY_PPM = 2.0
MAX_SAMPLES_PER_TRACE = 150_000
DEFAULT_OPTICAL_MINIMUM_LATENCY_NS = 5.0
PLAN_SCHEMA_VERSION = "1.0"
RESULT_SCHEMA_VERSION = "1.0"
DEFAULT_OPTICAL_RECIPE = "recipes/ndyag_alignment_10hz.yaml"
SAFE_IDLE_RECIPE = REPO_ROOT / "recipes" / "safe_idle.yaml"


class SafeIdleVerificationError(TimingCalibrationError):
    """Raised when STOP/OFF application or readback cannot be verified."""


@dataclass(frozen=True)
class MeasurementStep:
    """One immutable physical setup in the sequential calibration."""

    setup_id: str
    step: str
    measurement_id: str
    title: str
    category: str
    purpose: str
    reference_event: str
    target_event: str
    pico_ch_a: str
    pico_ch_b: str
    disconnect: tuple[str, ...]
    remains_connected: tuple[str, ...]
    uses_final_wiring: bool
    splitter_used: bool
    splitter_mapping: str
    correction_rule: str
    programmed_delay_mode: str
    trigger_rate_hz: int
    use_in_timing_recipe: bool
    reporting_label: str
    notes: str
    reference_signal: str | None = None
    target_signal: str | None = None
    dependency_signals: tuple[str, ...] = ()
    reference_edge: str = "rising"
    target_edge: str = "rising"
    requires_output_safety_confirmation: bool = False
    requires_laser_safety_confirmation: bool = False
    optical: bool = False
    recipe_use_condition: str = ""

    @property
    def sweep_delays(self) -> bool:
        return self.programmed_delay_mode == "six_point_sweep"


MEASUREMENT_STEPS: tuple[MeasurementStep, ...] = (
    MeasurementStep(
        setup_id="step_0a_splitter_normal",
        step="0a",
        measurement_id="MS-00A",
        title="Measurement-system correction: splitter normal orientation",
        category="measurement-system correction",
        purpose="Measure the combined PicoScope channel/cable skew and splitter branch skew.",
        reference_event="Splitter output 1 arrival",
        target_event="Splitter output 2 arrival",
        pico_ch_a="T660-2 CHA fixed 12-inch SMB-to-BNC bulkhead assembly -> installed EXT REF downstream BNC cable -> CLOCK-SPLITTER-01 input -> output 1 -> complete labeled CHA measurement assembly (including planned adapters) -> PicoScope CHA",
        pico_ch_b="T660-2 CHA fixed 12-inch SMB-to-BNC bulkhead assembly -> installed EXT REF downstream BNC cable -> CLOCK-SPLITTER-01 input -> output 2 -> complete labeled CHB measurement assembly (including planned adapters) -> PicoScope CHB",
        disconnect=(
            "Temporarily remove CLOCK-SPLITTER-01 from the T660-2 CLOCK distribution and label/park its installed 1.5-foot branches to T660-1 CLOCK and HF2LI CLOCK for exact restoration.",
            "Leave the fixed 12-inch T660-2 CHA SMB-to-BNC bulkhead assembly installed. Disconnect the installed 1-foot EXT REF downstream BNC cable only at the HF2LI destination and connect that free destination end to CLOCK-SPLITTER-01 input.",
            "No laser or MIRcat DB9 timing input may be driven by this setup.",
        ),
        remains_connected=(
            "T660-2 CHB remains physically connected to MIRcat TRIG IN, CHC to HF2LI DIO1 DAQ, and CHD to T660-1 TRIG IN; all three source channels are disabled.",
            "The Nd:YAG timing DB9 and MIRcat DB9 connectors remain physically installed; all four T660-1 channels and its trigger source are read back OFF. T660-1 and HF2LI CLOCK inputs are temporarily disconnected only while CLOCK-SPLITTER-01 is used for Step 0.",
        ),
        uses_final_wiring=False,
        splitter_used=True,
        splitter_mapping="output 1 -> CHA; output 2 -> CHB",
        correction_rule="normal = scope(B-A) + splitter(branch2-branch1)",
        programmed_delay_mode="fixed_zero_only",
        trigger_rate_hz=DIRECT_TRIGGER_RATE_HZ,
        use_in_timing_recipe=False,
        reporting_label="PicoScope plus splitter normal-orientation diagnostic",
        notes="Keep the same two complete scope measurement assemblies assigned to CHA and CHB for Step 0b, Step 0c, and later measurements.",
        reference_signal="hf2li_extref",
    ),
    MeasurementStep(
        setup_id="step_0b_splitter_swapped",
        step="0b",
        measurement_id="MS-00B",
        title="Measurement-system correction: splitter branches swapped",
        category="measurement-system correction",
        purpose="Separate PicoScope channel/cable skew from splitter branch skew.",
        reference_event="Splitter output 2 arrival",
        target_event="Splitter output 1 arrival",
        pico_ch_a="T660-2 CHA fixed bulkhead and installed EXT REF downstream BNC cable -> CLOCK-SPLITTER-01 output 2 -> the same CHA lead -> PicoScope CHA",
        pico_ch_b="T660-2 CHA fixed bulkhead and installed EXT REF downstream BNC cable -> CLOCK-SPLITTER-01 output 1 -> the same CHB lead -> PicoScope CHB",
        disconnect=(
            "Leave the installed EXT REF downstream BNC cable disconnected only at HF2LI and connected to CLOCK-SPLITTER-01 input; do not disturb the fixed T660-2 CHA bulkhead assembly.",
            "Swap only the splitter branches; do not swap the two scope leads at the PicoScope.",
        ),
        remains_connected=(
            "T660-2 CHB remains physically connected to MIRcat TRIG IN, CHC to HF2LI DIO1 DAQ, and CHD to T660-1 TRIG IN; all three source channels are disabled.",
            "The Nd:YAG timing DB9 and MIRcat DB9 connectors remain physically installed exactly as in Step 0a; all T660-1 outputs and its trigger source are read back OFF.",
        ),
        uses_final_wiring=False,
        splitter_used=True,
        splitter_mapping="output 2 -> CHA; output 1 -> CHB",
        correction_rule="swapped = scope(B-A) - splitter(branch2-branch1)",
        programmed_delay_mode="fixed_zero_only",
        trigger_rate_hz=DIRECT_TRIGGER_RATE_HZ,
        use_in_timing_recipe=False,
        reporting_label="PicoScope plus splitter swapped-orientation diagnostic",
        notes="scope(B-A)=(normal+swapped)/2; splitter(branch2-branch1)=(normal-swapped)/2.",
        reference_signal="hf2li_extref",
    ),
    MeasurementStep(
        setup_id="step_0c_splitter_installed_geometry",
        step="0c",
        measurement_id="MS-00C",
        title="Measurement-system correction: installed Step 7 splitter geometry",
        category="measurement-system correction",
        purpose="Measure the temporary splitter plus the exact unequal branch leads that will be installed for the optical measurement.",
        reference_event="Splitter output 1 arrival through the final Q-switch cable/DB9 adapter",
        target_event="Splitter output 2 arrival through the exact Step 7 monitor lead",
        pico_ch_a="T660-2 CHA fixed bulkhead and installed EXT REF downstream BNC cable -> CLOCK-SPLITTER-01 output 1 -> final Q-switch cable and approved pin-6 adapter -> same CHA lead -> PicoScope CHA",
        pico_ch_b="T660-2 CHA fixed bulkhead and installed EXT REF downstream BNC cable -> CLOCK-SPLITTER-01 output 2 -> exact Step 7 monitor adapter/lead -> same CHB lead -> PicoScope CHB",
        disconnect=(
            "Leave the fixed 12-inch T660-1 CHB SMB-to-BNC bulkhead assembly installed. Disconnect the downstream Q-switch BNC cable at the CHB bulkhead and disconnect its other end from Nd:YAG DB9 pin 6; connect that downstream cable to splitter output 1 and the same complete CHA measurement assembly used in Steps 0a/0b.",
            "Use the exact branch cables/adapters planned for Step 7; do not substitute equal test leads.",
            "At the final Q-switch-cable endpoint, reproduce the documented Nd:YAG pin-6 input loading with the reviewed matched-load/tee/high-impedance probing method.",
        ),
        remains_connected=(
            "T660-2 CHB remains physically connected to MIRcat TRIG IN, CHC to HF2LI DIO1 DAQ, and CHD to T660-1 TRIG IN; all three source channels are disabled.",
            "T660-1 FIRE remains physically connected to Nd:YAG pin 7 and the MIRcat DB9 remains installed, all with outputs OFF; the final Q-switch cable is disconnected at both T660-1 CHB and Nd:YAG pin 6.",
        ),
        uses_final_wiring=False,
        splitter_used=True,
        splitter_mapping="output 1 -> final Q-switch cable on CHA; output 2 -> exact monitor lead on CHB",
        correction_rule="installed branch2-monitor minus branch1-Q-switch delay = mean(MS-00C) - scope(B-A)",
        programmed_delay_mode="fixed_zero_only",
        trigger_rate_hz=DIRECT_TRIGGER_RATE_HZ,
        use_in_timing_recipe=False,
        reporting_label="Installed Step 7 splitter/branch-lead correction",
        notes="This measurement prevents temporary splitter and unequal lead delay from being folded into optical pump-arrival timing. The frozen plan records how the Nd:YAG pin-6 load is reproduced while probing.",
        reference_signal="hf2li_extref",
    ),
    MeasurementStep(
        setup_id="step_1_extref_to_daq",
        step="1",
        measurement_id="TC-01",
        title="HF2LI EXT REF to HF2LI DAQ relative timing",
        category="relative route offset",
        purpose="Measure the arrival mismatch between the final HF2LI reference and DAQ-trigger routes.",
        reference_event="HF2LI EXT REF arrival at the final CHA cable destination end",
        target_event="HF2LI DAQ trigger arrival at the final CHC cable destination end",
        pico_ch_a="T660-2 CHA final EXT REF cable, disconnected at HF2LI destination end -> PicoScope CHA",
        pico_ch_b="T660-2 CHC final DAQ cable, disconnected at HF2LI destination end -> PicoScope CHB",
        disconnect=(
            "Disconnect the EXT REF downstream BNC destination end from the Step 0 splitter input and route it to PicoScope CHA; leave its fixed T660-2 CHA bulkhead assembly installed. Park the labeled Q-switch/monitor assembly before reconnecting any laser timing harness.",
            "Restore CLOCK-SPLITTER-01 to T660-2 CLOCK and restore the same installed 1.5-foot branches and splitter output ports to T660-1 CLOCK and HF2LI CLOCK. Verify this normal CLOCK distribution before any clock-dependent recipe.",
            "Disconnect only the final DAQ downstream BNC destination end from HF2LI DIO1 and route it to PicoScope CHB; do not disturb the fixed T660-2 CHC bulkhead assembly.",
        ),
        remains_connected=(
            "T660-2 CHB remains connected to MIRcat TRIG IN but disabled; T660-2 CHD remains connected to T660-1 TRIG IN but disabled.",
            "The Nd:YAG timing DB9 and MIRcat DB9 connectors remain physically installed; all T660-1 outputs remain read back OFF.",
        ),
        uses_final_wiring=True,
        splitter_used=False,
        splitter_mapping="none",
        correction_rule="subtract scope/cable B-A skew from measured B-A",
        programmed_delay_mode="six_point_sweep",
        trigger_rate_hz=DIRECT_TRIGGER_RATE_HZ,
        use_in_timing_recipe=True,
        reporting_label="HF2LI reference-to-DAQ relative route offset",
        notes="This is not an absolute DAQ route delay, even if the two final cables are nominally matched.",
        reference_signal="hf2li_extref",
        target_signal="hf2li_daq_trigger",
    ),
    MeasurementStep(
        setup_id="step_2_extref_to_mircat_trigger",
        step="2",
        measurement_id="TC-02",
        title="HF2LI EXT REF to MIRcat TRIG IN relative timing",
        category="relative route offset",
        purpose="Measure MIRcat TRIG IN arrival relative to the final HF2LI EXT REF route.",
        reference_event="HF2LI EXT REF arrival at the final CHA cable destination end",
        target_event="MIRcat TRIG IN arrival at the final CHB cable destination end",
        pico_ch_a="T660-2 CHA final EXT REF cable, disconnected at HF2LI destination end -> PicoScope CHA",
        pico_ch_b="T660-2 CHB final MIRcat TRIG IN cable, disconnected at MIRcat destination end -> PicoScope CHB",
        disconnect=(
            "Restore T660-2 CHC to HF2LI DIO1 DAQ after Step 1; keep the CHA destination end disconnected for the scope reference.",
            "Disconnect T660-2 CHB only at MIRcat TRIG IN and connect that destination end to PicoScope CHB.",
        ),
        remains_connected=(
            "T660-2 CHC is restored to HF2LI DIO1 DAQ but disabled; T660-2 CHD remains connected to T660-1 TRIG IN but disabled.",
            "MIRcat DB9 process-control connector remains attached only with all T660-1 outputs disabled.",
            "The Nd:YAG timing DB9 remains physically installed with FIRE and Q-switch outputs read back OFF.",
        ),
        uses_final_wiring=True,
        splitter_used=False,
        splitter_mapping="none",
        correction_rule="subtract scope/cable B-A skew from measured B-A",
        programmed_delay_mode="six_point_sweep",
        trigger_rate_hz=DIRECT_TRIGGER_RATE_HZ,
        use_in_timing_recipe=True,
        reporting_label="HF2LI reference-to-MIRcat-trigger relative route offset",
        notes="Relative route timing includes T660-2 channel skew and final cable/connector mismatch.",
        reference_signal="hf2li_extref",
        target_signal="mircat_trig_in",
        requires_output_safety_confirmation=True,
    ),
    MeasurementStep(
        setup_id="step_3_extref_to_t6601_trigger",
        step="3",
        measurement_id="TC-03",
        title="HF2LI EXT REF to T660-1 TRIG IN relative timing",
        category="relative route offset",
        purpose="Measure the T660-1 trigger-input route arrival relative to HF2LI EXT REF.",
        reference_event="HF2LI EXT REF arrival at the final CHA cable destination end",
        target_event="T660-1 TRIG IN arrival at the final CHD cable destination end",
        pico_ch_a="T660-2 CHA final EXT REF cable, disconnected at HF2LI destination end -> PicoScope CHA",
        pico_ch_b="T660-2 CHD final T660-1 trigger cable, disconnected at T660-1 destination end -> PicoScope CHB",
        disconnect=(
            "Restore T660-2 CHB to MIRcat TRIG IN after Step 2; keep the CHA destination end disconnected for the scope reference.",
            "Disconnect T660-2 CHD only at T660-1 TRIG IN and connect that destination end to PicoScope CHB.",
        ),
        remains_connected=(
            "T660-2 CHB is restored to MIRcat TRIG IN and CHC remains on HF2LI DIO1 DAQ; both are disabled.",
            "The Nd:YAG timing DB9 and MIRcat DB9 remain physically installed with all T660-1 outputs disabled; T660-1 TRIG IN is physically disconnected during capture.",
        ),
        uses_final_wiring=True,
        splitter_used=False,
        splitter_mapping="none",
        correction_rule="subtract scope/cable B-A skew from measured B-A",
        programmed_delay_mode="six_point_sweep",
        trigger_rate_hz=DIRECT_TRIGGER_RATE_HZ,
        use_in_timing_recipe=True,
        reporting_label="HF2LI reference-to-T660-1-trigger relative route offset",
        notes="This is a route offset, not the downstream T660-1 timing-chain latency.",
        reference_signal="hf2li_extref",
        target_signal="t660_1_trig_in",
        requires_output_safety_confirmation=True,
    ),
    MeasurementStep(
        setup_id="step_4_extref_to_fire",
        step="4",
        measurement_id="TC-04",
        title="HF2LI EXT REF to Nd:YAG FIRE electrical arrival",
        category="cross-device timing-chain latency",
        purpose="Measure the HF2LI EXT REF cable-end reference to FIRE electrical timing chain through T660-2 CHD and T660-1.",
        reference_event="HF2LI EXT REF arrival at the final CHA cable destination end",
        target_event="Nd:YAG FIRE arrival at DB9 pin 7",
        pico_ch_a="T660-2 CHA final EXT REF cable, disconnected at HF2LI destination end -> PicoScope CHA",
        pico_ch_b="T660-1 CHA final FIRE conductor at the disconnected Nd:YAG DB9 pin 7 -> PicoScope CHB",
        disconnect=(
            "Remove CHD from PicoScope CHB and restore the final CHD cable to T660-1 TRIG IN before enabling this setup.",
            "Disconnect the Nd:YAG timing DB9 from the laser before exposing pin 7 to the scope.",
            "Disconnect/cap the MIRcat DB9 process-control connector for the electrical-only T660-1 steps.",
            "Keep the CHA final destination disconnected from HF2LI and connected to PicoScope CHA.",
        ),
        remains_connected=(
            "T660-2 CHD final cable remains connected to T660-1 TRIG IN; T660-2 CHB remains at MIRcat TRIG IN and CHC at HF2LI DAQ but both are disabled.",
            "Neither Nd:YAG FIRE/Q-switch nor MIRcat DB9 process-control inputs receive a T660-1 line during this electrical setup.",
        ),
        uses_final_wiring=True,
        splitter_used=False,
        splitter_mapping="none",
        correction_rule="subtract scope/cable B-A skew from measured B-A",
        programmed_delay_mode="six_point_sweep",
        trigger_rate_hz=T660_1_TRIGGER_RATE_HZ,
        use_in_timing_recipe=True,
        reporting_label="HF2LI EXT REF arrival-to-Nd:YAG-FIRE electrical chain latency",
        notes="Referenced to the final EXT REF route arrival while t_master=0 remains the programmed T660-2 event.",
        reference_signal="hf2li_extref",
        target_signal="ndyag_fire",
        dependency_signals=("t660_1_trig_in",),
        target_edge="falling",
        requires_output_safety_confirmation=True,
    ),
    MeasurementStep(
        setup_id="step_5_fire_to_qswitch",
        step="5",
        measurement_id="TC-05",
        title="Nd:YAG FIRE to Q-switch electrical arrival",
        category="FIRE-to-Q-switch electrical timing",
        purpose="Measure the actual FIRE-to-Q-switch electrical delay at the Nd:YAG DB9 connector.",
        reference_event="Nd:YAG FIRE arrival at DB9 pin 7",
        target_event="Nd:YAG Q-switch arrival at DB9 pin 6",
        pico_ch_a="T660-1 CHA final FIRE conductor at disconnected Nd:YAG DB9 pin 7 -> PicoScope CHA",
        pico_ch_b="T660-1 CHB final Q-switch conductor at disconnected Nd:YAG DB9 pin 6 -> PicoScope CHB",
        disconnect=(
            "From Step 4, keep the Nd:YAG timing DB9 disconnected; move FIRE pin 7 from PicoScope CHB to PicoScope CHA and connect Q-switch pin 6 to PicoScope CHB.",
            "Disconnect the EXT REF destination from PicoScope CHA and park/cap that labeled destination end; T660-2 CHA is disabled in this step.",
        ),
        remains_connected=(
            "T660-2 CHD final cable remains connected to T660-1 TRIG IN; T660-2 CHB/CHC final device routes remain connected but disabled.",
            "No T660-1 output is connected to Nd:YAG or MIRcat; only FIRE and Q-switch breakout conductors reach the PicoScope.",
        ),
        uses_final_wiring=True,
        splitter_used=False,
        splitter_mapping="none",
        correction_rule="subtract scope/cable B-A skew from measured B-A",
        programmed_delay_mode="six_point_sweep",
        trigger_rate_hz=T660_1_TRIGGER_RATE_HZ,
        use_in_timing_recipe=True,
        reporting_label="Nd:YAG FIRE-to-Q-switch electrical timing correction",
        notes="The intercept is fixed channel/route timing; slope ppm is delay-scale drift and is reported separately.",
        reference_signal="ndyag_fire",
        target_signal="ndyag_q_switch",
        dependency_signals=("t660_1_trig_in",),
        reference_edge="falling",
        target_edge="falling",
        requires_output_safety_confirmation=True,
    ),
    MeasurementStep(
        setup_id="step_6_extref_to_qswitch_validation",
        step="6",
        measurement_id="TC-06",
        title="HF2LI EXT REF to Q-switch electrical arrival validation",
        category="derived-chain validation",
        purpose="Directly validate HF2LI EXT REF arrival-to-Q-switch timing derived from Steps 4 and 5.",
        reference_event="HF2LI EXT REF arrival at the final CHA cable destination end",
        target_event="Nd:YAG Q-switch arrival at DB9 pin 6",
        pico_ch_a="T660-2 CHA final EXT REF cable, disconnected at HF2LI destination end -> PicoScope CHA",
        pico_ch_b="T660-1 CHB final Q-switch conductor at disconnected Nd:YAG DB9 pin 6 -> PicoScope CHB",
        disconnect=(
            "From Step 5, park/cap FIRE pin 7, keep Q-switch pin 6 on PicoScope CHB, and route the disconnected final EXT REF destination back to PicoScope CHA.",
            "Keep the complete Nd:YAG timing DB9 disconnected from the laser.",
        ),
        remains_connected=(
            "T660-2 CHD final cable remains connected to T660-1 TRIG IN; T660-2 CHB/CHC final device routes remain connected but disabled.",
            "Neither Nd:YAG nor MIRcat receives a T660-1 timing/control output; Q-switch reaches only PicoScope CHB.",
        ),
        uses_final_wiring=True,
        splitter_used=False,
        splitter_mapping="none",
        correction_rule="subtract scope/cable B-A skew; compare intercept with TC-04 + TC-05",
        programmed_delay_mode="six_point_sweep",
        trigger_rate_hz=T660_1_TRIGGER_RATE_HZ,
        use_in_timing_recipe=False,
        reporting_label="Direct HF2LI EXT REF arrival-to-Q-switch chain validation",
        notes="Validation row; use the explicit closure residual instead of silently replacing the component measurements.",
        reference_signal="hf2li_extref",
        target_signal="ndyag_q_switch",
        dependency_signals=("t660_1_trig_in",),
        target_edge="falling",
        requires_output_safety_confirmation=True,
    ),
    MeasurementStep(
        setup_id="step_7_qswitch_to_optical",
        step="7",
        measurement_id="TC-07",
        title="Q-switch electrical arrival to optical OPO pulse at sample",
        category="optical pump-arrival delay",
        purpose="Connect electrical timing to chemical time zero at the sample position.",
        reference_event="Q-switch electrical arrival at the Nd:YAG DB9 pin 6 branch",
        target_event="Optical OPO pump pulse arrival at the sample or sample-equivalent position",
        pico_ch_a="T660-1 CHB Q-switch -> splitter input; output 2 -> same CHA measurement lead -> PicoScope CHA",
        pico_ch_b="Strongly attenuated 200-1100 nm photodetector at sample position -> PicoScope CHB",
        disconnect=(
            "Safe-idle, remove all temporary electrical-step DB9 scope connections, and restore the approved Nd:YAG timing harness before installing the splitter.",
            "Install the exact splitter, Q-switch branch, monitor branch, CHA assembly, detector lead, attenuation, and sample-position geometry documented in the frozen plan.",
        ),
        remains_connected=(
            "Splitter output 1 remains connected to Nd:YAG Q-switch DB9 pin 6; T660-1 CHA FIRE remains connected to Nd:YAG pin 7.",
            "T660-2 CHD remains connected to T660-1 TRIG IN; T660-2 CHA/CHB/CHC and T660-1 CHC/CHD remain explicitly disabled.",
            "MIRcat TRIG IN may remain physically connected to disabled T660-2 CHB; MIRcat DB9 process-control lines are disconnected/capped.",
            "The approved OPO optical path remains configured to the strongly attenuated detector at the sample position or frozen equivalent plane.",
        ),
        uses_final_wiring=False,
        splitter_used=True,
        splitter_mapping="output 1 -> actual Nd:YAG pin 6; output 2 -> PicoScope CHA",
        correction_rule="measured(B-A) - scope(B-A) + installed Step 7 geometry from MS-00C - photodetector response delay",
        programmed_delay_mode="operational_recipe_fixed_delay",
        trigger_rate_hz=T660_1_TRIGGER_RATE_HZ,
        use_in_timing_recipe=True,
        reporting_label="Q-switch-to-optical-pump arrival at sample (t_chem anchor)",
        notes="The temporary installed splitter geometry is measured in load-equivalent MS-00C; detector/lead response provenance, sample-path uncertainty, a beam-blocked control, and a live unsaturated preview are required before accepted shots.",
        reference_signal="ndyag_q_switch",
        reference_edge="falling",
        target_edge="rising",
        requires_output_safety_confirmation=True,
        requires_laser_safety_confirmation=True,
        optical=True,
    ),
    MeasurementStep(
        setup_id="step_8_fire_to_mircat_process",
        step="8",
        measurement_id="TC-08",
        title="T660-1 FIRE to MIRcat process-trigger electrical arrival",
        category="MIRcat DB9 process-control timing",
        purpose="Measure T660-1 CHA/FIRE to CHC/process-trigger channel-plus-route timing.",
        reference_event="T660-1 CHA FIRE reference at disconnected Nd:YAG DB9 pin 7",
        target_event="T660-1 CHC MIRcat Process Trigger at disconnected DB9 pin 4",
        pico_ch_a="T660-1 CHA final FIRE conductor at disconnected Nd:YAG DB9 pin 7 -> PicoScope CHA",
        pico_ch_b="T660-1 CHC final MIRcat Process Trigger conductor at disconnected MIRcat DB9 pin 4 -> PicoScope CHB",
        disconnect=(
            "Safe-idle and remove the temporary Step 7 splitter completely; restore the Q-switch source cable to T660-1 CHB, then disconnect the Nd:YAG timing DB9 before probing FIRE pin 7.",
            "Disconnect the MIRcat DB9 connector before exposing pin 4 to PicoScope CHB; keep reserved pin 5 (Laser Output On/Off) disconnected.",
        ),
        remains_connected=(
            "T660-2 CHD final cable remains connected to T660-1 TRIG IN; T660-2 CHB/CHC final routes remain physically connected but disabled.",
            "The full Nd:YAG timing DB9 and MIRcat DB9 connectors are disconnected; neither device receives a measured T660-1 line.",
        ),
        uses_final_wiring=True,
        splitter_used=False,
        splitter_mapping="none",
        correction_rule="subtract scope/cable B-A skew from measured B-A",
        programmed_delay_mode="six_point_sweep",
        trigger_rate_hz=T660_1_TRIGGER_RATE_HZ,
        use_in_timing_recipe=True,
        reporting_label="FIRE-to-MIRcat DB9 pin 4 process-control timing",
        notes="This combines T660-1 channel skew and the final DB9 route; master-relative timing is derived with TC-04.",
        reference_signal="ndyag_fire",
        target_signal="mircat_db9_pin_4_process_trigger",
        dependency_signals=("t660_1_trig_in",),
        reference_edge="falling",
        target_edge="falling",
        requires_output_safety_confirmation=True,
        recipe_use_condition="conditional: yes only if T660-1 CHC is used to gate or mark MIRcat process timing",
    ),
)


class RemoteShotController:
    """Fire one T660-2 remote shot per armed Pico block and audit exposure."""

    def __init__(
        self,
        *,
        inventory: ConfigInventory,
        command_log: TextIO | None = None,
        minimum_interval_s: float = 0.1,
    ) -> None:
        self.inventory = inventory
        self.command_log = command_log
        self.minimum_interval_s = float(minimum_interval_s)
        self._services: dict[str, T660Service] = {}
        self._last_fire_monotonic: float | None = None

    def open(self) -> None:
        try:
            for unit in ("t660_1", "t660_2"):
                service = T660Service(
                    unit,
                    deepcopy(self.inventory.t660_devices[unit]),
                    command_log=self.command_log,
                )
                service.connect()
                self._services[unit] = service
                service.identify()
        except Exception:
            self.close()
            raise

    def reset_counters(self) -> None:
        self._require_open()
        for service in self._services.values():
            service.reset_shot_counter()

    def fire_once(self) -> None:
        self._require_open()
        if self._last_fire_monotonic is not None:
            while True:
                now = time.monotonic()
                remaining = self.minimum_interval_s - (
                    now - self._last_fire_monotonic
                )
                if remaining <= 0:
                    break
                time.sleep(remaining)
        self._services["t660_2"].fire_remote_trigger()
        self._last_fire_monotonic = time.monotonic()

    def read_counts(self) -> dict[str, int]:
        self._require_open()
        return {
            unit: service.get_shot_count()
            for unit, service in self._services.items()
        }

    def close(self) -> None:
        for service in self._services.values():
            service.close()
        self._services.clear()

    def _require_open(self) -> None:
        if set(self._services) != {"t660_1", "t660_2"}:
            raise TimingCalibrationError(
                "Remote optical shot controller is not connected to both T660 units"
            )


class TimingCalibrationProcedure:
    """Build the review plan, execute it sequentially, and consolidate results."""

    def __init__(
        self,
        *,
        operator: str,
        inventory: ConfigInventory | None = None,
        config_path: str | Path | None = None,
        command_log: TextIO | None = None,
        timing_manager_factory: Callable[..., TimingRecipeManager] = TimingRecipeManager,
        pico_factory: Callable[..., PicoScopeService] = PicoScopeService,
        remote_shot_controller_factory: Callable[..., "RemoteShotController"] | None = None,
    ) -> None:
        self.operator = operator
        self.inventory = inventory or load_config_inventory(config_path, write_files=False)
        self.config_path = Path(self.inventory.config_path)
        self.command_log = command_log
        self._timing_manager_factory = timing_manager_factory
        self._pico_factory = pico_factory
        self._remote_shot_controller_factory = (
            remote_shot_controller_factory or RemoteShotController
        )

    def build_plan(
        self,
        *,
        separations_ns: Iterable[int] = DEFAULT_SEPARATIONS_NS,
        shot_count: int = DEFAULT_SHOT_COUNT,
        reduced_set_rationale: str | None = None,
        picoscope_recipe_path: str | Path = "recipes/picoscope_settings_test.yaml",
        optical_recipe_path: str | Path = DEFAULT_OPTICAL_RECIPE,
        photodetector_edge: str = "rising",
        photodetector_threshold_adc: int = 5000,
        photodetector_minimum_latency_ns: float = DEFAULT_OPTICAL_MINIMUM_LATENCY_NS,
        photodetector_maximum_latency_ns: float | None = None,
        photodetector_response_delay_ns: float | None = None,
        photodetector_response_uncertainty_ns: float | None = None,
        photodetector_response_source: str | None = None,
        photodetector_identifier: str | None = None,
        photodetector_cable_identifier: str | None = None,
        photodetector_characterization_date: str | None = None,
        photodetector_path_description: str | None = None,
        sample_path_standard_uncertainty_ns: float | None = None,
        step7_load_match_method: str | None = None,
        step7_load_match_standard_uncertainty_ns: float | None = None,
        measurement_assembly_record: str | None = None,
    ) -> dict[str, Any]:
        separations = _validate_sweep(
            separations_ns,
            shot_count,
            reduced_set_rationale=reduced_set_rationale,
        )
        hardware_config_sha256 = _sha256_file(self.inventory.config_path)
        if hardware_config_sha256 != self.inventory.config_hash:
            raise TimingCalibrationError(
                "hardware_configuration.yaml changed after the in-memory inventory was loaded; reload configuration and create a new plan"
            )
        pico_recipe, resolved_pico_recipe, picoscope_recipe_sha256 = (
            _load_yaml_mapping_with_sha256(picoscope_recipe_path)
        )
        frozen_pico_settings = _settings_with_channel_a_trigger(
            capture_settings_from_recipe(pico_recipe),
            edge="rising",
        )
        optical_recipe = _resolve_repo_path(optical_recipe_path).resolve()
        effective_optical_recipe = _load_and_validate_optical_recipe(
            optical_recipe,
            expected_rate_hz=T660_1_TRIGGER_RATE_HZ,
        )
        optical_validation = TimingRecipeManager(self.inventory).validate_recipe(
            effective_optical_recipe
        )
        safe_idle_recipe, resolved_safe_idle_recipe, safe_idle_recipe_sha256 = (
            _load_yaml_mapping_with_sha256(SAFE_IDLE_RECIPE)
        )
        safe_idle_validation = TimingRecipeManager(self.inventory).validate_recipe(
            safe_idle_recipe
        )
        if photodetector_edge not in {"rising", "falling"}:
            raise TimingCalibrationError("photodetector edge must be rising or falling")
        if not -32767 <= int(photodetector_threshold_adc) <= 32767:
            raise TimingCalibrationError(
                "photodetector threshold must be within -32767..32767 ADC counts"
            )
        for name, value in (
            ("photodetector_response_delay_ns", photodetector_response_delay_ns),
            (
                "photodetector_response_uncertainty_ns",
                photodetector_response_uncertainty_ns,
            ),
            ("photodetector_minimum_latency_ns", photodetector_minimum_latency_ns),
            ("photodetector_maximum_latency_ns", photodetector_maximum_latency_ns),
            ("sample_path_standard_uncertainty_ns", sample_path_standard_uncertainty_ns),
            (
                "step7_load_match_standard_uncertainty_ns",
                step7_load_match_standard_uncertainty_ns,
            ),
        ):
            if value is not None and not math.isfinite(float(value)):
                raise TimingCalibrationError(f"{name} must be finite")
        if (
            photodetector_response_uncertainty_ns is not None
            and float(photodetector_response_uncertainty_ns) < 0
        ):
            raise TimingCalibrationError(
                "photodetector_response_uncertainty_ns must be non-negative"
            )
        if (
            photodetector_response_delay_ns is not None
            and float(photodetector_response_delay_ns) < 0
        ):
            raise TimingCalibrationError(
                "photodetector_response_delay_ns is a positive latency to subtract and must be non-negative"
            )
        if float(photodetector_minimum_latency_ns) < 0:
            raise TimingCalibrationError(
                "photodetector_minimum_latency_ns must be non-negative"
            )
        if (
            photodetector_maximum_latency_ns is not None
            and float(photodetector_maximum_latency_ns)
            <= float(photodetector_minimum_latency_ns)
        ):
            raise TimingCalibrationError(
                "photodetector_maximum_latency_ns must be greater than the minimum latency"
            )
        if (
            sample_path_standard_uncertainty_ns is not None
            and float(sample_path_standard_uncertainty_ns) < 0
        ):
            raise TimingCalibrationError(
                "sample_path_standard_uncertainty_ns must be non-negative"
            )
        if (
            step7_load_match_standard_uncertainty_ns is not None
            and float(step7_load_match_standard_uncertainty_ns) < 0
        ):
            raise TimingCalibrationError(
                "step7_load_match_standard_uncertainty_ns must be non-negative"
            )
        if str(photodetector_characterization_date or "").strip():
            try:
                datetime.strptime(
                    str(photodetector_characterization_date).strip(),
                    "%Y-%m-%d",
                )
            except ValueError as exc:
                raise TimingCalibrationError(
                    "photodetector_characterization_date must use YYYY-MM-DD"
                ) from exc
        load_method = str(step7_load_match_method or "").strip()
        steps: list[MeasurementStep] = []
        for step in MEASUREMENT_STEPS:
            updated = replace(step, target_edge=photodetector_edge) if step.optical else step
            if step.setup_id == "step_0c_splitter_installed_geometry":
                updated = replace(
                    updated,
                    notes=(
                        f"{updated.notes} Reviewed load-equivalence method: "
                        f"{load_method or 'UNRESOLVED BEFORE HARDWARE'}"
                    ),
                )
            steps.append(updated)
        unresolved_step7_inputs = [
            name
            for name, value in {
                "photodetector_response_delay_ns": photodetector_response_delay_ns,
                "photodetector_response_uncertainty_ns": photodetector_response_uncertainty_ns,
                "photodetector_response_source": photodetector_response_source,
                "photodetector_identifier": photodetector_identifier,
                "photodetector_cable_identifier": photodetector_cable_identifier,
                "photodetector_characterization_date": photodetector_characterization_date,
                "photodetector_path_description": photodetector_path_description,
                "sample_path_standard_uncertainty_ns": sample_path_standard_uncertainty_ns,
                "photodetector_maximum_latency_ns": photodetector_maximum_latency_ns,
                "step7_load_match_method": step7_load_match_method,
                "step7_load_match_standard_uncertainty_ns": step7_load_match_standard_uncertainty_ns,
                "measurement_assembly_record": measurement_assembly_record,
            }.items()
            if value is None or (isinstance(value, str) and not value.strip())
        ]
        recipe_validator = TimingRecipeManager(self.inventory)
        frozen_electrical_recipes: dict[str, dict[str, str]] = {}
        resolved_electrical_recipes: dict[str, dict[str, Any]] = {}
        electrical_review_summary: list[dict[str, Any]] = []
        for step in steps:
            if step.optical:
                continue
            delays = separations if step.sweep_delays else [0]
            frozen_electrical_recipes[step.setup_id] = {}
            resolved_electrical_recipes[step.setup_id] = {}
            for delay_ns in delays:
                generated = self.build_step_recipe(
                    step,
                    programmed_delay_ns=delay_ns,
                )
                resolved = recipe_validator.validate_recipe(generated)[
                    "resolved_settings"
                ]
                frozen_electrical_recipes[step.setup_id][str(delay_ns)] = (
                    _sha256_json(resolved)
                )
                resolved_electrical_recipes[step.setup_id][str(delay_ns)] = resolved
            review_recipe = resolved_electrical_recipes[step.setup_id][str(delays[0])]
            enabled_outputs: list[str] = []
            disabled_outputs: list[str] = []
            trigger_sources: dict[str, str] = {}
            for unit, unit_settings in review_recipe.items():
                trigger_sources[unit] = str(unit_settings.get("trigger_source", ""))
                for channel, settings in (unit_settings.get("channels") or {}).items():
                    description = f"{unit} CH{channel} {settings.get('signal', '')}"
                    if settings.get("enabled") is True:
                        enabled_outputs.append(
                            f"{description}: delay={settings.get('delay')}, width={settings.get('width')}, polarity={settings.get('polarity')}, termination={settings.get('termination')}"
                        )
                    else:
                        disabled_outputs.append(description)
            electrical_review_summary.append(
                {
                    "setup_id": step.setup_id,
                    "measurement_id": step.measurement_id,
                    "programmed_delays_ns": delays,
                    "trigger_sources": trigger_sources,
                    "enabled_outputs_at_first_delay": enabled_outputs,
                    "disabled_outputs": disabled_outputs,
                }
            )
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "generated_utc": _utc_now(),
            "status": "PREHARDWARE_REVIEW_ONLY",
            "operator": self.operator,
            "config_hash": self.inventory.config_hash,
            "config_path": self.inventory.config_path,
            "configuration_files": {
                "hardware_configuration": {
                    "path": str(Path(self.inventory.config_path).resolve()),
                    "sha256": hardware_config_sha256,
                },
                "wiring_map": {
                    "path": str((REPO_ROOT / "wiring_map.yaml").resolve()),
                    "sha256": _sha256_file(REPO_ROOT / "wiring_map.yaml"),
                },
            },
            "implementation": {
                "workflow_path": str(Path(__file__).resolve()),
                "workflow_sha256": _sha256_file(Path(__file__)),
                "procedure_document_path": str(
                    (REPO_ROOT / "docs" / "timing_calibration_procedure.md").resolve()
                ),
                "procedure_document_sha256": _sha256_file(
                    REPO_ROOT / "docs" / "timing_calibration_procedure.md"
                ),
            },
            "time_origins": {
                "t_master": (
                    "t_master = 0 is the first programmed T660-2 timing event. "
                    "It is recipe/programming zero, not optical time zero."
                ),
                "t_chem": (
                    "t_chem = 0 is optical OPO pump-pulse arrival at the sample, "
                    "established by TC-07."
                ),
            },
            "sign_convention": "Raw and corrected delay is target on Pico CHB minus reference on Pico CHA; positive means target arrived later.",
            "sweep": {
                "electrical_programmed_delays_ns": separations,
                "shot_count_per_point": shot_count,
                "reduced_set_rationale": reduced_set_rationale,
                "exceptions": {
                    "MS-00A/MS-00B/MS-00C": "No delay sweep: both scope channels observe one split edge.",
                    "TC-07": "No artificial sweep: use the approved operational 10 Hz FIRE/Q-switch recipe and repeated optical shots.",
                },
            },
            "rates": {
                "direct_t660_2_hz": DIRECT_TRIGGER_RATE_HZ,
                "all_t660_1_and_optical_hz": T660_1_TRIGGER_RATE_HZ,
                "reason": "Periods are much longer than the 1 ms sweep endpoint, preventing edge-cycle ambiguity; laser operation never exceeds 10 Hz.",
            },
            "recipes": {
                "procedure_base": {
                    "path": str((REPO_ROOT / "recipes" / "timing_calibration.yaml").resolve()),
                    "sha256": _sha256_file(REPO_ROOT / "recipes" / "timing_calibration.yaml"),
                },
                "safe_idle": {
                    "path": str(resolved_safe_idle_recipe),
                    "sha256": safe_idle_recipe_sha256,
                    "resolved_settings_sha256": _sha256_json(
                        safe_idle_validation["resolved_settings"]
                    ),
                    "resolved_settings": safe_idle_validation["resolved_settings"],
                },
                "picoscope": {
                    "path": str(resolved_pico_recipe.resolve()),
                    "sha256": picoscope_recipe_sha256,
                    "effective_capture_settings": frozen_pico_settings,
                },
                "optical": {
                    "path": str(optical_recipe),
                    "source_sha256": effective_optical_recipe["_source_sha256"],
                    "effective_recipe_sha256": _sha256_json(effective_optical_recipe),
                    "resolved_settings_sha256": _sha256_json(
                        optical_validation["resolved_settings"]
                    ),
                    "prehardware_validation_status": optical_validation["status"],
                    "effective_trigger_source": "REM",
                    "selected_program_ns": effective_optical_recipe[
                        "timing_calibration_selected_program_ns"
                    ],
                    "resolved_settings": optical_validation["resolved_settings"],
                },
                "generated_electrical_recipe_sha256_by_setup_and_delay_ns": frozen_electrical_recipes,
                "resolved_electrical_settings_by_setup_and_delay_ns": resolved_electrical_recipes,
                "electrical_review_summary": electrical_review_summary,
            },
            "capture_policy": {
                "automatic_timebase_and_window": True,
                "maximum_samples_per_trace": MAX_SAMPLES_PER_TRACE,
                "one_millisecond_in_same_run": True,
                "reason": "Bound raw volume while preserving the finest supported timebase that covers each delay; sample-resolution uncertainty is retained in the fit.",
            },
            "optical_recipe_path": str(optical_recipe),
            "photodetector": {
                "edge": photodetector_edge,
                "threshold_adc": int(photodetector_threshold_adc),
                "saturation_reject_adc": 30_000,
                "minimum_signal_to_noise": 5.0,
                "threshold_sensitivity_check": "repeat edge pick at threshold +/- max(100 ADC, 10 percent) and include half-range/sqrt(3) as standard uncertainty",
                "minimum_accepted_latency_after_qswitch_ns": float(
                    photodetector_minimum_latency_ns
                ),
                "maximum_accepted_latency_after_qswitch_ns": (
                    float(photodetector_maximum_latency_ns)
                    if photodetector_maximum_latency_ns is not None
                    else None
                ),
                "response_delay_correction_ns": photodetector_response_delay_ns,
                "response_delay_standard_uncertainty_ns": photodetector_response_uncertainty_ns,
                "response_characterization_source": photodetector_response_source,
                "detector_identifier": photodetector_identifier,
                "detector_cable_identifier": photodetector_cable_identifier,
                "response_characterization_date": photodetector_characterization_date,
                "sample_or_equivalent_path_description": photodetector_path_description,
                "sample_path_standard_uncertainty_ns": sample_path_standard_uncertainty_ns,
                "step7_qswitch_load_equivalence_method": step7_load_match_method,
                "step7_qswitch_load_equivalence_standard_uncertainty_ns": step7_load_match_standard_uncertainty_ns,
                "measurement_assembly_record": measurement_assembly_record,
                "requirements": [
                    "Detector is at the sample or sample-equivalent optical path length.",
                    "Beam is strongly attenuated.",
                    "A remotely fired beam-blocked control must show no delayed detector edge.",
                    "One real preview must pass saturation, signal-above-noise, latency-window, and threshold-sensitivity checks before operator acceptance.",
                ],
            },
            "optical_exposure_policy": {
                "t660_2_source": "REM",
                "beam_blocked_control_shots": 1,
                "live_safety_preview_shots": 1,
                "accepted_measurement_shots_after_preview": shot_count,
                "maximum_total_remote_shots": shot_count + 2,
                "automatic_retry_shots_permitted": 0,
                "scope_armed_before_each_remote_trigger": True,
                "t660_1_and_t660_2_counters_must_match_each_batch": True,
            },
            "operator_sequence": [asdict(step) for step in steps],
            "final_restoration": {
                "safe_idle_readback_required_before_handling": True,
                "instructions": [
                    "Remove PicoScope probes from isolated Nd:YAG FIRE pin 7 and MIRcat Process Trigger pin 4.",
                    "Restore all labeled final device cables/connectors only under the approved shutdown/restoration checklist.",
                    "Do not enable any T660 output during restoration; verify both units remain safe-idled.",
                ],
                "required_phrase": "FINAL CABLING RESTORED SAFE",
            },
            "corrections": {
                "scope_skew_b_minus_a_ns": "(mean(MS-00A) + mean(MS-00B)) / 2",
                "splitter_branch_2_minus_1_ns": "(mean(MS-00A) - mean(MS-00B)) / 2",
                "direct_measurements": "corrected = raw(B-A) - scope_skew(B-A)",
                "TC-07": (
                    "corrected optical delay = raw(B-A) - scope_skew(B-A) "
                    "+ installed_splitter_and_branch_geometry(MS-00C) "
                    "- photodetector_response_delay"
                ),
                "step7_installed_branch_geometry": "measured automatically by MS-00C",
            },
            "analysis": {
                "fit": "weighted corrected_measured_ns = intercept_ns + slope * programmed_ns, using per-point SEM plus a sample-resolution floor and retaining intercept/slope covariance",
                "slope_ppm": "(slope - 1) * 1e6",
                "slope_uncertainty": "fit slope standard error combined in quadrature with PicoScope 2 ppm timebase accuracy",
                "recipe_correction": "zero-arrival correction = -intercept/slope with covariance propagation",
                "fixed_offset": "fit intercept only; the 1 ms residual is not treated as cable delay",
                "timebase_accuracy_ppm": PICOSCOPE_TIMEBASE_ACCURACY_PPM,
                "timebase_accuracy_source": "docs/PicoScope/PicoScope 5000D Series Data Sheet.pdf, p. 17, PicoScope 5244D initial timebase accuracy +/-2 ppm",
                "timebase_annual_drift_status": "data sheet lists +/-1 ppm/year; not added unless the reviewed instrument calibration/age record requires it",
                "t660_programmed_delay_specification_status": "empirically evaluated by the six-point fit and reported as slope ppm; no separate manufacturer absolute-delay term is folded into the fixed intercept",
                "cable_reconnection_repeatability_status": "not separately evaluated; channel-assigned assembly identifiers and repeated-shot jitter are retained",
            },
            "prehardware_blockers": (
                [
                    "Resolve all Step 7 detector, optical-path, and load-equivalence inputs before hardware execution: "
                    + ", ".join(unresolved_step7_inputs)
                ]
                if unresolved_step7_inputs
                else []
            ),
            "output_policy": {
                "run_local_only": True,
                "existing_run_data_overwritten": False,
                "raw_trace_directory": "raw_pico_traces/ (git ignored)",
                "rsi_drafts_updated": False,
                "canonical_calibration_updated": False,
            },
        }

    def write_plan(self, run_dir: str | Path, **plan_kwargs: Any) -> dict[str, str]:
        run_path = Path(run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        # Render the human-review copy from the same JSON-normalized object that
        # is persisted.  This makes the reviewed Markdown reproducible after a
        # JSON reload (including mapping order and tuple/list normalization).
        plan = json.loads(
            json.dumps(self.build_plan(**plan_kwargs), sort_keys=True, default=str)
        )
        json_path = _write_json_new(run_path / "timing_calibration_plan.json", plan)
        markdown_path = _write_text_new(
            run_path / "timing_calibration_plan.md",
            render_plan_markdown(plan),
        )
        return {"json": str(json_path), "markdown": str(markdown_path)}

    def run(
        self,
        *,
        run_dir: str | Path,
        picoscope_recipe_path: str | Path = "recipes/picoscope_settings_test.yaml",
        optical_recipe_path: str | Path = DEFAULT_OPTICAL_RECIPE,
        separations_ns: Iterable[int] = DEFAULT_SEPARATIONS_NS,
        shot_count: int = DEFAULT_SHOT_COUNT,
        reduced_set_rationale: str | None = None,
        photodetector_edge: str = "rising",
        photodetector_threshold_adc: int = 5000,
        photodetector_minimum_latency_ns: float = DEFAULT_OPTICAL_MINIMUM_LATENCY_NS,
        photodetector_maximum_latency_ns: float | None = None,
        photodetector_response_delay_ns: float | None = None,
        photodetector_response_uncertainty_ns: float | None = None,
        photodetector_response_source: str | None = None,
        photodetector_identifier: str | None = None,
        photodetector_cable_identifier: str | None = None,
        photodetector_characterization_date: str | None = None,
        photodetector_path_description: str | None = None,
        sample_path_standard_uncertainty_ns: float | None = None,
        step7_load_match_method: str | None = None,
        step7_load_match_standard_uncertainty_ns: float | None = None,
        measurement_assembly_record: str | None = None,
        prompt: Callable[[str], str] = input,
        emit: Callable[[str], None] = print,
        hardware_state_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Execute all setups in order after interactive confirmations."""

        run_path = Path(run_dir).resolve()
        _require_fresh_acquisition_directory(run_path)
        step7_corrections = _validate_step7_corrections(
            photodetector_response_delay_ns=photodetector_response_delay_ns,
            photodetector_response_uncertainty_ns=photodetector_response_uncertainty_ns,
            photodetector_response_source=photodetector_response_source,
            photodetector_identifier=photodetector_identifier,
            photodetector_cable_identifier=photodetector_cable_identifier,
            photodetector_characterization_date=photodetector_characterization_date,
            photodetector_path_description=photodetector_path_description,
            sample_path_standard_uncertainty_ns=sample_path_standard_uncertainty_ns,
            step7_load_match_method=step7_load_match_method,
            step7_load_match_standard_uncertainty_ns=step7_load_match_standard_uncertainty_ns,
            measurement_assembly_record=measurement_assembly_record,
        )
        separations = _validate_sweep(
            separations_ns,
            shot_count,
            reduced_set_rationale=reduced_set_rationale,
        )
        plan = self.build_plan(
            separations_ns=separations,
            shot_count=shot_count,
            reduced_set_rationale=reduced_set_rationale,
            picoscope_recipe_path=picoscope_recipe_path,
            optical_recipe_path=optical_recipe_path,
            photodetector_edge=photodetector_edge,
            photodetector_threshold_adc=photodetector_threshold_adc,
            photodetector_minimum_latency_ns=photodetector_minimum_latency_ns,
            photodetector_maximum_latency_ns=photodetector_maximum_latency_ns,
            **step7_corrections,
        )
        reviewed_plan = validate_reviewed_plan_artifacts(run_path, plan)
        if plan.get("prehardware_blockers"):
            raise TimingCalibrationError(
                "Reviewed plan still has prehardware blockers: "
                + "; ".join(str(item) for item in plan["prehardware_blockers"])
            )

        # Load every file-backed runtime input into memory from one hashed byte
        # snapshot before hardware access. The long run never re-reads these
        # recipes, so a later filesystem change cannot alter applied settings.
        safe_idle_recipe, _, safe_idle_sha256 = _load_yaml_mapping_with_sha256(
            reviewed_plan["recipes"]["safe_idle"]["path"]
        )
        if safe_idle_sha256 != reviewed_plan["recipes"]["safe_idle"]["sha256"]:
            raise TimingCalibrationError(
                "safe_idle.yaml changed after plan review; create and review a new plan"
            )
        safe_idle_resolved = TimingRecipeManager(self.inventory).validate_recipe(
            safe_idle_recipe
        )["resolved_settings"]
        if safe_idle_resolved != reviewed_plan["recipes"]["safe_idle"]["resolved_settings"]:
            raise TimingCalibrationError(
                "Resolved safe-idle settings differ from the reviewed plan"
            )

        pico_recipe, resolved_pico_recipe, pico_recipe_sha256 = (
            _load_yaml_mapping_with_sha256(
                reviewed_plan["recipes"]["picoscope"]["path"]
            )
        )
        if pico_recipe_sha256 != reviewed_plan["recipes"]["picoscope"]["sha256"]:
            raise TimingCalibrationError(
                "PicoScope recipe changed after plan review; create and review a new plan"
            )
        base_capture_settings = _settings_with_channel_a_trigger(
            capture_settings_from_recipe(pico_recipe),
            edge="rising",
        )
        if base_capture_settings != reviewed_plan["recipes"]["picoscope"]["effective_capture_settings"]:
            raise TimingCalibrationError(
                "Effective PicoScope settings differ from the reviewed plan"
            )

        effective_optical_recipe = _load_and_validate_optical_recipe(
            reviewed_plan["recipes"]["optical"]["path"],
            expected_rate_hz=T660_1_TRIGGER_RATE_HZ,
        )
        optical_plan = reviewed_plan["recipes"]["optical"]
        runtime_recipe_validator = TimingRecipeManager(self.inventory)
        optical_validation = runtime_recipe_validator.validate_recipe(
            effective_optical_recipe
        )
        if (
            effective_optical_recipe["_source_sha256"] != optical_plan["source_sha256"]
            or _sha256_json(effective_optical_recipe)
            != optical_plan["effective_recipe_sha256"]
            or optical_validation["resolved_settings"]
            != optical_plan["resolved_settings"]
        ):
            raise TimingCalibrationError(
                "Effective optical recipe differs from the reviewed plan; create and review a new plan"
            )

        emit(f"Review plan: {run_path / 'timing_calibration_plan.md'}")
        _require_phrase(
            prompt,
            "Type REVIEWED TIMING PLAN to confirm the complete plan was reviewed before hardware access: ",
            "REVIEWED TIMING PLAN",
        )
        _log(self.command_log, "operator_confirmation=REVIEWED TIMING PLAN")

        device_config = self.inventory.devices.get("picoscope")
        if not isinstance(device_config, dict):
            raise TimingCalibrationError("picoscope missing from hardware_configuration.yaml")
        validate_capture_settings(base_capture_settings, device_config)

        raw_dir = run_path / "raw_pico_traces"
        readback_dir = run_path / "timing_readbacks"
        result_dir = run_path / "results"
        raw_dir.mkdir(exist_ok=False)
        readback_dir.mkdir(exist_ok=False)
        result_dir.mkdir(exist_ok=False)

        timing_manager = self._make_timing_manager()
        pico = self._make_pico(device_config, base_capture_settings)
        rows: list[dict[str, Any]] = []
        readback_paths: list[str] = []
        raw_paths: list[str] = []
        capture_profiles: dict[str, dict[str, Any]] = {}
        optical_exposure_audit: dict[str, Any] | None = None
        safe_idle_counter = 0

        execution_error: BaseException | None = None
        try:
            if hardware_state_callback is not None:
                hardware_state_callback("OPEN_ATTEMPT")
            pico.open_unit()
            if hardware_state_callback is not None:
                hardware_state_callback("OPENED")
            pico.capture_settings = base_capture_settings
            pico.apply_capture_settings()
            base_validation = pico.validate_sample_timing()
            base_interval_ns = float(base_validation["sample_interval_ns"])

            for step_data in plan["operator_sequence"]:
                step = MeasurementStep(**step_data)
                safe_idle_counter += 1
                safe_path = readback_dir / f"{safe_idle_counter:03d}_safe_idle_before_{step.setup_id}.json"
                _apply_verified_safe_idle(
                    timing_manager, safe_path, recipe=safe_idle_recipe
                )
                readback_paths.append(str(safe_path))

                emit(format_operator_prompt(step, plan=plan))
                _require_phrase(
                    prompt,
                    f"Type READY {step.setup_id} when the cabling exactly matches the instructions: ",
                    f"READY {step.setup_id}",
                )
                _log(self.command_log, f"operator_confirmation=READY {step.setup_id}")
                if step.requires_output_safety_confirmation:
                    output_phrase = (
                        f"OUTPUT ROUTING VERIFIED {step.setup_id}"
                        if step.optical
                        else f"OUTPUTS DISCONNECTED {step.setup_id}"
                    )
                    _require_phrase(
                        prompt,
                        f"Type {output_phrase} to confirm the stated destination disconnects or approved splitter/device route: ",
                        output_phrase,
                    )
                    _log(
                        self.command_log,
                        f"operator_confirmation={output_phrase}",
                    )
                if step.requires_laser_safety_confirmation:
                    _require_enter_confirmation(
                        prompt,
                        "Laser-area preflight: confirm the room interlock is ready and required protective eyewear is in use. Press Enter to continue, or Ctrl+C to abort: ",
                    )
                    _log(
                        self.command_log,
                        "operator_confirmation=LASER_AREA_PREFLIGHT_ENTER",
                    )

                delays = separations if step.sweep_delays else [0]
                for programmed_delay_ns in delays:
                    safe_idle_counter += 1
                    safe_delay_path = readback_dir / (
                        f"{safe_idle_counter:03d}_safe_idle_before_{step.setup_id}_{_delay_slug(programmed_delay_ns)}.json"
                    )
                    _apply_verified_safe_idle(
                        timing_manager, safe_delay_path, recipe=safe_idle_recipe
                    )
                    readback_paths.append(str(safe_delay_path))

                    capture_settings, timing_validation = _plan_capture_settings(
                        pico,
                        base_capture_settings,
                        programmed_delay_ns=(
                            programmed_delay_ns
                            if step.sweep_delays
                            else (
                                int(math.ceil(float(photodetector_maximum_latency_ns)))
                                if step.optical
                                else 0
                            )
                        ),
                        base_sample_interval_ns=base_interval_ns,
                        trigger_edge=step.reference_edge,
                    )
                    validate_capture_settings(capture_settings, device_config)
                    pico.capture_settings = capture_settings
                    pico.apply_capture_settings()
                    profile_key = f"{step.setup_id}/{programmed_delay_ns}ns"
                    capture_profiles[profile_key] = {
                        "capture_settings": capture_settings,
                        "sample_timing_validation": timing_validation,
                        "required_target_latency_ns": (
                            float(photodetector_maximum_latency_ns)
                            if step.optical
                            else float(programmed_delay_ns)
                        ),
                        "post_trigger_span_ns": _post_trigger_span_ns(
                            capture_settings,
                            float(timing_validation["sample_interval_ns"]),
                        ),
                    }

                    readback_path = readback_dir / (
                        f"{step.setup_id}_{_delay_slug(programmed_delay_ns)}_recipe_readback.json"
                    )
                    if step.optical:
                        optical_result = self._acquire_optical_step(
                            step=step,
                            pico=pico,
                            timing_manager=timing_manager,
                            optical_recipe=effective_optical_recipe,
                            safe_idle_recipe=safe_idle_recipe,
                            raw_dir=raw_dir,
                            readback_dir=readback_dir,
                            shot_count=shot_count,
                            capture_settings=capture_settings,
                            timing_validation=timing_validation,
                            photodetector_threshold_adc=photodetector_threshold_adc,
                            photodetector_minimum_latency_ns=photodetector_minimum_latency_ns,
                            photodetector_maximum_latency_ns=float(
                                photodetector_maximum_latency_ns
                            ),
                            prompt=prompt,
                            emit=emit,
                        )
                        rows.extend(optical_result["rows"])
                        raw_paths.extend(optical_result["raw_paths"])
                        readback_paths.extend(optical_result["readback_paths"])
                        optical_exposure_audit = optical_result["exposure_audit"]
                        _write_rows_replace(
                            result_dir / "per_shot_measurements.csv", rows
                        )
                        continue
                    else:
                        generated_recipe = self.build_step_recipe(
                            step,
                            programmed_delay_ns=programmed_delay_ns,
                        )
                        expected_resolved = plan["recipes"][
                            "resolved_electrical_settings_by_setup_and_delay_ns"
                        ][step.setup_id][str(programmed_delay_ns)]
                        actual_resolved = runtime_recipe_validator.validate_recipe(
                            generated_recipe
                        )["resolved_settings"]
                        if actual_resolved != expected_resolved:
                            raise TimingCalibrationError(
                                f"Generated recipe for {step.setup_id} at {programmed_delay_ns} ns differs from the reviewed plan"
                            )
                        timing_manager.apply_recipe(generated_recipe, output_path=readback_path)
                    readback_paths.append(str(readback_path))

                    for shot_index in range(shot_count):
                        raw_path = raw_dir / step.setup_id / (
                            f"delay_{_delay_slug(programmed_delay_ns)}_shot_{shot_index:03d}.csv"
                        )
                        capture_summary = pico.capture_block(raw_path)
                        raw_paths.append(str(raw_path))
                        interval_ns = float(timing_validation["sample_interval_ns"])
                        measurement = analyze_pico_trace(
                            raw_path,
                            sample_interval_ns=interval_ns,
                            threshold_adc=int(
                                capture_settings.get("pulse_count_threshold_adc", 5000)
                            ),
                            programmed_separation_ns=float(programmed_delay_ns),
                            reference_edge=step.reference_edge,
                            target_edge=step.target_edge,
                        )
                        rows.append(
                            _measurement_row(
                                step,
                                measurement,
                                operator=self.operator,
                                config_hash=self.inventory.config_hash,
                                programmed_delay_ns=programmed_delay_ns,
                                shot_index=shot_index,
                                capture_settings=capture_settings,
                                timing_validation=timing_validation,
                                raw_path=raw_path,
                                capture_summary=capture_summary,
                            )
                        )
                    _write_rows_replace(result_dir / "per_shot_measurements.csv", rows)

                safe_idle_counter += 1
                safe_after_path = readback_dir / f"{safe_idle_counter:03d}_safe_idle_after_{step.setup_id}.json"
                _apply_verified_safe_idle(
                    timing_manager, safe_after_path, recipe=safe_idle_recipe
                )
                readback_paths.append(str(safe_after_path))

            emit(
                "\nFINAL SAFE-IDLE RESTORATION:\n  - "
                + "\n  - ".join(plan["final_restoration"]["instructions"])
            )
            _require_phrase(
                prompt,
                "Type FINAL CABLING RESTORED SAFE after completing the stated restoration with all outputs disabled: ",
                "FINAL CABLING RESTORED SAFE",
            )
            _log(self.command_log, "operator_confirmation=FINAL CABLING RESTORED SAFE")
        except BaseException as exc:  # noqa: BLE001 - finalize hardware before re-raising
            execution_error = exc
        finally:
            final_safe_error: BaseException | None = None
            cleanup_errors: list[BaseException] = []
            try:
                final_safe_path = readback_dir / "999_safe_idle_final.json"
                _apply_verified_safe_idle(
                    timing_manager, final_safe_path, recipe=safe_idle_recipe
                )
                readback_paths.append(str(final_safe_path))
            except BaseException as exc:  # noqa: BLE001 - preserve as highest-priority safety failure
                final_safe_error = exc
            try:
                pico.stop()
            except BaseException as exc:  # noqa: BLE001 - retain without masking safe-idle state
                cleanup_errors.append(exc)
            try:
                pico.close_unit()
            except BaseException as exc:  # noqa: BLE001 - retain without masking safe-idle state
                cleanup_errors.append(exc)
            if final_safe_error is not None:
                for error in ([execution_error] if execution_error is not None else []) + cleanup_errors:
                    final_safe_error.add_note(f"Additional execution/cleanup error: {error}")
                raise final_safe_error
            if execution_error is not None:
                for error in cleanup_errors:
                    execution_error.add_note(f"Additional PicoScope cleanup error: {error}")
                raise execution_error
            if cleanup_errors:
                detail = "; ".join(str(error) for error in cleanup_errors)
                raise TimingCalibrationError(
                    f"PicoScope cleanup failed after verified final safe idle: {detail}"
                )

        if not rows:
            raise TimingCalibrationError("No timing measurements were acquired")
        outputs = consolidate_results(
            rows,
            steps=[MeasurementStep(**item) for item in plan["operator_sequence"]],
            output_dir=result_dir,
            config_hash=self.inventory.config_hash,
            optical_recipe_path=str(_resolve_repo_path(optical_recipe_path)),
            selected_optical_program_ns=effective_optical_recipe[
                "timing_calibration_selected_program_ns"
            ],
            **step7_corrections,
        )
        summary = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "generated_utc": _utc_now(),
            "status": "PASS",
            "operator": self.operator,
            "config_hash": self.inventory.config_hash,
            "run_dir": str(run_path),
            "picoscope_recipe_path": str(resolved_pico_recipe),
            "capture_profiles": capture_profiles,
            "raw_data_paths": raw_paths,
            "device_readback_paths": readback_paths,
            "optical_exposure_audit": optical_exposure_audit,
            "outputs": outputs,
            "publication_status": "RUN_LOCAL_ONLY_NOT_PUBLISHED_TO_RSI_OR_CANONICAL_CALIBRATION",
        }
        summary_path = _write_json_new(run_path / "workflow_summary.json", summary)
        summary["workflow_summary"] = str(summary_path)
        return summary

    def build_step_recipe(
        self,
        step: MeasurementStep,
        *,
        programmed_delay_ns: int,
    ) -> dict[str, Any]:
        """Build a fully specified, sparse-rate electrical recipe for one step."""

        if step.optical:
            raise TimingCalibrationError("TC-07 must use the approved optical recipe")
        active: dict[str, int] = {}
        if step.reference_signal:
            active[step.reference_signal] = 0
        if step.target_signal:
            active[step.target_signal] = int(programmed_delay_ns)
        for dependency in step.dependency_signals:
            active[dependency] = 0
        if not active:
            raise TimingCalibrationError(f"{step.setup_id} has no programmable timing signal")

        involved_units = {
            self.inventory.signal_map[signal]["device"]
            for signal in active
        }
        if "t660_1" in involved_units:
            involved_units.add("t660_2")
        ordered_units = [unit for unit in ("t660_1", "t660_2") if unit in involved_units]
        units: dict[str, dict[str, Any]] = {}
        for unit in ordered_units:
            unit_recipe: dict[str, Any] = {
                "stop_first": True,
                "predivider": 1,
                "gate_mode": 0,
                "burst_enabled": False,
                "trigger_source": "EXT" if unit == "t660_1" else "SYN",
                "external_trigger": {
                    "polarity": "positive",
                    "termination": "50OHM",
                    "threshold_v": 2.0,
                },
                "force_eod": True,
                "start": True,
                "channels": {},
            }
            if unit == "t660_1":
                trigger_input = self.inventory.t660_devices[unit].get(
                    "trigger_input", {}
                )
                unit_recipe["external_trigger"] = {
                    "polarity": str(trigger_input.get("polarity", "positive")),
                    "termination": str(
                        trigger_input.get("termination", "50OHM")
                    ),
                    "threshold_v": float(trigger_input.get("threshold_v", 2.0)),
                }
            if unit == "t660_2":
                unit_recipe["frames_engine"] = "OFF"
                unit_recipe["clock"] = {
                    "frequency": f"{step.trigger_rate_hz}Hz",
                    "shots": 0,
                }
            for channel in ("A", "B", "C", "D"):
                signal = str(
                    (self.inventory.t660_devices.get(unit, {}).get("channel_map") or {}).get(
                        channel, channel
                    )
                )
                if signal in active:
                    ndyag_signal = signal in {"ndyag_fire", "ndyag_q_switch"}
                    process_trigger = signal == "mircat_db9_pin_4_process_trigger"
                    width = (
                        "10ms"
                        if process_trigger
                        else "10us"
                        if signal == "t660_1_trig_in" or ndyag_signal
                        else "150ns"
                    )
                    unit_recipe["channels"][channel] = {
                        "timing_mode": "delay_width",
                        "delay": f"{active[signal]}ns",
                        "width": width,
                        "polarity": (
                            "negative"
                            if ndyag_signal or process_trigger
                            else "positive"
                        ),
                        "termination": "50OHM",
                        "enabled": True,
                        "signal": signal,
                    }
                else:
                    process_trigger = signal == "mircat_db9_pin_4_process_trigger"
                    unit_recipe["channels"][channel] = {
                        "timing_mode": "delay_width",
                        "delay": "0ns",
                        "width": "10ms" if process_trigger else "150ns",
                        "polarity": "negative" if process_trigger else "positive",
                        "termination": "50OHM",
                        "enabled": False,
                        "signal": signal,
                    }
            units[unit] = unit_recipe
        return {
            "name": f"timing_calibration_{step.setup_id}_{_delay_slug(programmed_delay_ns)}",
            "description": "Generated electrical-only calibration recipe; destination disconnect confirmed interactively before application.",
            "approved_laser_safety_condition": bool(step.requires_output_safety_confirmation),
            "direct_laser_emission_api_commands_sent": False,
            "laser_driving_ttl_outputs_enabled": bool(
                step.requires_output_safety_confirmation
            ),
            "laser_driving_ttl_destination_state": "physically disconnected and operator-confirmed",
            "measurement_id": step.measurement_id,
            "trigger_rate_hz": step.trigger_rate_hz,
            "t660": units,
        }

    def _acquire_optical_step(
        self,
        *,
        step: MeasurementStep,
        pico: PicoScopeService,
        timing_manager: TimingRecipeManager,
        optical_recipe: dict[str, Any],
        safe_idle_recipe: dict[str, Any],
        raw_dir: Path,
        readback_dir: Path,
        shot_count: int,
        capture_settings: dict[str, Any],
        timing_validation: dict[str, Any],
        photodetector_threshold_adc: int,
        photodetector_minimum_latency_ns: float,
        photodetector_maximum_latency_ns: float,
        prompt: Callable[[str], str],
        emit: Callable[[str], None],
    ) -> dict[str, Any]:
        """Acquire one blocked control, one preview, then bounded accepted shots."""

        interval_ns = float(timing_validation["sample_interval_ns"])
        pre_trigger = int(capture_settings["pre_trigger_samples"])
        reference_threshold = int(
            capture_settings.get("pulse_count_threshold_adc", 5000)
        )
        audit_path = readback_dir / "step_7_optical_exposure_audit.json"
        audit: dict[str, Any] = {
            "status": "IN_PROGRESS",
            "policy": {
                "trigger_source": "T660-2 REM",
                "beam_blocked_control_shots": 1,
                "preview_shots": 1,
                "accepted_measurement_shots": int(shot_count),
                "maximum_total_remote_shots": int(shot_count) + 2,
                "scope_armed_before_each_trigger": True,
                "minimum_inter_shot_interval_s_across_all_phases": (
                    1.0 / float(step.trigger_rate_hz)
                ),
            },
            "segments": [],
            "remote_trigger_commands": 0,
            "accepted_measurement_traces": 0,
            "rejected_measurement_traces": 0,
            "observed_inter_shot_intervals_s": [],
        }
        raw_paths: list[str] = []
        readback_paths: list[str] = []
        measurement_rows: list[dict[str, Any]] = []
        last_remote_fire_monotonic: float | None = None
        minimum_remote_interval_s = 1.0 / float(step.trigger_rate_hz)

        def persist_audit() -> None:
            _write_json_replace(audit_path, audit)

        def apply_optical(label: str) -> None:
            path = readback_dir / f"step_7_{label}_remote_recipe_readback.json"
            timing_manager.apply_recipe(optical_recipe, output_path=path)
            readback_paths.append(str(path))

        def safe_idle(label: str) -> None:
            path = readback_dir / f"step_7_safe_idle_after_{label}.json"
            _apply_verified_safe_idle(
                timing_manager, path, recipe=safe_idle_recipe
            )
            readback_paths.append(str(path))

        def remote_batch(
            label: str,
            count: int,
            callback: Callable[[int, Path, dict[str, Any]], None],
        ) -> None:
            controller = self._make_remote_shot_controller()
            trigger_commands = 0
            counts: dict[str, int] | None = None
            error: BaseException | None = None
            opened = False
            try:
                controller.open()
                opened = True
                controller.reset_counters()
                for index in range(count):
                    raw_path = raw_dir / step.setup_id / f"{label}_shot_{index:03d}.csv"

                    def fire() -> None:
                        nonlocal trigger_commands, last_remote_fire_monotonic
                        if last_remote_fire_monotonic is not None:
                            while True:
                                now = time.monotonic()
                                remaining = minimum_remote_interval_s - (
                                    now - last_remote_fire_monotonic
                                )
                                if remaining <= 0:
                                    break
                                time.sleep(remaining)
                        controller.fire_once()
                        fired_at = time.monotonic()
                        if last_remote_fire_monotonic is not None:
                            audit["observed_inter_shot_intervals_s"].append(
                                fired_at - last_remote_fire_monotonic
                            )
                        last_remote_fire_monotonic = fired_at
                        trigger_commands += 1
                        audit["remote_trigger_commands"] = int(
                            audit["remote_trigger_commands"]
                        ) + 1

                    capture_summary = pico.capture_block(raw_path, after_arm=fire)
                    raw_paths.append(str(raw_path))
                    audit["raw_trace_paths"] = list(raw_paths)
                    callback(index, raw_path, capture_summary)
                counts = controller.read_counts()
            except BaseException as exc:  # noqa: BLE001 - close ports and preserve exact failure
                error = exc
                if opened:
                    try:
                        counts = controller.read_counts()
                    except Exception as count_exc:  # noqa: BLE001
                        audit.setdefault("counter_read_errors", []).append(str(count_exc))
            finally:
                try:
                    controller.close()
                except Exception as close_exc:  # noqa: BLE001
                    audit.setdefault("controller_close_errors", []).append(
                        str(close_exc)
                    )
                    if error is None:
                        error = close_exc
                audit["segments"].append(
                    {
                        "label": label,
                        "requested_shots": int(count),
                        "remote_trigger_commands": int(trigger_commands),
                        "t660_elapsed_shot_counts": counts,
                    }
                )
                persist_audit()
            if error is not None:
                raise error
            expected_counts = {"t660_1": int(count), "t660_2": int(count)}
            if counts != expected_counts or trigger_commands != count:
                raise TimingCalibrationError(
                    f"Step 7 exposure audit mismatch for {label}: commands={trigger_commands}, counters={counts}, expected={expected_counts}"
                )

        try:
            _require_phrase(
                prompt,
                "Type BEAM BLOCKED CONTROL READY STEP 7 after placing the approved beam block/dump before the detector: ",
                "BEAM BLOCKED CONTROL READY STEP 7",
            )
            _log(self.command_log, "operator_confirmation=BEAM BLOCKED CONTROL READY STEP 7")
            apply_optical("beam_blocked_control")

            def inspect_control(
                _index: int,
                raw_path: Path,
                _capture_summary: dict[str, Any],
            ) -> None:
                audit["beam_blocked_control"] = analyze_beam_blocked_control(
                    raw_path,
                    sample_interval_ns=interval_ns,
                    pre_trigger_samples=pre_trigger,
                    reference_threshold_adc=reference_threshold,
                    reference_edge=step.reference_edge,
                    target_threshold_adc=int(photodetector_threshold_adc),
                    target_edge=step.target_edge,
                    minimum_latency_ns=float(photodetector_minimum_latency_ns),
                    maximum_latency_ns=float(photodetector_maximum_latency_ns),
                )

            remote_batch("beam_blocked_control", 1, inspect_control)
            safe_idle("beam_blocked_control")
            control = audit["beam_blocked_control"]
            emit(
                "STEP 7 BEAM-BLOCKED CONTROL PASSED: "
                f"detector edges={int(control['detector_edge_count'])}, "
                f"peak={int(control['detector_peak_abs_adc'])} ADC, "
                f"noise={float(control['detector_baseline_noise_adc']):.3g} ADC; "
                "outputs are safe-idled."
            )

            _require_phrase(
                prompt,
                "Type BEAM UNBLOCKED PREVIEW READY STEP 7 after restoring the approved attenuated sample-position path: ",
                "BEAM UNBLOCKED PREVIEW READY STEP 7",
            )
            _log(self.command_log, "operator_confirmation=BEAM UNBLOCKED PREVIEW READY STEP 7")
            apply_optical("preview")

            def inspect_preview(
                _index: int,
                raw_path: Path,
                _capture_summary: dict[str, Any],
            ) -> None:
                audit["preview"] = analyze_optical_trace(
                    raw_path,
                    sample_interval_ns=interval_ns,
                    pre_trigger_samples=pre_trigger,
                    reference_threshold_adc=reference_threshold,
                    reference_edge=step.reference_edge,
                    target_threshold_adc=int(photodetector_threshold_adc),
                    target_edge=step.target_edge,
                    minimum_latency_ns=float(photodetector_minimum_latency_ns),
                    maximum_latency_ns=float(photodetector_maximum_latency_ns),
                    blocked_control=audit["beam_blocked_control"],
                )

            remote_batch("preview", 1, inspect_preview)
            safe_idle("preview")
            preview = audit["preview"]
            emit(
                "STEP 7 PREVIEW PASSED: "
                f"delay={float(preview['measured_separation_ns']):.6g} ns, "
                f"peak={int(preview['photodetector_peak_abs_adc'])} ADC, "
                f"noise={float(preview['photodetector_baseline_noise_adc']):.3g} ADC, "
                "outputs are safe-idled."
            )
            _require_phrase(
                prompt,
                "Type OPTICAL PREVIEW ACCEPTED STEP 7 to approve the displayed acquired preview before measurement shots: ",
                "OPTICAL PREVIEW ACCEPTED STEP 7",
            )
            _log(self.command_log, "operator_confirmation=OPTICAL PREVIEW ACCEPTED STEP 7")

            apply_optical("measurement")

            def inspect_measurement(
                shot_index: int,
                raw_path: Path,
                capture_summary: dict[str, Any],
            ) -> None:
                try:
                    measurement = analyze_optical_trace(
                        raw_path,
                        sample_interval_ns=interval_ns,
                        pre_trigger_samples=pre_trigger,
                        reference_threshold_adc=reference_threshold,
                        reference_edge=step.reference_edge,
                        target_threshold_adc=int(photodetector_threshold_adc),
                        target_edge=step.target_edge,
                        minimum_latency_ns=float(photodetector_minimum_latency_ns),
                        maximum_latency_ns=float(photodetector_maximum_latency_ns),
                        blocked_control=audit["beam_blocked_control"],
                    )
                except Exception:
                    audit["rejected_measurement_traces"] = int(
                        audit["rejected_measurement_traces"]
                    ) + 1
                    raise
                measurement_rows.append(
                    _measurement_row(
                        step,
                        measurement,
                        operator=self.operator,
                        config_hash=self.inventory.config_hash,
                        programmed_delay_ns=0,
                        shot_index=shot_index,
                        capture_settings=capture_settings,
                        timing_validation=timing_validation,
                        raw_path=raw_path,
                        capture_summary=capture_summary,
                    )
                )
                audit["accepted_measurement_traces"] = int(
                    audit["accepted_measurement_traces"]
                ) + 1

            remote_batch("measurement", shot_count, inspect_measurement)
            safe_idle("measurement")
            expected_raw_count = int(shot_count) + 2
            if (
                len(raw_paths) != expected_raw_count
                or int(audit["accepted_measurement_traces"]) != int(shot_count)
            ):
                raise TimingCalibrationError(
                    "Step 7 trace-budget closure failed: "
                    f"raw={len(raw_paths)}/{expected_raw_count}, "
                    f"accepted={audit['accepted_measurement_traces']}/{shot_count}"
                )
            observed_intervals = [
                float(value)
                for value in audit["observed_inter_shot_intervals_s"]
            ]
            if observed_intervals and min(observed_intervals) < (
                minimum_remote_interval_s - 1e-6
            ):
                raise TimingCalibrationError(
                    "Step 7 cross-phase remote-shot rate audit failed: "
                    f"minimum observed interval {min(observed_intervals):.6g} s is below "
                    f"{minimum_remote_interval_s:.6g} s"
                )
            audit["status"] = "PASS_EXPOSURE_AND_TRACE_AUDIT"
            audit["completed_utc"] = _utc_now()
            persist_audit()
        except BaseException as exc:  # noqa: BLE001 - preserve audit and force an extra safe idle
            audit["status"] = "BLOCKED"
            audit["error"] = str(exc)
            audit["stopped_utc"] = _utc_now()
            persist_audit()
            try:
                safe_idle("blocked")
            except Exception as safe_exc:  # noqa: BLE001
                raise SafeIdleVerificationError(
                    f"Step 7 failed and the immediate safe-idle also failed: {safe_exc}"
                ) from safe_exc
            raise

        return {
            "rows": measurement_rows,
            "raw_paths": raw_paths,
            "readback_paths": readback_paths + [str(audit_path)],
            "exposure_audit": audit,
        }

    def _make_timing_manager(self) -> TimingRecipeManager:
        try:
            return self._timing_manager_factory(
                self.inventory,
                command_log=self.command_log,
            )
        except TypeError:
            return self._timing_manager_factory()  # type: ignore[call-arg]

    def _make_pico(
        self,
        device_config: dict[str, Any],
        capture_settings: dict[str, Any],
    ) -> PicoScopeService:
        try:
            return self._pico_factory(
                device_config,
                capture_settings,
                command_log=self.command_log,
            )
        except TypeError:
            return self._pico_factory()  # type: ignore[call-arg]

    def _make_remote_shot_controller(self) -> RemoteShotController:
        try:
            return self._remote_shot_controller_factory(
                inventory=self.inventory,
                command_log=self.command_log,
                minimum_interval_s=1.0 / T660_1_TRIGGER_RATE_HZ,
            )
        except TypeError:
            return self._remote_shot_controller_factory()  # type: ignore[call-arg]


def create_unique_run_directory(
    *,
    run_parent: str | Path = REPO_ROOT / "calibration",
    requested_path: str | Path | None = None,
) -> Path:
    """Create an exclusive run directory; existing paths are never reused."""

    if requested_path is not None:
        target = Path(requested_path)
        if not target.is_absolute():
            target = REPO_ROOT / target
        target.mkdir(parents=True, exist_ok=False)
        return target.resolve()
    parent = Path(run_parent)
    if not parent.is_absolute():
        parent = REPO_ROOT / parent
    parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    for _ in range(100):
        candidate = parent / f"{timestamp}_timing_calibration_{uuid.uuid4().hex[:8]}"
        try:
            candidate.mkdir(exist_ok=False)
            return candidate.resolve()
        except FileExistsError:
            continue
    raise TimingCalibrationError("Could not allocate a unique timing-calibration run directory")


def render_plan_markdown(plan: dict[str, Any]) -> str:
    """Render the JSON plan as a human-reviewable cable procedure."""

    lines = [
        "# Pump-probe timing calibration plan",
        "",
        f"Status: **{plan['status']}**  ",
        f"Generated: {plan['generated_utc']}  ",
        f"Operator: {plan['operator']}  ",
        f"Configuration hash: `{plan['config_hash']}`",
        "",
        "No hardware is opened by plan generation. No RSI draft or canonical calibration file is updated.",
        "",
        "## Time and sign conventions",
        "",
        f"- {plan['time_origins']['t_master']}",
        f"- {plan['time_origins']['t_chem']}",
        f"- {plan['sign_convention']}",
        "",
    ]
    if plan.get("prehardware_blockers"):
        lines.extend(["## Prehardware blockers", ""])
        lines.extend(f"- {item}" for item in plan["prehardware_blockers"])
        lines.append("")
    lines.extend(
        [
            "## Frozen execution inputs",
            "",
            f"- Workflow SHA-256: `{plan['implementation']['workflow_sha256']}`",
            f"- Procedure document SHA-256: `{plan['implementation']['procedure_document_sha256']}`",
            f"- Hardware configuration SHA-256: `{plan['configuration_files']['hardware_configuration']['sha256']}`",
            f"- Wiring map SHA-256: `{plan['configuration_files']['wiring_map']['sha256']}`",
            f"- Procedure-base recipe SHA-256: `{plan['recipes']['procedure_base']['sha256']}`",
            f"- Safe-idle recipe SHA-256: `{plan['recipes']['safe_idle']['sha256']}`",
            f"- PicoScope recipe: `{plan['recipes']['picoscope']['path']}`; SHA-256 `{plan['recipes']['picoscope']['sha256']}`",
            f"- Optical recipe: `{plan['recipes']['optical']['path']}`; source SHA-256 `{plan['recipes']['optical']['source_sha256']}`; effective REM recipe SHA-256 `{plan['recipes']['optical']['effective_recipe_sha256']}`",
            f"- Maximum samples per raw trace: {plan['capture_policy']['maximum_samples_per_trace']}",
            f"- PicoScope timebase uncertainty source/status: {plan['analysis']['timebase_accuracy_source']}; {plan['analysis']['timebase_annual_drift_status']}",
            f"- T660 delay-scale status: {plan['analysis']['t660_programmed_delay_specification_status']}",
            f"- Optical exposure ceiling: {plan['optical_exposure_policy']['maximum_total_remote_shots']} remote shots ({plan['optical_exposure_policy']['beam_blocked_control_shots']} blocked control + {plan['optical_exposure_policy']['live_safety_preview_shots']} preview + {plan['optical_exposure_policy']['accepted_measurement_shots_after_preview']} measurement).",
            f"- Step 7 load-equivalence method: {plan['photodetector']['step7_qswitch_load_equivalence_method'] or 'UNRESOLVED'}",
            f"- Step 7 load-equivalence standard uncertainty: {plan['photodetector']['step7_qswitch_load_equivalence_standard_uncertainty_ns'] if plan['photodetector']['step7_qswitch_load_equivalence_standard_uncertainty_ns'] is not None else 'UNRESOLVED'} ns",
            f"- Detector/path record: {plan['photodetector']['detector_identifier'] or 'UNRESOLVED'}; cable {plan['photodetector']['detector_cable_identifier'] or 'UNRESOLVED'}; {plan['photodetector']['sample_or_equivalent_path_description'] or 'UNRESOLVED'}",
            f"- Detector response correction/source/date: {plan['photodetector']['response_delay_correction_ns']} ns ± {plan['photodetector']['response_delay_standard_uncertainty_ns']} ns; {plan['photodetector']['response_characterization_source'] or 'UNRESOLVED'}; {plan['photodetector']['response_characterization_date'] or 'UNRESOLVED'}",
            f"- Optical edge/threshold/saturation/reviewed latency window: {plan['photodetector']['edge']}; {plan['photodetector']['threshold_adc']} ADC; {plan['photodetector']['saturation_reject_adc']} ADC; {plan['photodetector']['minimum_accepted_latency_after_qswitch_ns']} to {plan['photodetector']['maximum_accepted_latency_after_qswitch_ns']} ns; blocked-control amplitude comparison required",
            f"- Measurement assemblies: {plan['photodetector']['measurement_assembly_record'] or 'UNRESOLVED'}",
            "",
            "### Effective safe-idle T660 settings",
            "",
            "```yaml",
            yaml.safe_dump(
                plan["recipes"]["safe_idle"]["resolved_settings"],
                sort_keys=False,
            ).rstrip(),
            "```",
            "",
            "### Effective Step 7 T660 settings",
            "",
            "```yaml",
            yaml.safe_dump(
                plan["recipes"]["optical"]["resolved_settings"],
                sort_keys=False,
            ).rstrip(),
            "```",
            "",
            "### Electrical recipe review summary",
            "",
            "| Setup | Measurement | Programmed delays (ns) | Trigger sources | Enabled outputs at first delay | Explicitly disabled outputs |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in plan["recipes"]["electrical_review_summary"]:
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    item["setup_id"],
                    item["measurement_id"],
                    ", ".join(str(value) for value in item["programmed_delays_ns"]),
                    ", ".join(
                        f"{unit}={source}"
                        for unit, source in item["trigger_sources"].items()
                    ),
                    "; ".join(item["enabled_outputs_at_first_delay"]),
                    "; ".join(item["disabled_outputs"]),
                )
            )
            + " |"
        )
    lines.append("")
    lines.extend(["## Sequential cable procedure", ""])
    for data in plan["operator_sequence"]:
        step = MeasurementStep(**data)
        lines.extend(
            [
                f"### Step {step.step}: {step.title} ({step.measurement_id})",
                "",
                step.purpose,
                "",
                f"- PicoScope CHA: {step.pico_ch_a}",
                f"- PicoScope CHB: {step.pico_ch_b}",
                "- Disconnect: " + " ".join(step.disconnect),
                "- Remains connected: " + " ".join(step.remains_connected),
                f"- Trigger rate: {step.trigger_rate_hz} Hz",
                f"- Programmed-delay mode: {step.programmed_delay_mode}",
                f"- Uses final wiring: {'yes' if step.uses_final_wiring else 'no'}",
                f"- Splitter: {'yes' if step.splitter_used else 'no'}; {step.splitter_mapping}",
                f"- Correction: {step.correction_rule}",
                f"- Use in timing recipe: {step.recipe_use_condition or ('yes' if step.use_in_timing_recipe else 'no')}",
                f"- RSI/thesis label: {step.reporting_label}",
                f"- Notes: {step.notes}",
                "",
            ]
        )
    lines.extend(
        [
            "### Final safe-idle restoration",
            "",
            *(
                f"- {instruction}"
                for instruction in plan["final_restoration"]["instructions"]
            ),
            f"- Required phrase: `{plan['final_restoration']['required_phrase']}`",
            "",
        ]
    )
    lines.extend(
        [
            "## Analysis and outputs",
            "",
            "Electrical sweeps use 0 ns, 100 ns, 1 us, 10 us, 100 us, and 1 ms. The scope window grows automatically for each delay.",
            "Fit corrected measured delay versus programmed delay. Report the intercept as fixed offset and `(slope - 1) * 1e6` as ppm; never use the 1 ms residual as fixed cable delay.",
            "Run-local outputs include per-shot data, per-delay statistics, measurement-system corrections, a consolidated CSV/Markdown/YAML table, derived recipe corrections, readbacks, and raw traces.",
            "",
        ]
    )
    return "\n".join(lines)


def format_operator_prompt(
    step: MeasurementStep,
    *,
    plan: dict[str, Any] | None = None,
) -> str:
    """Return the exact setup block printed before operator confirmation."""

    disconnect = "\n".join(f"  - {item}" for item in step.disconnect)
    remains = "\n".join(f"  - {item}" for item in step.remains_connected)
    frozen_details: list[str] = []
    if plan is not None and step.step in {"0c", "7"}:
        detector = plan["photodetector"]
        frozen_details.extend(
            [
                f"Measurement assemblies: {detector['measurement_assembly_record']}",
                f"Q-switch load equivalence: {detector['step7_qswitch_load_equivalence_method']} (standard uncertainty {detector['step7_qswitch_load_equivalence_standard_uncertainty_ns']} ns)",
            ]
        )
    if plan is not None and step.step == "7":
        detector = plan["photodetector"]
        selected = plan["recipes"]["optical"]["selected_program_ns"]
        frozen_details.extend(
            [
                f"Detector/cable: {detector['detector_identifier']} / {detector['detector_cable_identifier']}",
                f"Detector plane/path: {detector['sample_or_equivalent_path_description']} (standard uncertainty {detector['sample_path_standard_uncertainty_ns']} ns)",
                f"Detector response correction: {detector['response_delay_correction_ns']} ns (standard uncertainty {detector['response_delay_standard_uncertainty_ns']} ns), source {detector['response_characterization_source']}, dated {detector['response_characterization_date']}",
                f"Optical discriminator: {detector['edge']} edge at {detector['threshold_adc']} ADC; saturation reject {detector['saturation_reject_adc']} ADC; reviewed Q-to-OPO window {detector['minimum_accepted_latency_after_qswitch_ns']} to {detector['maximum_accepted_latency_after_qswitch_ns']} ns; blocked-control amplitude comparison required",
                f"Frozen optical program: FIRE {selected['fire_delay_ns']} ns; Q-switch {selected['q_switch_delay_ns']} ns; FIRE-to-Q {selected['fire_to_q_switch_programmed_ns']} ns; T660-1 EXT, T660-2 REM",
            ]
        )
    frozen_block = (
        "\nFrozen setup values:\n"
        + "\n".join(f"  - {item}" for item in frozen_details)
        if frozen_details
        else ""
    )
    return (
        f"\n{'=' * 78}\n"
        f"STEP {step.step} / {step.measurement_id}: {step.title}\n"
        f"Purpose: {step.purpose}\n"
        f"PicoScope CHA: {step.pico_ch_a}\n"
        f"PicoScope CHB: {step.pico_ch_b}\n"
        f"Disconnect:\n{disconnect}\n"
        f"Remains connected:\n{remains}\n"
        f"Rate: {step.trigger_rate_hz} Hz; splitter: {'yes' if step.splitter_used else 'no'}\n"
        f"{frozen_block}\n"
        f"{'=' * 78}"
    )


def analyze_optical_trace(
    raw_csv_path: str | Path,
    *,
    sample_interval_ns: float,
    pre_trigger_samples: int,
    reference_threshold_adc: int,
    reference_edge: str,
    target_threshold_adc: int,
    target_edge: str,
    minimum_latency_ns: float = DEFAULT_OPTICAL_MINIMUM_LATENCY_NS,
    maximum_latency_ns: float | None = None,
    blocked_control: dict[str, Any] | None = None,
    saturation_adc: int = 30_000,
    minimum_signal_to_noise: float = 5.0,
) -> dict[str, Any]:
    """Measure one optical edge in the reviewed window and reject unsafe traces."""

    samples_a, samples_b = _read_trace_channels(raw_csv_path)
    if not samples_a or not samples_b:
        raise TimingCalibrationError(f"No samples found in {raw_csv_path}")
    if maximum_latency_ns is not None and float(maximum_latency_ns) <= float(
        minimum_latency_ns
    ):
        raise TimingCalibrationError(
            "Optical maximum latency must be greater than the minimum latency"
        )
    peak_abs = max(abs(value) for value in samples_b)
    if peak_abs >= saturation_adc:
        raise TimingCalibrationError(
            f"Photodetector trace saturated ({peak_abs} ADC counts) in {raw_csv_path}; increase attenuation before continuing."
        )
    baseline_stop = max(10, min(pre_trigger_samples // 2, len(samples_b) // 10))
    baseline = samples_b[:baseline_stop]
    baseline_mean = statistics.fmean(baseline)
    baseline_noise = statistics.pstdev(baseline) if len(baseline) > 1 else 0.0
    signal_excursion = max(abs(value - baseline_mean) for value in samples_b)
    required_excursion = max(100.0, minimum_signal_to_noise * max(baseline_noise, 1.0))
    if signal_excursion < required_excursion:
        raise TimingCalibrationError(
            f"Photodetector signal-to-noise check failed in {raw_csv_path}: excursion {signal_excursion:.1f}, required {required_excursion:.1f} ADC counts."
        )
    if blocked_control is not None:
        control_excursion = float(
            blocked_control.get("detector_signal_excursion_adc", 0.0) or 0.0
        )
        control_noise = float(
            blocked_control.get("detector_baseline_noise_adc", 0.0) or 0.0
        )
        control_like_limit = control_excursion + 5.0 * max(
            control_noise,
            baseline_noise,
            1.0,
        )
        if signal_excursion <= control_like_limit:
            raise TimingCalibrationError(
                f"Photodetector trace is control-like in {raw_csv_path}: excursion "
                f"{signal_excursion:.1f} ADC is not above the blocked-control limit "
                f"{control_like_limit:.1f} ADC."
            )
    reference_edges = _edge_indices(samples_a, reference_threshold_adc, reference_edge)
    target_edges = _edge_indices(samples_b, target_threshold_adc, target_edge)
    reference_index = min(reference_edges, key=lambda value: abs(value - pre_trigger_samples))
    minimum_target_index = reference_index + float(minimum_latency_ns) / sample_interval_ns
    maximum_target_index = (
        reference_index + float(maximum_latency_ns) / sample_interval_ns
        if maximum_latency_ns is not None
        else math.inf
    )
    target_candidates = [
        value
        for value in target_edges
        if minimum_target_index <= value <= maximum_target_index
    ]
    if not target_candidates:
        window_text = (
            f" between {minimum_latency_ns:g} and {maximum_latency_ns:g} ns"
            if maximum_latency_ns is not None
            else f" by at least {minimum_latency_ns:g} ns"
        )
        raise TimingCalibrationError(
            f"No {target_edge} photodetector edge followed the Q-switch{window_text} in {raw_csv_path}"
        )
    if len(target_candidates) != 1:
        raise TimingCalibrationError(
            f"Ambiguous photodetector trace in {raw_csv_path}: {len(target_candidates)} "
            "threshold edges fall inside the reviewed optical search window"
        )
    target_index = target_candidates[0]
    measured_ns = (target_index - reference_index) * sample_interval_ns
    threshold_delta = max(100, int(round(abs(target_threshold_adc) * 0.10)))
    sensitivity_delays: list[float] = []
    for varied_threshold in (
        max(-32767, target_threshold_adc - threshold_delta),
        min(32767, target_threshold_adc + threshold_delta),
    ):
        varied_edges = _edge_indices(samples_b, varied_threshold, target_edge)
        varied_candidates = [
            value
            for value in varied_edges
            if minimum_target_index <= value <= maximum_target_index
        ]
        if len(varied_candidates) != 1:
            raise TimingCalibrationError(
                f"Photodetector threshold-sensitivity check found {len(varied_candidates)} in-window edges at {varied_threshold} ADC in {raw_csv_path}"
            )
        sensitivity_delays.append(
            (min(varied_candidates) - reference_index) * sample_interval_ns
        )
    threshold_half_range_ns = max(
        abs(value - measured_ns) for value in sensitivity_delays
    )
    return {
        "reference_edge_time_ns": reference_index * sample_interval_ns,
        "target_edge_time_ns": target_index * sample_interval_ns,
        "measured_separation_ns": measured_ns,
        "residual_ns": measured_ns,
        "reference_edge_count": len(reference_edges),
        "target_edge_count": len(target_edges),
        "photodetector_peak_abs_adc": peak_abs,
        "photodetector_baseline_mean_adc": baseline_mean,
        "photodetector_baseline_noise_adc": baseline_noise,
        "photodetector_signal_excursion_adc": signal_excursion,
        "photodetector_minimum_latency_ns": float(minimum_latency_ns),
        "photodetector_maximum_latency_ns": (
            float(maximum_latency_ns) if maximum_latency_ns is not None else None
        ),
        "blocked_control_comparison_applied": blocked_control is not None,
        "photodetector_threshold_sensitivity_half_range_ns": threshold_half_range_ns,
        "photodetector_threshold_sensitivity_standard_uncertainty_ns": (
            threshold_half_range_ns / math.sqrt(3.0)
        ),
        "photodetector_saturated": False,
    }


def analyze_beam_blocked_control(
    raw_csv_path: str | Path,
    *,
    sample_interval_ns: float,
    pre_trigger_samples: int,
    reference_threshold_adc: int,
    reference_edge: str,
    target_threshold_adc: int,
    target_edge: str,
    minimum_latency_ns: float = DEFAULT_OPTICAL_MINIMUM_LATENCY_NS,
    maximum_latency_ns: float | None = None,
    saturation_adc: int = 30_000,
) -> dict[str, Any]:
    """Require a Q-switch edge but no delayed detector edge with the beam blocked."""

    samples_a, samples_b = _read_trace_channels(raw_csv_path)
    if not samples_a or not samples_b:
        raise TimingCalibrationError(f"No samples found in {raw_csv_path}")
    if maximum_latency_ns is not None and float(maximum_latency_ns) <= float(
        minimum_latency_ns
    ):
        raise TimingCalibrationError(
            "Optical maximum latency must be greater than the minimum latency"
        )
    peak_abs = max(abs(value) for value in samples_b)
    if peak_abs >= saturation_adc:
        raise TimingCalibrationError(
            f"Beam-blocked detector control saturated ({peak_abs} ADC counts) in {raw_csv_path}"
        )
    reference_edges = _edge_indices(samples_a, reference_threshold_adc, reference_edge)
    reference_index = min(reference_edges, key=lambda value: abs(value - pre_trigger_samples))
    try:
        target_edges = _edge_indices(samples_b, target_threshold_adc, target_edge)
    except TimingCalibrationError:
        target_edges = []
    minimum_target_index = reference_index + float(minimum_latency_ns) / sample_interval_ns
    maximum_target_index = (
        reference_index + float(maximum_latency_ns) / sample_interval_ns
        if maximum_latency_ns is not None
        else math.inf
    )
    delayed_edges = [
        value
        for value in target_edges
        if minimum_target_index <= value <= maximum_target_index
    ]
    if delayed_edges:
        first_delay_ns = (min(delayed_edges) - reference_index) * sample_interval_ns
        raise TimingCalibrationError(
            "Beam-blocked control contains a delayed photodetector-threshold edge "
            f"at {first_delay_ns:.6g} ns; treat this as EMI/crosstalk and do not accept optical data"
        )
    baseline_stop = max(10, min(pre_trigger_samples // 2, len(samples_b) // 10))
    baseline = samples_b[:baseline_stop]
    baseline_mean = statistics.fmean(baseline)
    baseline_noise = statistics.pstdev(baseline) if len(baseline) > 1 else 0.0
    signal_excursion = max(abs(value - baseline_mean) for value in samples_b)
    return {
        "status": "PASS_NO_DELAYED_OPTICAL_EDGE",
        "reference_edge_count": len(reference_edges),
        "detector_edge_count": len(target_edges),
        "detector_peak_abs_adc": peak_abs,
        "detector_baseline_mean_adc": baseline_mean,
        "detector_baseline_noise_adc": baseline_noise,
        "detector_signal_excursion_adc": signal_excursion,
        "minimum_latency_ns": float(minimum_latency_ns),
        "maximum_latency_ns": (
            float(maximum_latency_ns) if maximum_latency_ns is not None else None
        ),
    }


def _read_trace_channels(raw_csv_path: str | Path) -> tuple[list[int], list[int]]:
    samples_a: list[int] = []
    samples_b: list[int] = []
    with Path(raw_csv_path).open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            samples_a.append(int(row["ch_a_adc"]))
            samples_b.append(int(row["ch_b_adc"]))
    return samples_a, samples_b


def derive_measurement_system_corrections(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Derive scope B-A and splitter branch2-branch1 corrections from Step 0."""

    normal = [float(row["measured_separation_ns"]) for row in rows if row["measurement_id"] == "MS-00A"]
    swapped = [float(row["measured_separation_ns"]) for row in rows if row["measurement_id"] == "MS-00B"]
    installed = [
        float(row["measured_separation_ns"])
        for row in rows
        if row["measurement_id"] == "MS-00C"
    ]
    if not normal or not swapped or not installed:
        raise TimingCalibrationError(
            "Step 0 normal, swapped, and installed-geometry measurements are all required"
        )
    normal_mean = statistics.fmean(normal)
    swapped_mean = statistics.fmean(swapped)
    normal_sem = _standard_error(normal)
    swapped_sem = _standard_error(swapped)
    installed_mean = statistics.fmean(installed)
    installed_sem = _standard_error(installed)
    sample_intervals = [
        float(row.get("sample_interval_ns", 0.0) or 0.0)
        for row in rows
        if str(row.get("measurement_id", "")).startswith("MS-00")
    ]
    step0_resolution_uncertainty = (
        max(sample_intervals) / math.sqrt(6.0) if sample_intervals else 0.0
    )
    derived_uncertainty = math.sqrt(
        normal_sem**2
        + swapped_sem**2
        + 2.0 * step0_resolution_uncertainty**2
    ) / 2.0
    scope_splitter_covariance_ns2 = (normal_sem**2 - swapped_sem**2) / 4.0
    scope_variance = derived_uncertainty**2
    installed_geometry = installed_mean - (normal_mean + swapped_mean) / 2.0
    installed_geometry_uncertainty = math.sqrt(
        installed_sem**2
        + step0_resolution_uncertainty**2
        + scope_variance
    )
    return {
        "sign_convention": "B minus A; splitter branch 2 minus branch 1",
        "normal_mean_b_minus_a_ns": normal_mean,
        "swapped_mean_b_minus_a_ns": swapped_mean,
        "scope_channel_and_fixed_lead_b_minus_a_ns": (normal_mean + swapped_mean) / 2.0,
        "splitter_branch_2_minus_1_ns": (normal_mean - swapped_mean) / 2.0,
        "installed_orientation_mean_b_minus_a_ns": installed_mean,
        "installed_step7_branch_2_monitor_minus_branch_1_qswitch_ns": installed_geometry,
        "installed_step7_geometry_standard_uncertainty_ns": installed_geometry_uncertainty,
        "scope_installed_step7_geometry_covariance_ns2": -scope_variance,
        "installed_orientation_standard_error_ns": installed_sem,
        "scope_correction_standard_uncertainty_ns": derived_uncertainty,
        "splitter_correction_standard_uncertainty_ns": derived_uncertainty,
        "scope_splitter_covariance_ns2": scope_splitter_covariance_ns2,
        "step0_sample_resolution_standard_uncertainty_ns": step0_resolution_uncertainty,
        "normal_jitter_std_ns": _sample_std(normal),
        "swapped_jitter_std_ns": _sample_std(swapped),
        "installed_orientation_jitter_std_ns": _sample_std(installed),
    }


def fit_delay_sweep(points: list[dict[str, Any]]) -> dict[str, float]:
    """Weighted linear fit with resolution floors and full fit covariance."""

    if len(points) < 2:
        raise TimingCalibrationError("At least two programmed delays are required for a sweep fit")
    x = [float(point["programmed_delay_ns"]) for point in points]
    y = [float(point["mean_corrected_measured_ns"]) for point in points]
    standard_uncertainties: list[float] = []
    for point in points:
        sem = max(float(point.get("standard_error_ns", 0.0) or 0.0), 0.0)
        interval = max(float(point.get("sample_interval_ns", 0.0) or 0.0), 0.0)
        resolution = interval / math.sqrt(6.0)
        standard_uncertainties.append(math.hypot(sem, resolution) or 1.0)
    weights = [1.0 / (value * value) for value in standard_uncertainties]
    sum_w = sum(weights)
    sum_wx = sum(weight * value for weight, value in zip(weights, x))
    sum_wy = sum(weight * value for weight, value in zip(weights, y))
    sum_wxx = sum(weight * value * value for weight, value in zip(weights, x))
    sum_wxy = sum(weight * xi * yi for weight, xi, yi in zip(weights, x, y))
    determinant = sum_w * sum_wxx - sum_wx * sum_wx
    if determinant <= 0:
        raise TimingCalibrationError("Programmed delays do not span a fit range")
    intercept = (sum_wxx * sum_wy - sum_wx * sum_wxy) / determinant
    slope = (sum_w * sum_wxy - sum_wx * sum_wy) / determinant
    residuals = [yi - (intercept + slope * xi) for xi, yi in zip(x, y)]
    dof = len(points) - 2
    chi_squared = sum(
        weight * residual * residual
        for weight, residual in zip(weights, residuals)
    )
    covariance_scale = max(1.0, chi_squared / dof) if dof > 0 else 1.0
    intercept_variance = covariance_scale * sum_wxx / determinant
    slope_variance = covariance_scale * sum_w / determinant
    intercept_slope_covariance = -covariance_scale * sum_wx / determinant
    intercept_se = math.sqrt(max(intercept_variance, 0.0))
    slope_fit_se = math.sqrt(max(slope_variance, 0.0))
    slope_total_se_ppm = math.hypot(
        slope_fit_se * 1_000_000.0,
        PICOSCOPE_TIMEBASE_ACCURACY_PPM,
    )
    if abs(slope) < 1e-15:
        raise TimingCalibrationError(
            "Delay-sweep slope is effectively zero; recipe correction is undefined"
        )
    correction = -intercept / slope
    correction_da = -1.0 / slope
    correction_db = intercept / (slope * slope)
    correction_variance = (
        correction_da * correction_da * intercept_variance
        + correction_db * correction_db * slope_variance
        + 2.0 * correction_da * correction_db * intercept_slope_covariance
    )
    return {
        "fixed_offset_intercept_ns": intercept,
        "slope": slope,
        "slope_ppm": (slope - 1.0) * 1_000_000.0,
        "intercept_standard_error_ns": intercept_se,
        "slope_fit_standard_error_ppm": slope_fit_se * 1_000_000.0,
        "slope_standard_error_ppm": slope_total_se_ppm,
        "intercept_variance_ns2": intercept_variance,
        "slope_variance": slope_variance,
        "intercept_slope_covariance_ns": intercept_slope_covariance,
        "zero_arrival_recipe_correction_ns": correction,
        "zero_arrival_recipe_correction_standard_uncertainty_ns": math.sqrt(
            max(correction_variance, 0.0)
        ),
        "weighted_reduced_chi_squared": chi_squared / dof if dof > 0 else math.nan,
        "minimum_point_standard_uncertainty_ns": min(standard_uncertainties),
        "maximum_point_standard_uncertainty_ns": max(standard_uncertainties),
        "fit_residual_rms_ns": math.sqrt(statistics.fmean([value * value for value in residuals])),
    }


def consolidate_results(
    rows: list[dict[str, Any]],
    *,
    steps: list[MeasurementStep],
    output_dir: str | Path,
    config_hash: str,
    optical_recipe_path: str,
    selected_optical_program_ns: dict[str, Any] | None = None,
    photodetector_response_delay_ns: float = 0.0,
    photodetector_response_uncertainty_ns: float = 0.0,
    photodetector_response_source: str = "not supplied",
    photodetector_identifier: str = "not supplied",
    photodetector_cable_identifier: str = "not supplied",
    photodetector_characterization_date: str = "not supplied",
    photodetector_path_description: str = "not supplied",
    sample_path_standard_uncertainty_ns: float = 0.0,
    step7_load_match_method: str = "not supplied",
    step7_load_match_standard_uncertainty_ns: float = 0.0,
    measurement_assembly_record: str = "not supplied",
) -> dict[str, str]:
    """Apply corrections, fit sweeps, and write the single intuitive result table."""

    target = Path(output_dir)
    corrections = derive_measurement_system_corrections(rows)
    corrections["photodetector_response_delay_ns"] = float(
        photodetector_response_delay_ns
    )
    corrections["photodetector_response_standard_uncertainty_ns"] = float(
        photodetector_response_uncertainty_ns
    )
    corrections["photodetector_response_source"] = str(
        photodetector_response_source
    )
    corrections["photodetector_identifier"] = str(photodetector_identifier)
    corrections["photodetector_cable_identifier"] = str(
        photodetector_cable_identifier
    )
    corrections["photodetector_characterization_date"] = str(
        photodetector_characterization_date
    )
    corrections["photodetector_path_description"] = str(
        photodetector_path_description
    )
    corrections["sample_path_standard_uncertainty_ns"] = float(
        sample_path_standard_uncertainty_ns
    )
    corrections["step7_load_match_method"] = str(step7_load_match_method)
    corrections["step7_load_match_standard_uncertainty_ns"] = float(
        step7_load_match_standard_uncertainty_ns
    )
    corrections["measurement_assembly_record"] = str(
        measurement_assembly_record
    )
    selected_optical_program = (
        deepcopy(selected_optical_program_ns)
        if selected_optical_program_ns is not None
        else _load_and_validate_optical_recipe(
            optical_recipe_path,
            expected_rate_hz=T660_1_TRIGGER_RATE_HZ,
        )["timing_calibration_selected_program_ns"]
    )
    corrections["selected_optical_program_ns"] = selected_optical_program
    corrections["uncertainty_provenance"] = {
        "picoscope_initial_timebase_accuracy": {
            "value_ppm": PICOSCOPE_TIMEBASE_ACCURACY_PPM,
            "source": "docs/PicoScope/PicoScope 5000D Series Data Sheet.pdf, p. 17, PicoScope 5244D",
            "status": "included in fixed/derived combined uncertainty and slope uncertainty",
        },
        "picoscope_annual_timebase_drift": {
            "data_sheet_bound_ppm_per_year": 1.0,
            "status": "not evaluated separately without a reviewed calibration/age record",
        },
        "t660_programmed_delay_accuracy": {
            "status": "empirically evaluated through fitted slope ppm; no separate manufacturer specification added",
        },
        "cable_reconnection_repeatability": {
            "status": "not separately evaluated; assembly IDs and repeated-shot jitter retained",
        },
        "photodetector_response": {
            "source": str(photodetector_response_source),
            "characterization_date": str(photodetector_characterization_date),
            "status": "included",
        },
        "step7_load_equivalence": {
            "method": str(step7_load_match_method),
            "status": "included",
        },
        "sample_path_placement": {
            "description": str(photodetector_path_description),
            "status": "included",
        },
    }
    scope_skew = float(corrections["scope_channel_and_fixed_lead_b_minus_a_ns"])
    corrected_rows: list[dict[str, Any]] = []
    for row in rows:
        corrected = dict(row)
        measurement_id = str(row["measurement_id"])
        raw_value = float(row["measured_separation_ns"])
        if measurement_id.startswith("MS-00"):
            applied = 0.0
            corrected_value = raw_value
        else:
            applied = -scope_skew
            corrected_value = raw_value - scope_skew
            if measurement_id == "TC-07":
                installed_geometry = float(
                    corrections["installed_step7_branch_2_monitor_minus_branch_1_qswitch_ns"]
                )
                applied += installed_geometry
                corrected_value += installed_geometry
                applied -= float(photodetector_response_delay_ns)
                corrected_value -= float(photodetector_response_delay_ns)
        corrected["measurement_system_correction_applied_ns"] = applied
        corrected["corrected_measured_separation_ns"] = corrected_value
        corrected_rows.append(corrected)
    _write_rows_replace(target / "corrected_per_shot_measurements.csv", corrected_rows)

    per_delay = _aggregate_per_delay(corrected_rows)
    _write_rows_replace(target / "per_delay_statistics.csv", per_delay)
    consolidated: list[dict[str, Any]] = _measurement_system_table_rows(corrections)
    result_by_id: dict[str, dict[str, Any]] = {}
    for step in steps:
        step_points = [item for item in per_delay if item["measurement_id"] == step.measurement_id]
        if not step_points:
            raise TimingCalibrationError(f"No result rows for {step.measurement_id}")
        if step.measurement_id.startswith("MS-00"):
            continue
        if step.sweep_delays:
            fit = fit_delay_sweep(step_points)
            jitter = _pooled_jitter(step_points)
        else:
            values = [
                float(row["corrected_measured_separation_ns"])
                for row in corrected_rows
                if row["measurement_id"] == step.measurement_id
            ]
            fit = {
                "fixed_offset_intercept_ns": statistics.fmean(values),
                "slope": math.nan,
                "slope_ppm": math.nan,
                "intercept_standard_error_ns": _standard_error(values),
                "slope_fit_standard_error_ppm": math.nan,
                "slope_standard_error_ppm": math.nan,
                "intercept_slope_covariance_ns": math.nan,
                "zero_arrival_recipe_correction_ns": math.nan,
                "zero_arrival_recipe_correction_standard_uncertainty_ns": math.nan,
                "fit_residual_rms_ns": math.nan,
            }
            jitter = _sample_std(values)
        correction_uncertainty = 0.0
        correction_text = "none; diagnostic input to correction model"
        if not step.measurement_id.startswith("MS-00"):
            correction_uncertainty = float(corrections["scope_correction_standard_uncertainty_ns"])
            correction_text = f"scope B-A {scope_skew:+.6g} ns subtracted"
            if step.measurement_id == "TC-07":
                scope_variance = correction_uncertainty**2
                installed_variance = float(
                    corrections["installed_step7_geometry_standard_uncertainty_ns"]
                ) ** 2 + float(step7_load_match_standard_uncertainty_ns) ** 2
                covariance = float(
                    corrections["scope_installed_step7_geometry_covariance_ns2"]
                )
                correction_uncertainty = math.sqrt(
                    max(scope_variance + installed_variance - 2.0 * covariance, 0.0)
                    + float(photodetector_response_uncertainty_ns) ** 2
                )
                correction_text += (
                    "; installed splitter/branch geometry "
                    f"{float(corrections['installed_step7_branch_2_monitor_minus_branch_1_qswitch_ns']):+.6g} ns added (MS-00C)"
                    f"; photodetector response {float(photodetector_response_delay_ns):+.6g} ns subtracted"
                )
        sample_resolution_uncertainty = (
            max(float(point["sample_interval_ns"]) for point in step_points)
            / math.sqrt(6.0)
        )
        threshold_values = [
            float(value)
            for point in step_points
            for value in [
                point.get(
                    "photodetector_threshold_sensitivity_standard_uncertainty_ns"
                )
            ]
            if value not in (None, "") and math.isfinite(float(value))
        ]
        threshold_sensitivity_uncertainty = (
            max(threshold_values) if threshold_values else math.nan
        )
        path_uncertainty = (
            float(sample_path_standard_uncertainty_ns)
            if step.measurement_id == "TC-07"
            else 0.0
        )
        combined_variance = (
            float(fit["intercept_standard_error_ns"]) ** 2
            + correction_uncertainty**2
            + (
                threshold_sensitivity_uncertainty**2
                if math.isfinite(threshold_sensitivity_uncertainty)
                else 0.0
            )
            + path_uncertainty**2
        )
        picoscope_fixed_timebase_uncertainty = (
            abs(float(fit["fixed_offset_intercept_ns"]))
            * PICOSCOPE_TIMEBASE_ACCURACY_PPM
            / 1_000_000.0
        )
        combined_variance += picoscope_fixed_timebase_uncertainty**2
        if not step.sweep_delays:
            # Weighted sweep fits already include the sample-interval floor in
            # each point covariance; fixed-point estimates do not.
            combined_variance += sample_resolution_uncertainty**2
        combined_uncertainty = math.sqrt(combined_variance)
        delay_range = (
            f"{min(int(point['programmed_delay_ns']) for point in step_points)} to "
            f"{max(int(point['programmed_delay_ns']) for point in step_points)} ns"
            if step.sweep_delays
            else "fixed operational point"
        )
        recipe_use = (
            step.recipe_use_condition
            or ("yes" if step.use_in_timing_recipe else "no")
        )
        recipe_correction = fit["zero_arrival_recipe_correction_ns"]
        recipe_correction_uncertainty = fit[
            "zero_arrival_recipe_correction_standard_uncertainty_ns"
        ]
        if step.sweep_delays and math.isfinite(float(recipe_correction_uncertainty)):
            recipe_correction_uncertainty = math.hypot(
                float(recipe_correction_uncertainty),
                correction_uncertainty / abs(float(fit["slope"])),
            )
        recipe_formula = (
            "programmed_ns = (desired_physical_arrival_ns - fixed_offset_intercept_ns) / slope"
            if step.sweep_delays and step.use_in_timing_recipe
            else (
                "Use as a measured physical Q-switch-to-t_chem latency in a derived anchor; it is not independently programmable"
                if step.measurement_id == "TC-07"
                else "n/a"
            )
        )
        notes = step.notes
        uncertainty_provenance = (
            "fit/shot statistics + sample-resolution floor + Step 0 scope correction + "
            "PicoScope 5244D data-sheet 2 ppm initial timebase term included; "
            "T660 delay scale evaluated empirically by slope; annual Pico drift and cable-reconnection repeatability not separately evaluated"
        )
        if step.measurement_id == "TC-07":
            notes += (
                f" Detector {photodetector_identifier}, cable {photodetector_cable_identifier}; response source {photodetector_response_source}; "
                f"characterized {photodetector_characterization_date}; path {photodetector_path_description}; "
                f"load equivalence {step7_load_match_method} (u={step7_load_match_standard_uncertainty_ns:g} ns); "
                f"measurement assemblies {measurement_assembly_record}."
            )
            uncertainty_provenance += (
                "; optical detector response, threshold sensitivity, sample-path placement, installed splitter geometry, and load-equivalence terms included with frozen provenance"
            )
        else:
            uncertainty_provenance += (
                "; electrical edge threshold sensitivity not evaluated and excluded"
            )
        row = {
            "category": step.category,
            "measurement_id": step.measurement_id,
            "setup_step": step.step,
            "reference_event": step.reference_event,
            "target_event": step.target_event,
            "physical_connection_summary": f"CHA: {step.pico_ch_a}; CHB: {step.pico_ch_b}",
            "uses_final_wiring": "yes" if step.uses_final_wiring else "no",
            "splitter_used": "yes" if step.splitter_used else "no",
            "splitter_scope_correction_applied": correction_text,
            "programmed_delay_range": delay_range,
            "fixed_offset_intercept_ns": fit["fixed_offset_intercept_ns"],
            "slope_ppm": fit["slope_ppm"],
            "slope_fit_standard_error_ppm": fit["slope_fit_standard_error_ppm"],
            "slope_standard_error_ppm": fit["slope_standard_error_ppm"],
            "intercept_slope_covariance_ns": fit["intercept_slope_covariance_ns"],
            "jitter_std_ns": jitter,
            "intercept_standard_error_ns": fit["intercept_standard_error_ns"],
            "sample_resolution_standard_uncertainty_ns": sample_resolution_uncertainty,
            "threshold_sensitivity_standard_uncertainty_ns": threshold_sensitivity_uncertainty,
            "sample_path_standard_uncertainty_ns": path_uncertainty,
            "combined_standard_uncertainty_ns": combined_uncertainty,
            "uncertainty_terms_and_provenance": uncertainty_provenance,
            "picoscope_timebase_accuracy_ppm": PICOSCOPE_TIMEBASE_ACCURACY_PPM,
            "picoscope_fixed_timebase_standard_uncertainty_ns": picoscope_fixed_timebase_uncertainty,
            "recipe_correction_ns": recipe_correction,
            "recipe_correction_standard_uncertainty_ns": recipe_correction_uncertainty,
            "recipe_formula": recipe_formula,
            "use_in_timing_recipe": recipe_use,
            "rsi_thesis_reporting_label": step.reporting_label,
            "notes": notes,
        }
        consolidated.append(row)
        result_by_id[step.measurement_id] = row

    derived = _derive_recipe_corrections(
        result_by_id,
        corrections=corrections,
        optical_recipe_path=optical_recipe_path,
        optical_fire_programmed_delay_ns=float(
            selected_optical_program["fire_delay_ns"]
        ),
        optical_q_switch_programmed_delay_ns=float(
            selected_optical_program["q_switch_delay_ns"]
        ),
    )
    consolidated.extend(_derived_table_rows(derived))
    csv_path = _write_rows_replace(target / "consolidated_timing_calibration.csv", consolidated)
    yaml_path = _write_yaml_replace(
        target / "consolidated_timing_calibration.yaml",
        {
            "schema_version": RESULT_SCHEMA_VERSION,
            "generated_utc": _utc_now(),
            "config_hash": config_hash,
            "time_origins": {
                "t_master": "first programmed T660-2 timing event",
                "t_chem": "optical OPO pump arrival at sample (TC-07)",
            },
            "measurement_system_corrections": corrections,
            "measurements": consolidated,
            "derived_recipe_corrections": derived,
        },
    )
    markdown_path = _write_text_replace(
        target / "consolidated_timing_calibration.md",
        _render_consolidated_markdown(consolidated, corrections, derived),
    )
    corrections_path = _write_yaml_replace(
        target / "derived_recipe_corrections.yaml",
        {
            "schema_version": RESULT_SCHEMA_VERSION,
            "generated_utc": _utc_now(),
            "config_hash": config_hash,
            "measurement_system_corrections": corrections,
            "derived_recipe_corrections": derived,
            "publication_status": "review before manual promotion; no canonical recipe or RSI draft was modified",
        },
    )
    return {
        "consolidated_csv": str(csv_path),
        "consolidated_yaml": str(yaml_path),
        "consolidated_markdown": str(markdown_path),
        "derived_recipe_corrections_yaml": str(corrections_path),
        "per_delay_statistics_csv": str(target / "per_delay_statistics.csv"),
        "corrected_per_shot_csv": str(target / "corrected_per_shot_measurements.csv"),
    }


def _derive_recipe_corrections(
    results: dict[str, dict[str, Any]],
    *,
    corrections: dict[str, Any],
    optical_recipe_path: str,
    optical_fire_programmed_delay_ns: float,
    optical_q_switch_programmed_delay_ns: float,
) -> dict[str, Any]:
    """Create formulas and the requested cross-device derived timing checks."""

    def intercept(measurement_id: str) -> float:
        return float(results[measurement_id]["fixed_offset_intercept_ns"])

    def fit_variance(measurement_id: str) -> float:
        row = results[measurement_id]
        variance = float(row["intercept_standard_error_ns"]) ** 2
        if math.isnan(float(row["slope_ppm"])):
            variance += float(row["sample_resolution_standard_uncertainty_ns"]) ** 2
        for field in (
            "threshold_sensitivity_standard_uncertainty_ns",
            "sample_path_standard_uncertainty_ns",
        ):
            value = float(row.get(field, 0.0) or 0.0)
            if math.isfinite(value):
                variance += value**2
        return variance

    def slope_ppm(measurement_id: str) -> float:
        return float(results[measurement_id]["slope_ppm"])

    def slope(measurement_id: str) -> float:
        value = slope_ppm(measurement_id)
        return 1.0 if math.isnan(value) else 1.0 + value / 1_000_000.0

    def prediction(measurement_id: str, programmed_delay_ns: float) -> float:
        return intercept(measurement_id) + slope(measurement_id) * programmed_delay_ns

    def prediction_fit_variance(
        measurement_id: str,
        programmed_delay_ns: float,
    ) -> float:
        row = results[measurement_id]
        if math.isnan(float(row["slope_ppm"])):
            return fit_variance(measurement_id)
        intercept_variance = float(row["intercept_standard_error_ns"]) ** 2
        slope_variance = (
            float(row["slope_fit_standard_error_ppm"]) / 1_000_000.0
        ) ** 2
        intercept_slope_covariance = float(
            row["intercept_slope_covariance_ns"]
        )
        return max(
            intercept_variance
            + programmed_delay_ns * programmed_delay_ns * slope_variance
            + 2.0 * programmed_delay_ns * intercept_slope_covariance,
            0.0,
        )

    def include_timebase_scale(value_ns: float, variance_ns2: float) -> float:
        scale_uncertainty = (
            abs(value_ns) * PICOSCOPE_TIMEBASE_ACCURACY_PPM / 1_000_000.0
        )
        return math.sqrt(max(variance_ns2, 0.0) + scale_uncertainty**2)

    def slope_standard_error_ppm(measurement_id: str) -> float:
        # The Pico timebase-accuracy term is common to both slopes and cancels
        # in this same-instrument difference; retain only independent fit error.
        return float(results[measurement_id]["slope_fit_standard_error_ppm"])

    closure = intercept("TC-06") - (intercept("TC-04") + intercept("TC-05"))
    closure_slope_ppm = slope_ppm("TC-06") - slope_ppm("TC-05")
    closure_slope_standard_error_ppm = math.hypot(
        slope_standard_error_ppm("TC-06"),
        slope_standard_error_ppm("TC-05"),
    )
    master_to_process = intercept("TC-04") + intercept("TC-08")
    master_to_q_zero = intercept("TC-04") + intercept("TC-05")
    master_to_chem_zero_programmed = master_to_q_zero + intercept("TC-07")
    direct_q_to_chem_zero_programmed = intercept("TC-06") + intercept("TC-07")
    fire_programmed = float(optical_fire_programmed_delay_ns)
    q_programmed = float(optical_q_switch_programmed_delay_ns)
    fire_to_q_programmed = q_programmed - fire_programmed
    selected_fire_arrival = prediction("TC-04", fire_programmed)
    selected_fire_to_q = prediction("TC-05", fire_to_q_programmed)
    selected_q_component = selected_fire_arrival + selected_fire_to_q
    selected_q_direct = prediction("TC-06", q_programmed)
    selected_chem_component = selected_q_component + intercept("TC-07")
    selected_chem_direct = selected_q_direct + intercept("TC-07")
    selected_q_closure = selected_q_direct - selected_q_component
    scope_variance = float(corrections["scope_correction_standard_uncertainty_ns"]) ** 2
    installed_geometry_variance = float(
        corrections["installed_step7_geometry_standard_uncertainty_ns"]
    ) ** 2 + float(
        corrections.get("step7_load_match_standard_uncertainty_ns", 0.0)
    ) ** 2
    covariance = float(corrections["scope_installed_step7_geometry_covariance_ns2"])
    detector_variance = float(
        corrections["photodetector_response_standard_uncertainty_ns"]
    ) ** 2
    closure_uncertainty = include_timebase_scale(
        closure,
        fit_variance("TC-06")
        + fit_variance("TC-04")
        + fit_variance("TC-05")
        + scope_variance,
    )
    selected_q_closure_uncertainty = include_timebase_scale(
        selected_q_closure,
        prediction_fit_variance("TC-06", q_programmed)
        + prediction_fit_variance("TC-04", fire_programmed)
        + prediction_fit_variance("TC-05", fire_to_q_programmed)
        + scope_variance,
    )
    master_to_q_uncertainty = include_timebase_scale(
        master_to_q_zero,
        fit_variance("TC-04") + fit_variance("TC-05") + 4.0 * scope_variance,
    )
    selected_q_component_uncertainty = include_timebase_scale(
        selected_q_component,
        prediction_fit_variance("TC-04", fire_programmed)
        + prediction_fit_variance("TC-05", fire_to_q_programmed)
        + 4.0 * scope_variance,
    )
    master_to_process_uncertainty = include_timebase_scale(
        master_to_process,
        fit_variance("TC-04") + fit_variance("TC-08") + 4.0 * scope_variance,
    )
    master_to_chem_uncertainty = include_timebase_scale(
        master_to_chem_zero_programmed,
        fit_variance("TC-04")
        + fit_variance("TC-05")
        + fit_variance("TC-07")
        + max(9.0 * scope_variance + installed_geometry_variance - 6.0 * covariance, 0.0)
        + detector_variance,
    )
    direct_q_to_chem_uncertainty = include_timebase_scale(
        direct_q_to_chem_zero_programmed,
        fit_variance("TC-06")
        + fit_variance("TC-07")
        + max(
            4.0 * scope_variance
            + installed_geometry_variance
            - 4.0 * covariance,
            0.0,
        )
        + detector_variance,
    )
    selected_chem_component_uncertainty = include_timebase_scale(
        selected_chem_component,
        prediction_fit_variance("TC-04", fire_programmed)
        + prediction_fit_variance("TC-05", fire_to_q_programmed)
        + fit_variance("TC-07")
        + max(
            9.0 * scope_variance
            + installed_geometry_variance
            - 6.0 * covariance,
            0.0,
        )
        + detector_variance,
    )
    selected_chem_direct_uncertainty = include_timebase_scale(
        selected_chem_direct,
        prediction_fit_variance("TC-06", q_programmed)
        + fit_variance("TC-07")
        + max(
            4.0 * scope_variance
            + installed_geometry_variance
            - 4.0 * covariance,
            0.0,
        )
        + detector_variance,
    )
    per_measurement = {}
    for measurement_id, row in results.items():
        if row["use_in_timing_recipe"] == "no":
            continue
        slope_ppm = float(row["slope_ppm"])
        slope = 1.0 if math.isnan(slope_ppm) else 1.0 + slope_ppm / 1_000_000.0
        fixed = float(row["fixed_offset_intercept_ns"])
        if measurement_id == "TC-07":
            per_measurement[measurement_id] = {
                "fixed_optical_delay_ns": fixed,
                "fixed_optical_delay_standard_uncertainty_ns": float(
                    row["combined_standard_uncertainty_ns"]
                ),
                "slope": None,
                "slope_ppm": None,
                "recipe_application": "Add this Q-switch-to-optical delay when deriving the optical t_chem anchor; it is not an independently programmable route correction.",
            }
        else:
            per_measurement[measurement_id] = {
                "fixed_offset_intercept_ns": fixed,
                "slope": slope,
                "slope_ppm": slope_ppm,
                "zero_arrival_recipe_correction_ns": float(
                    row["recipe_correction_ns"]
                ),
                "zero_arrival_recipe_correction_standard_uncertainty_ns": float(
                    row["recipe_correction_standard_uncertainty_ns"]
                ),
                "use_condition": row["use_in_timing_recipe"],
                "general_formula": "programmed_ns = (desired_physical_arrival_ns - fixed_offset_intercept_ns) / slope",
            }
    return {
        "per_measurement": per_measurement,
        "hf2li_extref_arrival_to_qswitch_zero_programmed_ns_derived_TC04_plus_TC05": master_to_q_zero,
        "hf2li_extref_arrival_to_qswitch_zero_programmed_standard_uncertainty_ns": master_to_q_uncertainty,
        "hf2li_extref_arrival_to_qswitch_validation_closure_ns_TC06_minus_TC04_plus_TC05": closure,
        "hf2li_extref_arrival_to_qswitch_validation_closure_standard_uncertainty_ns": closure_uncertainty,
        "qswitch_validation_slope_difference_ppm_TC06_minus_TC05": closure_slope_ppm,
        "qswitch_validation_slope_difference_standard_error_ppm": closure_slope_standard_error_ppm,
        "hf2li_extref_arrival_to_mircat_process_zero_programmed_ns_TC04_plus_TC08": master_to_process,
        "hf2li_extref_arrival_to_mircat_process_zero_programmed_standard_uncertainty_ns": master_to_process_uncertainty,
        "hf2li_extref_arrival_to_t_chem_zero_programmed_ns_TC04_plus_TC05_plus_TC07": master_to_chem_zero_programmed,
        "hf2li_extref_arrival_to_t_chem_zero_programmed_standard_uncertainty_ns": master_to_chem_uncertainty,
        "hf2li_extref_arrival_to_t_chem_zero_programmed_ns_TC06_plus_TC07_direct_validation": direct_q_to_chem_zero_programmed,
        "hf2li_extref_arrival_to_t_chem_zero_programmed_standard_uncertainty_ns_TC06_plus_TC07_direct_validation": direct_q_to_chem_uncertainty,
        "hf2li_extref_arrival_to_t_chem_dual_derivation_closure_ns_direct_minus_component": direct_q_to_chem_zero_programmed - master_to_chem_zero_programmed,
        "hf2li_extref_arrival_to_t_chem_dual_derivation_closure_standard_uncertainty_ns": closure_uncertainty,
        "selected_optical_recipe_programmed_delays_ns": {
            "fire": fire_programmed,
            "q_switch": q_programmed,
            "fire_to_q_switch": fire_to_q_programmed,
        },
        "hf2li_extref_arrival_to_qswitch_selected_recipe_ns_TC04_at_FIRE_plus_TC05_at_Q_minus_FIRE": selected_q_component,
        "hf2li_extref_arrival_to_qswitch_selected_recipe_standard_uncertainty_ns": selected_q_component_uncertainty,
        "hf2li_extref_arrival_to_qswitch_selected_recipe_validation_closure_ns_TC06_at_Q_minus_components": selected_q_closure,
        "hf2li_extref_arrival_to_qswitch_selected_recipe_validation_closure_standard_uncertainty_ns": selected_q_closure_uncertainty,
        "hf2li_extref_arrival_to_t_chem_selected_recipe_ns_TC04_plus_TC05_plus_TC07": selected_chem_component,
        "hf2li_extref_arrival_to_t_chem_selected_recipe_standard_uncertainty_ns_TC04_plus_TC05_plus_TC07": selected_chem_component_uncertainty,
        "hf2li_extref_arrival_to_t_chem_selected_recipe_ns_TC06_plus_TC07_direct_validation": selected_chem_direct,
        "hf2li_extref_arrival_to_t_chem_selected_recipe_standard_uncertainty_ns_TC06_plus_TC07_direct_validation": selected_chem_direct_uncertainty,
        "hf2li_extref_arrival_to_t_chem_selected_recipe_dual_derivation_closure_ns_direct_minus_component": selected_q_closure,
        "hf2li_extref_arrival_to_t_chem_selected_recipe_dual_derivation_closure_standard_uncertainty_ns": selected_q_closure_uncertainty,
        "optical_recipe_path": optical_recipe_path,
        "time_origin_note": "These combinations are referenced to physical HF2LI EXT REF cable-end arrival. t_master=0 remains recipe zero; converting to t_master requires a separately established programming-origin-to-EXT-REF-arrival term. t_chem=0 is the corrected optical arrival.",
        "drift_note": "Zero-programmed diagnostics use intercepts only. The selected-recipe t_chem anchor evaluates each fitted slope at the frozen FIRE/Q-switch program; long-delay residuals are never treated as fixed cable delay.",
        "optical_closure_covariance_note": "The direct-minus-component optical closure is algebraically the selected-program Q-switch-chain closure; shared TC-07 detector, path, scope/splitter, and load-equivalence terms cancel and must not be RSS-added from DER-02 and DER-04.",
    }


def _derived_table_rows(derived: dict[str, Any]) -> list[dict[str, Any]]:
    """Append visibly distinct validation/recipe rows to the consolidated table."""

    common = {
        "physical_connection_summary": "Derived from corrected component measurements; no additional cable setup",
        "uses_final_wiring": "derived",
        "splitter_used": "component-dependent",
        "splitter_scope_correction_applied": "already applied to component measurements with shared-correction covariance retained",
        "programmed_delay_range": "derived from fitted intercepts",
        "slope_ppm": math.nan,
        "slope_fit_standard_error_ppm": math.nan,
        "slope_standard_error_ppm": math.nan,
        "intercept_slope_covariance_ns": math.nan,
        "jitter_std_ns": math.nan,
        "intercept_standard_error_ns": math.nan,
        "sample_resolution_standard_uncertainty_ns": math.nan,
        "threshold_sensitivity_standard_uncertainty_ns": math.nan,
        "sample_path_standard_uncertainty_ns": math.nan,
        "picoscope_timebase_accuracy_ppm": PICOSCOPE_TIMEBASE_ACCURACY_PPM,
        "picoscope_fixed_timebase_standard_uncertainty_ns": math.nan,
        "recipe_correction_ns": math.nan,
        "recipe_correction_standard_uncertainty_ns": math.nan,
        "recipe_formula": "see derived formula",
        "uncertainty_terms_and_provenance": "component fit/shot/resolution and Step 0 shared-correction covariance included; PicoScope 5244D data-sheet 2 ppm fixed-scale term included; component-specific unresolved statuses remain in measurement_system_corrections.uncertainty_provenance",
    }
    definitions = (
        (
            "derived-chain validation",
            "DER-01",
            "TC-04 + TC-05 derived Q-switch arrival",
            "TC-06 direct Q-switch arrival",
            "hf2li_extref_arrival_to_qswitch_validation_closure_ns_TC06_minus_TC04_plus_TC05",
            "hf2li_extref_arrival_to_qswitch_validation_closure_standard_uncertainty_ns",
            "no",
            "Direct-minus-derived HF2LI-EXT-REF-arrival-to-Q-switch closure",
            "A nonzero closure is a diagnostic; do not average it away.",
        ),
        (
            "derived timing",
            "DER-02",
            "HF2LI EXT REF arrival",
            "optical OPO pump arrival at sample (t_chem = 0)",
            "hf2li_extref_arrival_to_t_chem_selected_recipe_ns_TC04_plus_TC05_plus_TC07",
            "hf2li_extref_arrival_to_t_chem_selected_recipe_standard_uncertainty_ns_TC04_plus_TC05_plus_TC07",
            "yes",
            "Derived electrical-reference-to-chemical-zero timing",
            "Evaluates TC-04 at the frozen FIRE delay and TC-05 at the frozen FIRE-to-Q delay, then adds detector/splitter-corrected TC-07; this is the selected optical recipe's t_chem anchor.",
        ),
        (
            "derived timing",
            "DER-03",
            "HF2LI EXT REF arrival",
            "MIRcat Process Trigger DB9 pin 4 arrival",
            "hf2li_extref_arrival_to_mircat_process_zero_programmed_ns_TC04_plus_TC08",
            "hf2li_extref_arrival_to_mircat_process_zero_programmed_standard_uncertainty_ns",
            "conditional: yes only if T660-1 CHC is used for MIRcat process timing",
            "Derived HF2LI-EXT-REF-arrival-to-MIRcat-process timing",
            "TC-04 + TC-08; slope terms remain separate.",
        ),
        (
            "derived-chain validation",
            "DER-04",
            "HF2LI EXT REF arrival",
            "optical OPO pump arrival at sample (t_chem = 0)",
            "hf2li_extref_arrival_to_t_chem_selected_recipe_ns_TC06_plus_TC07_direct_validation",
            "hf2li_extref_arrival_to_t_chem_selected_recipe_standard_uncertainty_ns_TC06_plus_TC07_direct_validation",
            "no; validation of DER-02",
            "Direct-Q-switch-validation route to chemical-zero timing",
            "Evaluates TC-06 at the frozen Q-switch delay, then adds TC-07; compare its selected-program closure with DER-02 rather than averaging silently.",
        ),
    )
    rows: list[dict[str, Any]] = []
    for (
        category,
        measurement_id,
        reference,
        target,
        value_key,
        uncertainty_key,
        use_in_recipe,
        label,
        notes,
    ) in definitions:
        rows.append(
            {
                **common,
                "category": category,
                "measurement_id": measurement_id,
                "setup_step": "derived",
                "reference_event": reference,
                "target_event": target,
                "fixed_offset_intercept_ns": derived[value_key],
                "combined_standard_uncertainty_ns": derived[uncertainty_key],
                "picoscope_fixed_timebase_standard_uncertainty_ns": (
                    abs(float(derived[value_key]))
                    * PICOSCOPE_TIMEBASE_ACCURACY_PPM
                    / 1_000_000.0
                ),
                "use_in_timing_recipe": use_in_recipe,
                "rsi_thesis_reporting_label": label,
                "notes": notes,
            }
        )
    for row in rows:
        if row["measurement_id"] == "DER-01":
            row["slope_ppm"] = derived[
                "qswitch_validation_slope_difference_ppm_TC06_minus_TC05"
            ]
            row["slope_standard_error_ppm"] = derived[
                "qswitch_validation_slope_difference_standard_error_ppm"
            ]
        elif row["measurement_id"] in {"DER-02", "DER-03"}:
            row["recipe_correction_ns"] = -float(
                row["fixed_offset_intercept_ns"]
            )
            row["recipe_correction_standard_uncertainty_ns"] = float(
                row["combined_standard_uncertainty_ns"]
            )
            row["recipe_formula"] = (
                "Signed zero-arrival shift shown as -physical_latency; apply component slopes/formulas rather than folding ppm into the fixed term"
            )
        if row["measurement_id"] in {"DER-02", "DER-04"}:
            selected = derived["selected_optical_recipe_programmed_delays_ns"]
            row["programmed_delay_range"] = (
                f"selected optical recipe: FIRE={selected['fire']} ns, "
                f"Q-switch={selected['q_switch']} ns, "
                f"FIRE-to-Q={selected['fire_to_q_switch']} ns"
            )
    return rows


def _measurement_system_table_rows(corrections: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose derived scope/splitter corrections rather than raw swap orientations."""

    common = {
        "category": "measurement-system correction",
        "setup_step": "0",
        "uses_final_wiring": "no",
        "splitter_used": "yes",
        "splitter_scope_correction_applied": "derived from MS-00A/MS-00B/MS-00C; not a final-system route delay",
        "programmed_delay_range": "fixed zero-delay characterization",
        "slope_ppm": math.nan,
        "slope_fit_standard_error_ppm": math.nan,
        "slope_standard_error_ppm": math.nan,
        "intercept_slope_covariance_ns": math.nan,
        "jitter_std_ns": math.nan,
        "sample_resolution_standard_uncertainty_ns": corrections[
            "step0_sample_resolution_standard_uncertainty_ns"
        ],
        "threshold_sensitivity_standard_uncertainty_ns": math.nan,
        "sample_path_standard_uncertainty_ns": math.nan,
        "picoscope_timebase_accuracy_ppm": PICOSCOPE_TIMEBASE_ACCURACY_PPM,
        "recipe_correction_ns": math.nan,
        "recipe_correction_standard_uncertainty_ns": math.nan,
        "recipe_formula": "n/a; measurement-system correction",
        "uncertainty_terms_and_provenance": "Step 0 repeat statistics and sample resolution included; PicoScope 5244D data-sheet 2 ppm fixed-scale term included; cable-reconnection repeatability not separately evaluated",
        "use_in_timing_recipe": "no",
    }
    definitions = (
        (
            "COR-01",
            "PicoScope CHA plus fixed A lead",
            "PicoScope CHB plus fixed B lead",
            "scope_channel_and_fixed_lead_b_minus_a_ns",
            "scope_correction_standard_uncertainty_ns",
            "PicoScope differential acquisition-path correction",
            "Subtract this B-A term from every direct CHB-minus-CHA system measurement.",
        ),
        (
            "COR-02",
            "Bare splitter output 1",
            "Bare splitter output 2",
            "splitter_branch_2_minus_1_ns",
            "splitter_correction_standard_uncertainty_ns",
            "Bare splitter branch-skew diagnostic",
            "Diagnostic separation of splitter skew from scope skew; the splitter is not final wiring.",
        ),
        (
            "COR-03",
            "Installed splitter output 1 plus final Q-switch cable",
            "Installed splitter output 2 plus exact monitor lead",
            "installed_step7_branch_2_monitor_minus_branch_1_qswitch_ns",
            "installed_step7_geometry_standard_uncertainty_ns",
            "Installed Step 7 splitter/branch geometry correction",
            "Add this term in TC-07 so temporary splitter and unequal lead delay are not folded into optical timing.",
        ),
    )
    rows: list[dict[str, Any]] = []
    for measurement_id, reference, target, value_key, uncertainty_key, label, notes in definitions:
        fit_uncertainty = float(corrections[uncertainty_key])
        combined_uncertainty = fit_uncertainty
        if measurement_id == "COR-03":
            combined_uncertainty = math.hypot(
                fit_uncertainty,
                float(
                    corrections.get(
                        "step7_load_match_standard_uncertainty_ns", 0.0
                    )
                ),
            )
            notes += " Combined uncertainty also includes the separately supplied load-equivalence term."
            uncertainty_provenance = (
                common["uncertainty_terms_and_provenance"]
                + "; frozen Step 0c load-equivalence standard uncertainty included"
            )
            jitter = float(corrections["installed_orientation_jitter_std_ns"])
        else:
            uncertainty_provenance = common[
                "uncertainty_terms_and_provenance"
            ]
            jitter = math.hypot(
                float(corrections["normal_jitter_std_ns"]),
                float(corrections["swapped_jitter_std_ns"]),
            ) / 2.0
        picoscope_fixed_uncertainty = (
            abs(float(corrections[value_key]))
            * PICOSCOPE_TIMEBASE_ACCURACY_PPM
            / 1_000_000.0
        )
        combined_uncertainty = math.hypot(
            combined_uncertainty,
            picoscope_fixed_uncertainty,
        )
        rows.append(
            {
                **common,
                "measurement_id": measurement_id,
                "reference_event": reference,
                "target_event": target,
                "physical_connection_summary": "Step 0 normal, swapped, and exact installed-geometry splitter configurations",
                "fixed_offset_intercept_ns": corrections[value_key],
                "intercept_standard_error_ns": fit_uncertainty,
                "jitter_std_ns": jitter,
                "combined_standard_uncertainty_ns": combined_uncertainty,
                "picoscope_fixed_timebase_standard_uncertainty_ns": picoscope_fixed_uncertainty,
                "uncertainty_terms_and_provenance": uncertainty_provenance,
                "rsi_thesis_reporting_label": label,
                "notes": notes,
            }
        )
    return rows


def _aggregate_per_delay(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["measurement_id"]), int(row["programmed_delay_ns"]))
        grouped.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
    for (measurement_id, programmed_delay_ns), group in sorted(grouped.items()):
        corrected = [float(row["corrected_measured_separation_ns"]) for row in group]
        raw = [float(row["measured_separation_ns"]) for row in group]
        threshold_values = [
            float(value)
            for row in group
            for value in [
                row.get(
                    "photodetector_threshold_sensitivity_standard_uncertainty_ns"
                )
            ]
            if value not in (None, "") and math.isfinite(float(value))
        ]
        output.append(
            {
                "measurement_id": measurement_id,
                "setup_id": group[0]["setup_id"],
                "programmed_delay_ns": programmed_delay_ns,
                "shot_count": len(group),
                "mean_raw_measured_ns": statistics.fmean(raw),
                "mean_corrected_measured_ns": statistics.fmean(corrected),
                "mean_corrected_residual_ns": statistics.fmean(corrected) - programmed_delay_ns,
                "jitter_std_ns": _sample_std(corrected),
                "standard_error_ns": _standard_error(corrected),
                "sample_interval_ns": float(group[0]["sample_interval_ns"]),
                "photodetector_threshold_sensitivity_standard_uncertainty_ns": (
                    max(threshold_values) if threshold_values else None
                ),
                "first_raw_trace": group[0]["raw_trace_path"],
            }
        )
    return output


def _measurement_row(
    step: MeasurementStep,
    measurement: dict[str, Any],
    *,
    operator: str,
    config_hash: str,
    programmed_delay_ns: int,
    shot_index: int,
    capture_settings: dict[str, Any],
    timing_validation: dict[str, Any],
    raw_path: Path,
    capture_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "timestamp_utc": _utc_now(),
        "operator": operator,
        "config_hash": config_hash,
        "setup_id": step.setup_id,
        "step": step.step,
        "measurement_id": step.measurement_id,
        "category": step.category,
        "reference_event": step.reference_event,
        "target_event": step.target_event,
        "programmed_delay_ns": int(programmed_delay_ns),
        "shot_index": int(shot_index),
        "measured_separation_ns": float(measurement["measured_separation_ns"]),
        "raw_residual_ns": float(measurement["residual_ns"]),
        "reference_edge_time_ns": float(measurement["reference_edge_time_ns"]),
        "target_edge_time_ns": float(measurement["target_edge_time_ns"]),
        "reference_edge_count": int(measurement["reference_edge_count"]),
        "target_edge_count": int(measurement["target_edge_count"]),
        "reference_edge": step.reference_edge,
        "target_edge": step.target_edge,
        "sample_interval_ns": float(timing_validation["sample_interval_ns"]),
        "picoscope_timebase": int(capture_settings["timebase"]),
        "picoscope_total_samples": int(capture_settings["total_samples"]),
        "picoscope_pre_trigger_samples": int(capture_settings["pre_trigger_samples"]),
        "photodetector_peak_abs_adc": measurement.get("photodetector_peak_abs_adc", ""),
        "photodetector_baseline_noise_adc": measurement.get("photodetector_baseline_noise_adc", ""),
        "photodetector_signal_excursion_adc": measurement.get("photodetector_signal_excursion_adc", ""),
        "photodetector_minimum_latency_ns": measurement.get(
            "photodetector_minimum_latency_ns", ""
        ),
        "photodetector_saturated": measurement.get(
            "photodetector_saturated", ""
        ),
        "photodetector_threshold_sensitivity_standard_uncertainty_ns": measurement.get(
            "photodetector_threshold_sensitivity_standard_uncertainty_ns", ""
        ),
        "raw_trace_path": str(raw_path),
        "capture_summary": json.dumps(capture_summary, sort_keys=True),
    }


def _plan_capture_settings(
    pico: PicoScopeService,
    base: dict[str, Any],
    *,
    programmed_delay_ns: int,
    base_sample_interval_ns: float,
    trigger_edge: str,
    max_samples_per_trace: int = MAX_SAMPLES_PER_TRACE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base_settings = _settings_with_channel_a_trigger(base, edge=trigger_edge)
    pre_trigger = int(base_settings.get("pre_trigger_samples", 0))
    first_timebase = int(base_settings.get("timebase", 1))
    last_error: Exception | None = None
    for timebase in range(first_timebase, first_timebase + 32):
        settings = deepcopy(base_settings)
        settings["timebase"] = timebase
        # Query each candidate with a known-small block, then calculate the
        # exact sample count from the interval returned by the real driver.
        settings["total_samples"] = min(
            max(int(base_settings.get("total_samples", 0)), 1000),
            int(max_samples_per_trace),
        )
        pico.capture_settings = settings
        try:
            timing_validation = pico.validate_sample_timing()
        except Exception as exc:  # noqa: BLE001 - try the next driver-supported timebase
            last_error = exc
            continue
        actual_interval = float(timing_validation["sample_interval_ns"])
        if actual_interval <= 0:
            continue
        margin_ns = max(10_000.0, 50.0 * actual_interval, 50.0 * base_sample_interval_ns)
        required_post_span = max(programmed_delay_ns, 0) + margin_ns
        required_post_samples = math.ceil(required_post_span / actual_interval)
        required_total = _round_up(pre_trigger + required_post_samples, 1000)
        settings["total_samples"] = max(1000, required_total)
        if int(settings["total_samples"]) > int(max_samples_per_trace):
            continue
        max_samples = int(timing_validation.get("max_samples", 0))
        if max_samples > 0 and int(settings["total_samples"]) > max_samples:
            continue
        pico.capture_settings = settings
        try:
            timing_validation = pico.validate_sample_timing()
        except Exception as exc:  # noqa: BLE001 - candidate cannot hold the requested block
            last_error = exc
            continue
        max_samples = int(timing_validation.get("max_samples", 0))
        if max_samples > 0 and int(settings["total_samples"]) > max_samples:
            continue
        if _post_trigger_span_ns(
            settings,
            float(timing_validation["sample_interval_ns"]),
        ) >= required_post_span:
            timing_validation = dict(timing_validation)
            timing_validation["workflow_sample_budget"] = int(max_samples_per_trace)
            return settings, timing_validation
    detail = f": {last_error}" if last_error is not None else ""
    raise TimingCalibrationError(
        "PicoScope could not find a supported timebase/window covering "
        f"{programmed_delay_ns} ns in one capture within the {max_samples_per_trace}-sample raw-volume budget{detail}"
    )


def _settings_with_channel_a_trigger(settings: dict[str, Any], *, edge: str) -> dict[str, Any]:
    copied = deepcopy(settings)
    trigger = copied.setdefault("external_trigger", {})
    trigger["source"] = "A"
    trigger["direction"] = 2 if edge == "rising" else 3
    trigger["direction_name"] = edge
    trigger["auto_trigger_ms"] = 0
    return copied


def _load_and_validate_optical_recipe(
    path: str | Path,
    *,
    expected_rate_hz: int,
) -> dict[str, Any]:
    recipe, target, source_sha256 = _load_yaml_mapping_with_sha256(path)
    if recipe.get("approved_laser_safety_condition") is not True:
        raise TimingCalibrationError("Optical recipe lacks approved_laser_safety_condition: true")
    t660 = recipe.get("t660") or {}
    t660_1 = t660.get("t660_1") or {}
    t660_2 = t660.get("t660_2") or {}
    signals = t660_1.get("signals") or {}
    fire_settings = deepcopy(signals.get("ndyag_fire") or {})
    qswitch_settings = deepcopy(signals.get("ndyag_q_switch") or {})
    if not (fire_settings.get("enabled") is True and qswitch_settings.get("enabled") is True):
        raise TimingCalibrationError("Optical recipe must enable both Nd:YAG FIRE and Q-switch")
    _require_optical_channel_fields("ndyag_fire", fire_settings)
    _require_optical_channel_fields("ndyag_q_switch", qswitch_settings)
    master_channels = t660_2.get("channels") or {}
    master_drive = deepcopy(master_channels.get("D") or {})
    if master_drive.get("enabled") is not True:
        raise TimingCalibrationError(
            "Optical recipe must explicitly enable only T660-2 CHD as the T660-1 trigger drive"
        )
    _require_optical_channel_fields("t660_1_trig_in", master_drive)
    frequency = str((t660_2.get("clock") or {}).get("frequency", "")).lower().replace(" ", "")
    if frequency not in {f"{expected_rate_hz}hz", str(expected_rate_hz)}:
        raise TimingCalibrationError(
            f"Optical recipe must use exactly {expected_rate_hz} Hz, found {frequency!r}"
        )
    recipe = deepcopy(recipe)
    recipe["_path"] = str(target)
    recipe["_source_sha256"] = source_sha256
    recipe["timing_calibration_optical_step"] = True
    trigger_input = recipe["t660"]["t660_1"]
    trigger_input["stop_first"] = True
    trigger_input["trigger_source"] = "EXT"
    trigger_input.pop("clock", None)
    trigger_input["predivider"] = 1
    trigger_input["gate_mode"] = 0
    trigger_input["burst_enabled"] = False
    trigger_input["external_trigger"] = {
        "polarity": "positive",
        "termination": "50OHM",
        "threshold_v": 2.0,
    }
    master = recipe["t660"]["t660_2"]
    master["stop_first"] = True
    master["force_eod"] = True
    master["start"] = True
    master["predivider"] = 1
    master["gate_mode"] = 0
    master["burst_enabled"] = False
    master["frames_engine"] = "OFF"
    master["trigger_source"] = "REM"
    master_clock = deepcopy(master.get("clock") or {})
    master_clock.pop("mode", None)
    master_clock["frequency"] = f"{expected_rate_hz}Hz"
    master_clock["shots"] = 0
    master["clock"] = master_clock
    master["external_trigger"] = {
        "polarity": "positive",
        "termination": "50OHM",
        "threshold_v": 2.0,
    }
    trigger_input["force_eod"] = True
    trigger_input["start"] = True
    disabled_channel = {
        "timing_mode": "delay_width",
        "delay": "0ns",
        "width": "150ns",
        "polarity": "positive",
        "termination": "50OHM",
        "enabled": False,
    }
    trigger_input.pop("channels", None)
    trigger_input["signals"] = {
        "ndyag_fire": fire_settings,
        "ndyag_q_switch": qswitch_settings,
        "mircat_db9_pin_4_process_trigger": {
            **deepcopy(disabled_channel),
            "width": "10ms",
            "polarity": "negative",
        },
    }
    master.pop("signals", None)
    master["channels"] = {
        "A": deepcopy(disabled_channel),
        "B": deepcopy(disabled_channel),
        "C": deepcopy(disabled_channel),
        "D": master_drive,
    }
    recipe["timing_calibration_selected_program_ns"] = {
        "fire_delay_ns": _duration_ns(fire_settings["delay"]),
        "q_switch_delay_ns": _duration_ns(qswitch_settings["delay"]),
        "fire_to_q_switch_programmed_ns": (
            _duration_ns(qswitch_settings["delay"])
            - _duration_ns(fire_settings["delay"])
        ),
    }
    return recipe


def _load_yaml_mapping_with_sha256(
    path: str | Path,
) -> tuple[dict[str, Any], Path, str]:
    """Read, hash, and parse one immutable byte snapshot of a YAML mapping."""

    target = _resolve_repo_path(path).resolve()
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise TimingCalibrationError(f"Could not read frozen YAML file {target}: {exc}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise TimingCalibrationError(f"Could not parse frozen YAML file {target}: {exc}") from exc
    if not isinstance(data, dict):
        raise TimingCalibrationError(f"Frozen YAML file {target} is not a mapping")
    return data, target, digest


def _require_optical_channel_fields(
    signal: str,
    settings: dict[str, Any],
) -> None:
    required = ("delay", "width", "polarity", "termination", "enabled")
    missing = [field for field in required if field not in settings]
    if missing:
        raise TimingCalibrationError(
            f"Optical recipe {signal} must explicitly define: {', '.join(missing)}"
        )


def _duration_ns(value: Any) -> float:
    text = str(value).strip().lower().replace(" ", "")
    multipliers = {
        "ps": 1e-3,
        "ns": 1.0,
        "us": 1e3,
        "ms": 1e6,
        "s": 1e9,
    }
    for suffix, multiplier in multipliers.items():
        if text.endswith(suffix):
            number = float(text[: -len(suffix)])
            if not math.isfinite(number):
                break
            return number * multiplier
    try:
        number = float(text)
    except ValueError as exc:
        raise TimingCalibrationError(
            f"Unsupported optical-recipe duration {value!r}"
        ) from exc
    if not math.isfinite(number):
        raise TimingCalibrationError(
            f"Unsupported optical-recipe duration {value!r}"
        )
    # Unitless T660 values are seconds in the documented P500 interface.
    return number * 1e9


def _render_consolidated_markdown(
    rows: list[dict[str, Any]],
    corrections: dict[str, Any],
    derived: dict[str, Any],
) -> str:
    lines = [
        "# Consolidated pump-probe timing calibration",
        "",
        "`t_master = 0` is the first programmed T660-2 event. `t_chem = 0` is the optical OPO pump arrival at the sample (TC-07).",
        "",
        f"Scope/lead B-A correction: {corrections['scope_channel_and_fixed_lead_b_minus_a_ns']:.6g} ns.  ",
        f"Splitter branch 2-1 correction: {corrections['splitter_branch_2_minus_1_ns']:.6g} ns.  ",
        f"Step 7 installed splitter/branch geometry: {corrections['installed_step7_branch_2_monitor_minus_branch_1_qswitch_ns']:.6g} ns.  ",
        f"Photodetector response delay removed: {corrections['photodetector_response_delay_ns']:.6g} ns.",
        "PicoScope timebase term: 2 ppm initial accuracy included in fixed/derived combined uncertainties and slope uncertainty; source: `docs/PicoScope/PicoScope 5000D Series Data Sheet.pdf`, p. 17, PicoScope 5244D. Annual drift remains separately reviewable unless covered by the run's calibration record.",
        "",
        "| Category | ID | Reference event | Target event | Physical connection summary | Final wiring? | Splitter? | Splitter/scope correction | Programmed range | Fixed intercept (ns) | Slope ppm (combined u) | Jitter / combined u (ns) | Uncertainty terms / provenance | Signed recipe correction ns (u) | Exact recipe formula | Use in recipe? | RSI/thesis label | Notes |",
        "|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---:|---|---|---|---|",
    ]
    for row in rows:
        slope_text = _format_number(row.get("slope_ppm"))
        slope_uncertainty_text = _format_number(
            row.get("slope_standard_error_ppm")
        )
        slope_with_uncertainty = (
            slope_text
            if slope_text == "n/a"
            else f"{slope_text} ({slope_uncertainty_text})"
        )
        jitter_with_uncertainty = (
            f"{_format_number(row.get('jitter_std_ns'))} / "
            f"{_format_number(row.get('combined_standard_uncertainty_ns'))}"
        )
        recipe_correction_text = _format_number(row.get("recipe_correction_ns"))
        recipe_correction_uncertainty_text = _format_number(
            row.get("recipe_correction_standard_uncertainty_ns")
        )
        recipe_correction_with_uncertainty = (
            recipe_correction_text
            if recipe_correction_text == "n/a"
            else f"{recipe_correction_text} ({recipe_correction_uncertainty_text})"
        )
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    row["category"],
                    row["measurement_id"],
                    row["reference_event"],
                    row["target_event"],
                    row["physical_connection_summary"],
                    row["uses_final_wiring"],
                    row["splitter_used"],
                    row["splitter_scope_correction_applied"],
                    row["programmed_delay_range"],
                    _format_number(row.get("fixed_offset_intercept_ns")),
                    slope_with_uncertainty,
                    jitter_with_uncertainty,
                    row.get("uncertainty_terms_and_provenance", "not available"),
                    recipe_correction_with_uncertainty,
                    row.get("recipe_formula", "n/a"),
                    row["use_in_timing_recipe"],
                    row["rsi_thesis_reporting_label"],
                    row["notes"],
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Derived checks",
            "",
            f"- Direct-vs-derived Q-switch closure: {derived['hf2li_extref_arrival_to_qswitch_validation_closure_ns_TC06_minus_TC04_plus_TC05']:.6g} ns.",
            f"- HF2LI EXT REF arrival to MIRcat process control at zero programmed delay: {derived['hf2li_extref_arrival_to_mircat_process_zero_programmed_ns_TC04_plus_TC08']:.6g} ns.",
            f"- Selected optical recipe EXT REF arrival to chemical zero (TC-04 evaluated at FIRE + TC-05 evaluated at Q-FIRE + TC-07): {derived['hf2li_extref_arrival_to_t_chem_selected_recipe_ns_TC04_plus_TC05_plus_TC07']:.6g} ns.",
            f"- Independent selected-recipe TC-06-at-Q + TC-07 derivation: {derived['hf2li_extref_arrival_to_t_chem_selected_recipe_ns_TC06_plus_TC07_direct_validation']:.6g} ns; direct-minus-component closure {derived['hf2li_extref_arrival_to_t_chem_selected_recipe_dual_derivation_closure_ns_direct_minus_component']:.6g} ± {derived['hf2li_extref_arrival_to_t_chem_selected_recipe_dual_derivation_closure_standard_uncertainty_ns']:.6g} ns. TC-07 detector/path/splitter terms cancel in this closure.",
            f"- Zero-programmed fixed-term optical diagnostic (not the selected operational anchor): {derived['hf2li_extref_arrival_to_t_chem_zero_programmed_ns_TC04_plus_TC05_plus_TC07']:.6g} ns; dual-derivation closure uncertainty {derived['hf2li_extref_arrival_to_t_chem_dual_derivation_closure_standard_uncertainty_ns']:.6g} ns.",
            "",
            "Slope/ppm values are reported separately and are not folded into fixed route delays.",
            "",
        ]
    )
    return "\n".join(lines)


def _format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if not math.isfinite(number) else f"{number:.6g}"


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _edge_indices(samples: list[int], threshold_adc: int, edge: str) -> list[float]:
    if edge not in {"rising", "falling"}:
        raise TimingCalibrationError(f"Unsupported edge {edge!r}")
    output: list[float] = []
    for index in range(1, len(samples)):
        previous, current = samples[index - 1], samples[index]
        crossed = (
            previous < threshold_adc <= current
            if edge == "rising"
            else previous > threshold_adc >= current
        )
        if crossed:
            span = current - previous
            output.append(float(index) if span == 0 else (index - 1) + (threshold_adc - previous) / span)
    if not output:
        raise TimingCalibrationError(f"No {edge} edge crossed {threshold_adc} ADC counts")
    return output


def _require_phrase(prompt: Callable[[str], str], message: str, expected: str) -> None:
    try:
        response = prompt(message)
    except (EOFError, KeyboardInterrupt) as exc:
        raise TimingCalibrationError("Operator confirmation was not completed; outputs remain safe-idled") from exc
    if response.strip() != expected:
        raise TimingCalibrationError(
            f"Operator confirmation did not exactly match {expected!r}; outputs remain safe-idled"
        )


def _require_enter_confirmation(prompt: Callable[[str], str], message: str) -> None:
    try:
        response = prompt(message)
    except (EOFError, KeyboardInterrupt) as exc:
        raise TimingCalibrationError(
            "Operator confirmation was not completed; outputs remain safe-idled"
        ) from exc
    if response != "":
        raise TimingCalibrationError(
            "Operator confirmation requires Enter with no typed response; outputs remain safe-idled"
        )


def _apply_verified_safe_idle(
    timing_manager: TimingRecipeManager,
    output_path: str | Path,
    *,
    recipe: str | Path | dict[str, Any] = SAFE_IDLE_RECIPE,
) -> dict[str, Any]:
    try:
        return timing_manager.apply_recipe(
            recipe,
            output_path=output_path,
        )
    except BaseException as exc:  # noqa: BLE001 - even interrupts must preserve unknown output state
        raise SafeIdleVerificationError(
            "SAFE-IDLE STOP/OFF application or readback could not be verified; "
            "do not assume outputs are off and perform the laboratory manual-stop/emergency verification procedure"
        ) from exc


def _validate_step7_corrections(
    *,
    photodetector_response_delay_ns: float | None,
    photodetector_response_uncertainty_ns: float | None,
    photodetector_response_source: str | None,
    photodetector_identifier: str | None,
    photodetector_cable_identifier: str | None,
    photodetector_characterization_date: str | None,
    photodetector_path_description: str | None,
    sample_path_standard_uncertainty_ns: float | None,
    step7_load_match_method: str | None,
    step7_load_match_standard_uncertainty_ns: float | None,
    measurement_assembly_record: str | None,
) -> dict[str, Any]:
    numeric_values = {
        "photodetector_response_delay_ns": photodetector_response_delay_ns,
        "photodetector_response_uncertainty_ns": photodetector_response_uncertainty_ns,
        "sample_path_standard_uncertainty_ns": sample_path_standard_uncertainty_ns,
        "step7_load_match_standard_uncertainty_ns": step7_load_match_standard_uncertainty_ns,
    }
    text_values = {
        "photodetector_response_source": photodetector_response_source,
        "photodetector_identifier": photodetector_identifier,
        "photodetector_cable_identifier": photodetector_cable_identifier,
        "photodetector_characterization_date": photodetector_characterization_date,
        "photodetector_path_description": photodetector_path_description,
        "step7_load_match_method": step7_load_match_method,
        "measurement_assembly_record": measurement_assembly_record,
    }
    missing = [name for name, value in numeric_values.items() if value is None]
    missing.extend(
        name for name, value in text_values.items() if not str(value or "").strip()
    )
    if missing:
        raise TimingCalibrationError(
            "Step 7 corrections, provenance, path placement, and load equivalence must be supplied before hardware execution: "
            + ", ".join(missing)
        )
    converted: dict[str, Any] = {
        name: float(value) for name, value in numeric_values.items() if value is not None
    }
    converted.update({name: str(value).strip() for name, value in text_values.items()})
    for name in (
        "photodetector_response_delay_ns",
        "photodetector_response_uncertainty_ns",
        "sample_path_standard_uncertainty_ns",
        "step7_load_match_standard_uncertainty_ns",
    ):
        if converted[name] < 0:
            raise TimingCalibrationError(f"{name} must be non-negative")
    if not all(
        math.isfinite(float(converted[name])) for name in numeric_values
    ):
        raise TimingCalibrationError("Step 7 corrections and uncertainties must be finite")
    return converted


def _require_fresh_acquisition_directory(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        raise TimingCalibrationError(f"Run directory does not exist: {path}")
    allowed_root = (REPO_ROOT / "calibration").resolve()
    try:
        path.resolve().relative_to(allowed_root)
    except ValueError as exc:
        raise TimingCalibrationError(
            "Calibration acquisition directories must be inside repository calibration/"
        ) from exc
    forbidden = ["raw_pico_traces", "timing_readbacks", "results", "workflow_summary.json"]
    present = [name for name in forbidden if (path / name).exists()]
    if present:
        raise TimingCalibrationError(
            "Refusing to reuse a run directory containing acquisition data: " + ", ".join(present)
        )
    allowed_review_files = {
        "timing_calibration_plan.json",
        "timing_calibration_plan.md",
        "workflow_status.json",
    }
    unexpected = sorted(
        child.name for child in path.iterdir() if child.name not in allowed_review_files
    )
    if unexpected:
        raise TimingCalibrationError(
            "Refusing hardware acquisition in a non-fresh run directory containing: "
            + ", ".join(unexpected)
        )


def validate_reviewed_plan_artifacts(
    run_dir: str | Path,
    requested_plan: dict[str, Any],
) -> dict[str, Any]:
    """Verify that JSON and Markdown are an unchanged, previously written plan."""

    run_path = Path(run_dir).resolve()
    json_path = run_path / "timing_calibration_plan.json"
    markdown_path = run_path / "timing_calibration_plan.md"
    if not json_path.is_file() or not markdown_path.is_file():
        raise TimingCalibrationError(
            "Hardware execution requires an existing JSON and Markdown plan from a prior plan-only invocation"
        )
    with json_path.open("r", encoding="utf-8") as handle:
        reviewed = json.load(handle)
    _assert_reviewed_plan_matches(reviewed, requested_plan)
    expected_markdown = render_plan_markdown(reviewed)
    if markdown_path.read_text(encoding="utf-8") != expected_markdown:
        raise TimingCalibrationError(
            "The human-reviewed Markdown cable plan is missing or differs from the frozen execution plan; create and review a new unique run plan"
        )
    return reviewed


def _assert_reviewed_plan_matches(
    reviewed: dict[str, Any],
    requested: dict[str, Any],
) -> None:
    """Refuse hardware if execution parameters differ from the frozen plan."""

    fields = (
        "schema_version",
        "status",
        "operator",
        "config_hash",
        "config_path",
        "configuration_files",
        "implementation",
        "time_origins",
        "sign_convention",
        "sweep",
        "rates",
        "recipes",
        "capture_policy",
        "optical_recipe_path",
        "photodetector",
        "optical_exposure_policy",
        "operator_sequence",
        "final_restoration",
        "corrections",
        "analysis",
        "prehardware_blockers",
        "output_policy",
    )
    normalized_requested = json.loads(json.dumps(requested))
    changed = [
        field
        for field in fields
        if reviewed.get(field) != normalized_requested.get(field)
    ]
    if changed:
        raise TimingCalibrationError(
            "Hardware execution parameters differ from the frozen reviewed plan: "
            + ", ".join(changed)
            + ". Create a new unique run plan and review it."
        )


def _validate_sweep(
    separations_ns: Iterable[int],
    shot_count: int,
    *,
    reduced_set_rationale: str | None = None,
) -> list[int]:
    values = [int(value) for value in separations_ns]
    if values != list(DEFAULT_SEPARATIONS_NS):
        raise TimingCalibrationError(
            "The complete calibration requires exactly 0, 100, 1000, 10000, 100000, and 1000000 ns"
        )
    if shot_count <= 0:
        raise TimingCalibrationError("shot_count must be positive")
    if shot_count != DEFAULT_SHOT_COUNT and not str(reduced_set_rationale or "").strip():
        raise TimingCalibrationError(
            f"A shot count other than the complete default ({DEFAULT_SHOT_COUNT}) requires a reduced-set rationale"
        )
    return values


def _resolve_repo_path(path: str | Path) -> Path:
    target = Path(path)
    return target if target.is_absolute() else REPO_ROOT / target


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _standard_error(values: list[float]) -> float:
    return _sample_std(values) / math.sqrt(len(values)) if values else math.nan


def _sample_std(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _pooled_jitter(points: list[dict[str, Any]]) -> float:
    variances = [float(point["jitter_std_ns"]) ** 2 for point in points]
    return math.sqrt(statistics.fmean(variances)) if variances else 0.0


def _post_trigger_span_ns(settings: dict[str, Any], interval_ns: float) -> float:
    return max(
        int(settings.get("total_samples", 0)) - int(settings.get("pre_trigger_samples", 0)),
        0,
    ) * interval_ns


def _round_up(value: int, increment: int) -> int:
    return ((value + increment - 1) // increment) * increment


def _delay_slug(value: int) -> str:
    return f"{int(value)}ns".replace("-", "m")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _log(handle: TextIO | None, message: str) -> None:
    if handle is not None:
        handle.write(f"{_utc_now()} timing_calibration {message}\n")
        handle.flush()


def _write_json_new(path: Path, data: Any) -> Path:
    return _write_text_new(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def _write_json_replace(path: Path, data: Any) -> Path:
    return _write_text_replace(
        path,
        json.dumps(data, indent=2, sort_keys=True) + "\n",
    )


def _write_text_new(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _write_rows_replace(path: Path, rows: list[dict[str, Any]]) -> Path:
    if not rows:
        raise TimingCalibrationError(f"No rows to write for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_yaml_replace(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _write_text_replace(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
