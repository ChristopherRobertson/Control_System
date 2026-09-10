"""Compact adapter compatibility and automatic native-data reuse contracts."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import json

import numpy as np
import pytest

from control_app.measurement_host.presentation import StartSnapshot
from control_app.measurement_modules.repeated_rapid_scan.adapter import RepeatedRapidScanAdapter
from control_app.measurement_modules.repeated_rapid_scan.data import SpectralBaseline, SpectrumSupport
from control_app.measurement_modules.repeated_rapid_scan.session import (
    MeasurementSession, compatibility_conflicts, normalize_ui_settings, operational_contract,
)
from control_app.measurement_modules.repeated_rapid_scan.settings import AcquisitionIntent, RepeatedRapidScanSettings, example_settings


class Preferences:
    def __init__(self): self.values={}
    def value(self,key,default=None): return self.values.get(key,default)
    def setValue(self,key,value): self.values[key]=value
    def sync(self): pass


class Settings:
    def __init__(self,mode): self.value=example_settings(mode).to_dict(); self.caps=None
    def read(self): return deepcopy(self.value)
    def apply(self,value): self.value=deepcopy(value)
    def set_capabilities(self,caps): self.caps=caps


def adapter(mode="single",**kwargs):
    context=SimpleNamespace(mode=mode,preferences=Preferences(),configuration=lambda:{})
    return RepeatedRapidScanAdapter(context,Settings(mode),**kwargs)


def baseline_record(item, *, kind="preliminary"):
    mode=item.context.mode
    kind_baseline="background" if kind=="blank" else "q0" if mode=="dual" else "single_baseline"
    baseline=SpectralBaseline("record-baseline",mode,"optional old condition label",
        (SpectrumSupport("forward",np.array([1900.,1950.]),np.ones(2)),),kind=kind_baseline,
        complete=True,accepted=False)
    return {"experiment_id":"repeated_rapid_scan","schema_version":1,"mode":mode,"run_id":"record-1",
            "kind":kind,"status":"complete","baseline":baseline,"native_movies":[],
            "compatibility_contract":item._contract(item.read_settings())}


def snapshot(item,plan,preliminary=None):
    operation=SimpleNamespace(settings=plan.settings.to_dict() if plan else item.read_settings(),
         configuration={},calibration_records=(),sample_records=(),run_id="run-new",hardware=True)
    return StartSnapshot(operation,"measurement",plan,preliminary)


def test_rrs_compact_adapter_needs_no_approval_or_optional_metadata():
    item=adapter("dual")
    plan=item.make_plan(item.read_settings())
    assert item.validate_preliminary(None,plan)==()
    assert item.validate_operation("measurement",plan,None)==()
    assert not hasattr(item,"validate_review")
    assert not hasattr(item,"manual_action_handler")
    assert item.hardware_required("measurement",{"execution":"simulation"})
    assert not item.hardware_required("load_preliminary",{})
    original=baseline_record(item)
    assert item.validate_preliminary(original,plan)==()
    changed=item.read_settings()
    changed["condition"].update(condition_id="new descriptive label",temperature_K=77.,protein="MbCO",
        notes="optional annotation",temperature_record_id="",sample_selection_id="",
        concentration_metadata={"CO":"unknown"})
    changed["calibration_ids"]=["different optional provenance"]
    changed["instrument_state_id"]="not reviewed"
    changed["post_scans"]+=1
    assert item.validate_preliminary(original,item.make_plan(changed))==()


def test_rrs_actual_acquisition_change_invalidates_reuse_not_start():
    item=adapter("dual")
    record=baseline_record(item)
    item.session.preliminary=record
    changed=item.read_settings(); changed["sample_input_range_v"]=.3
    plan=item.make_plan(changed)
    assert "sample_input_range_v" in "; ".join(item.validate_preliminary(record,plan))
    assert item.compatible_preliminary(plan) is None
    assert item.validate_preliminary(None,plan)==()
    assert item.validate_operation("measurement",plan,None)==()
    assert item.session.preliminary is record


def test_rrs_single_blank_optional_and_same_q0_survives_background_selection():
    item=adapter()
    plan=item.make_plan(item.read_settings())
    record=baseline_record(item)
    assert item.validate_blank(plan)==()
    assert item.validate_preliminary(record,plan)==()
    item.session.blank=baseline_record(item,kind="blank")
    assert item.compatible_blank(plan) is item.session.blank
    item.session.background=replace(item.session.blank["baseline"],record_id="new-B")
    assert item.validate_preliminary(record,plan)==()


def test_rrs_contract_known_sample_and_required_direction_support():
    settings=example_settings("single").to_dict()
    settings["condition"]["sample_id"]="sample-a"
    original=operational_contract(settings)
    settings["condition"]["sample_id"]="sample-b"
    assert "sample_id" in "; ".join(compatibility_conflicts(original,operational_contract(settings)))
    settings["condition"]["sample_id"]="unassigned"
    assert compatibility_conflicts(original,operational_contract(settings))==[]
    settings["directions"]=["forward"]
    assert compatibility_conflicts(original,operational_contract(settings))==[]
    assert "reverse" in "; ".join(compatibility_conflicts(operational_contract(settings),original))


def test_rrs_legacy_records_migrate_without_approval_and_sessions_are_independent():
    single,dual=MeasurementSession("single"),MeasurementSession("dual")
    settings=example_settings().to_dict()
    legacy={"review_contract":{"settings":settings,"configuration":{},"accepted":False,
                               "sample_records":[{"reviewer":""}],"calibration_records":[]},
            "readbacks":{"mircat_pulse":{"qcl":1}}}
    assert single.check(legacy,operational_contract(settings))==()
    single.preliminary=legacy
    assert dual.preliminary is None
    single.clear()
    assert single.preliminary is None and legacy["review_contract"]["accepted"] is False


def test_rrs_adapter_forwards_worker_and_discards_incompatible_reuse_automatically():
    observed={}
    class Runner:
        def __init__(self,context,acquirer_factory=None): observed["factory"]=acquirer_factory
        def run(self,snap,worker,**kwargs):
            observed.update(snapshot=snap,worker=worker,kwargs=kwargs)
            return {"kind":"measurement","status":"complete","auto_preliminary":baseline_record(item)}
    marker=object()
    item=adapter("dual",acquirer_factory=marker,runner_factory=Runner)
    old=baseline_record(item)
    settings=item.read_settings(); settings["sample_filter_timeconstant_s"]*=2
    plan=item.make_plan(settings)
    worker=object()
    result=item.run_measurement(snapshot(item,plan,old),worker)
    assert observed["factory"] is marker
    assert observed["worker"] is worker
    assert observed["snapshot"].preliminary is None
    assert "compatibility_contract" in observed["kwargs"] and "review_contract" not in observed["kwargs"]
    assert item.session.preliminary is result["auto_preliminary"]
    assert old["baseline"].accepted is False


def test_rrs_summary_offline_actions_and_planless_capabilities_are_compact():
    item=adapter()
    rows=item.summarize_plan(item.make_plan(item.read_settings()))
    assert isinstance(rows,tuple) and all(len(row)==2 for row in rows)
    assert len(rows)<=8 and all("\n" not in str(value) for _,value in rows)
    for kind in ("load_blank","load_preliminary","load_selection","load_fit_model","fit_movie","preserve_retained","capabilities"):
        assert item.validate_operation(kind,None,None)==()
    assert item.validate_operation("measurement",None,None)
    item.settings_widget.raw_intent=lambda:{"spectral_min_cm1":"unfinished user edit"}
    item.settings_widget.read=lambda:(_ for _ in ()).throw(ValueError("invalid input"))
    request=item.read_operation_settings("capabilities")
    assert request["mode"]=="single" and request["acquisition_intent"]["spectral_min_cm1"]=="unfinished user edit"


def test_rrs_selection_metadata_has_no_approval_field_requirement(tmp_path):
    item=adapter()
    path=tmp_path/"selection.json"
    path.write_text(json.dumps({"condition_id":"optional source label","sample_id":"source label",
                               "windows":[{"lower_cm1":1903.,"upper_cm1":1907.}]}))
    selection=item.read_selection(path)
    assert "accepted" not in selection
    item.apply_selection(selection)
    assert item.read_settings()["band_windows_cm1"]==((1903.,1907.),)
    assert item.session.sample_records[0]["source_path"]==str(path.resolve())
    selected=item.read_settings()
    assert selected["manual_overrides"]["band_windows_cm1"]==[[1903.,1907.]]
    assert selected["acquisition_intent"]["spectral_min_cm1"]==selected["scan_start_cm1"]


def test_rrs_legacy_plan_load_preserves_intent_and_moves_removed_controls_to_history(tmp_path):
    item=adapter()
    settings=replace(example_settings(),sample_rate_hz=1234.,measured_scan_period_s=.2,
                     probe_pulse_width_s=140e-9,post_scans=24,pre_scans=17,
                     mircat_pulse_rate_hz=2_000_000.,mircat_current_ma=999.,
                     memory_limit_bytes=1_000_000_000).to_dict()
    settings["qcl"]=2
    settings["manual_overrides"]={"pre_scans":17,"mircat_current_ma":999.,"qcl":2}
    path=tmp_path/"legacy.json"
    payload={"record_kind":"repeated_rapid_scan_plan","schema_version":1,"experiment_id":"repeated_rapid_scan",
             "mode":"single","settings":settings}
    path.write_text(json.dumps(payload))
    original=path.read_bytes()
    migrated=item.load_plan(path)
    assert migrated["manual_overrides"]["sample_rate_hz"]==1234.
    defaults=RepeatedRapidScanSettings().to_dict()
    for key in ("probe_pulse_width_s","pre_scans","mircat_pulse_rate_hz","mircat_current_ma","memory_limit_bytes"):
        assert key not in migrated["manual_overrides"]
        assert migrated[key]==defaults[key]
        assert migrated["historical_ui_settings"]["removed_settings"][key]==settings[key]
    assert migrated["measured_scan_period_s"]==.1
    assert migrated["historical_ui_settings"]["removed_settings"]["measured_scan_period_s"]==.2
    assert migrated["historical_ui_settings"]["removed_settings"]["qcl"]==2
    assert migrated["acquisition_intent"]["observation_duration_s"]==4.8
    assert normalize_ui_settings(migrated)==migrated
    assert path.read_bytes()==original
    settings["phase_offsets_s"]=[0.,.01,.08]
    path.write_text(json.dumps(payload))
    migrated=item.load_plan(path)
    assert migrated["acquisition_intent"]["phase_count"]==3
    assert migrated["historical_ui_settings"]["removed_settings"]["phase_offsets_s"]==[0.,.01,.08]
    assert np.allclose(migrated["phase_offsets_s"],[0.,1/30,1/15],atol=5e-12,rtol=0)
    assert json.loads(path.read_text())["settings"]["phase_offsets_s"]==[0.,.01,.08]


def test_rrs_legacy_example_preferences_keep_intent_without_phantom_conditions():
    saved=example_settings().to_dict()
    saved["condition"].update(sample_id="My sample",protein="HRP-CO",temperature_K=298.15,
                             condition_id="example-hrp-room-temperature")
    saved["controls"]=["probe_only","pump_blocked"]
    saved["manual_overrides"]={"sample_rate_hz":1234.}
    context=SimpleNamespace(mode="single",preferences=Preferences(),configuration=lambda:{})
    context.preferences.setValue("settings",json.dumps(saved))
    item=RepeatedRapidScanAdapter(context,Settings("single"))
    actual=item.read_settings()
    assert actual["execution"]=="hardware" and actual["controls"]==("probe_only",)
    assert actual["condition"]["sample_id"]=="My sample"
    assert actual["condition"]["protein"]=="" and actual["condition"]["temperature_K"] is None
    assert actual["manual_overrides"]=={}


@pytest.mark.parametrize("field,value",[("mircat_current_ma",700.),("mircat_pulse_rate_hz",100000.),("mircat_pulse_width_ns",100.)])
def test_rrs_actual_qcl_changes_invalidate_baseline_reuse(field,value):
    settings=example_settings().to_dict()
    old=operational_contract(settings)
    settings[field]=value
    assert field in "; ".join(compatibility_conflicts(old,operational_contract(settings)))
    settings=example_settings().to_dict()
    settings["condition"]["preparation_id"]="prep-a"
    old=operational_contract(settings)
    settings["condition"]["preparation_id"]="prep-b"
    assert "preparation_id" in "; ".join(compatibility_conflicts(old,operational_contract(settings)))


def test_rrs_plan_budgets_existing_native_records_once_per_array_identity():
    item=adapter()
    settings=item.read_settings()
    original=item.make_plan(settings)
    shared=np.arange(4096,dtype=np.uint64)
    separate=shared.copy()
    native=SpectralBaseline("selected-blank","single","annotation",
        (SpectrumSupport("forward",shared,shared),),kind="background",complete=True)
    item.session.blank={"baseline":native,"raw":[shared,shared]}
    item.session.preliminary={"same_blank":item.session.blank}
    item.session.background=native
    item.session.result={"original":item.session.preliminary,"independent_native_copy":separate}
    measured=item.make_plan(settings)
    expected=shared.nbytes+separate.nbytes
    assert measured.capabilities.selected_baseline_bytes==expected
    assert measured.estimates["retained_run_memory_bytes"]==original.estimates["retained_run_memory_bytes"]+expected
    assert measured.estimates["storage_bytes"]==original.estimates["storage_bytes"]+expected
    item.session.clear()
    assert item.make_plan(settings).capabilities.selected_baseline_bytes==0


@pytest.mark.parametrize("qcl",[None,2])
def test_rrs_previous_unknown_or_other_qcl_support_reacquires_without_blocking_start(qcl):
    item=adapter()
    plan=item.make_plan(item.read_settings())
    record=baseline_record(item)
    record["compatibility_contract"].pop("mircat_qcl")
    if qcl is not None:
        record["readbacks"]={"mircat_pulse":{"qcl":qcl}}
    item.session.preliminary=record
    assert "mircat_qcl" in "; ".join(item.validate_preliminary(record,plan))
    assert item.compatible_preliminary(plan) is None
    assert item.validate_operation("measurement",plan,None)==()
    assert item.session.preliminary is record
    record["readbacks"]={"mircat_pulse":{"qcl":1}}
    assert item.compatible_preliminary(plan) is record
    # A conflicting observed source overrides a newly added contract annotation.
    record["compatibility_contract"]["mircat_qcl"]=1
    record["readbacks"]["mircat_pulse"]["qcl"]=2
    assert item.compatible_preliminary(plan) is None


@pytest.mark.parametrize("manual",[False,True])
def test_rrs_unsafe_saved_optical_pulse_pair_rejected_before_apply_or_save(tmp_path,manual):
    item=adapter()
    original=item.read_settings()
    plan=item.make_plan(original)
    unsafe=deepcopy(original)
    unsafe.update(mircat_pulse_rate_hz=None,mircat_pulse_width_ns=150.)
    unsafe["probe_frequency_hz"]=2_000_000.
    unsafe["acquisition_intent"]=AcquisitionIntent.from_settings(example_settings()).to_dict()
    if manual:
        unsafe["manual_overrides"]={"mircat_pulse_width_ns":151.}
    else:
        unsafe["mircat_pulse_width_ns"]=151.
    with pytest.raises(ValueError,match="30% duty"):
        item.apply_settings(unsafe)
    assert item.read_settings()==original
    assert item.context.preferences.values=={}
    output=tmp_path/"not-created.json"
    with pytest.raises(ValueError,match="30% duty"):
        item.save_plan(output,unsafe,plan)
    assert not output.exists() and item.context.preferences.values=={}
    incoming=tmp_path/"old-plan.json"
    payload={"record_kind":"repeated_rapid_scan_plan","schema_version":1,
             "experiment_id":"repeated_rapid_scan","mode":"single","settings":unsafe}
    incoming.write_text(json.dumps(payload))
    native=incoming.read_bytes()
    with pytest.raises(ValueError,match="30% duty"):
        item.load_plan(incoming)
    assert incoming.read_bytes()==native and item.read_settings()==original


def test_rrs_emitted_pulse_boundary_roundtrips_with_internal_and_ttl_settings_historical(tmp_path):
    item=adapter()
    settings=item.read_settings()
    settings.update(mircat_pulse_rate_hz=3_000_000.,mircat_pulse_width_ns=150.,
                    probe_frequency_hz=2_000_000.,probe_pulse_width_s=140e-9)
    settings["acquisition_intent"]=AcquisitionIntent.from_settings(example_settings()).to_dict()
    settings["manual_overrides"]={"mircat_pulse_rate_hz":3_000_000.,"probe_frequency_hz":2_000_000.,"mircat_pulse_width_ns":150.}
    item.apply_settings(settings)
    output=tmp_path/"boundary-plan.json"
    item.save_plan(output,item.read_settings(),item.make_plan(item.read_settings()))
    loaded=item.load_plan(output)
    assert loaded["mircat_pulse_rate_hz"] is None
    assert loaded["mircat_pulse_width_ns"]==150.
    assert loaded["probe_frequency_hz"]==2_000_000.
    assert loaded["probe_pulse_width_s"]==RepeatedRapidScanSettings().probe_pulse_width_s
    assert loaded["manual_overrides"]=={"probe_frequency_hz":2_000_000.,"mircat_pulse_width_ns":150.}
    assert loaded["historical_ui_settings"]["removed_settings"]["mircat_pulse_rate_hz"]==3_000_000.
    assert loaded["historical_ui_settings"]["removed_settings"]["probe_pulse_width_s"]==140e-9


def test_rrs_unsafe_stored_preferences_do_not_mutate_current_widget():
    stored=example_settings().to_dict()
    stored.update(execution="hardware",probe_frequency_hz=2_000_000.,mircat_pulse_width_ns=151.)
    context=SimpleNamespace(mode="single",preferences=Preferences(),configuration=lambda:{})
    serialized=json.dumps(stored)
    context.preferences.setValue("settings",serialized)
    widget=Settings("single")
    original=widget.read()
    item=RepeatedRapidScanAdapter(context,widget)
    assert item.read_settings()==original
    assert context.preferences.value("settings")==serialized


def test_rrs_current_auto_choices_and_analysis_inputs_survive_repeated_normalization():
    settings=RepeatedRapidScanSettings(mode="dual").to_dict()
    settings["acquisition_intent"]=AcquisitionIntent().to_dict()
    settings.update(sample_rate_hz=1234.,reference_rate_hz=5678.,mircat_current_ma=999.)
    settings["manual_overrides"]={"sample_rate_hz":None,"reference_rate_hz":5678.,
                                  "band_windows_cm1":[[1903.,1907.]],"mircat_current_ma":999.}
    settings["condition"].update(sample_id="Actual sample",preparation_id="actual preparation",temperature_K=77.)
    settings["acquisition_intent"]["sample_name"]="Actual sample"
    normalized=normalize_ui_settings(settings,"dual")
    assert normalized["sample_rate_hz"]==1234. and "sample_rate_hz" not in normalized["manual_overrides"]
    assert normalized["manual_overrides"]["reference_rate_hz"]==5678.
    assert normalized["manual_overrides"]["band_windows_cm1"]==[[1903.,1907.]]
    assert normalized["condition"]["preparation_id"]=="actual preparation"
    assert normalized["condition"]["temperature_K"]==77.
    assert normalized["mircat_current_ma"] is None
    assert normalize_ui_settings(normalized,"dual")==normalized


def test_rrs_legacy_ui_roundtrip_canonicalizes_sequences_without_casting_provenance(tmp_path):
    item=adapter()
    legacy=replace(example_settings(),phase_offsets_s=(0.,),directions=("forward",)).to_dict()
    legacy["condition"]["sample_id"]="unassigned"
    legacy["manual_overrides"]={"band_windows_cm1":((1903.,1907.),)}
    native_origin=2**63+17
    legacy["historical_ui_settings"]={"native_origin":native_origin,"prior_choices":("qcl",2)}
    original=deepcopy(legacy)
    item.apply_settings(legacy)
    current=item.read_settings()
    assert current["acquisition_intent"]["sample_name"]=="Sample"
    assert current["condition"]["sample_id"]=="Sample"
    assert current["historical_ui_settings"]["legacy_sample_id"]=="unassigned"
    assert current["historical_ui_settings"]["removed_settings"]["directions"]==["forward"]
    assert current["historical_ui_settings"]["prior_choices"]==["qcl",2]
    assert current["manual_overrides"]["band_windows_cm1"]==[[1903.,1907.]]
    path=tmp_path/"roundtrip.json"
    item.save_plan(path,current,item.make_plan(current))
    loaded=item.load_plan(path)
    assert loaded==current
    assert loaded["historical_ui_settings"]["native_origin"]==native_origin
    assert type(loaded["historical_ui_settings"]["native_origin"]) is int
    item.apply_settings(loaded)
    assert item.read_settings()==current and legacy==original
    record=baseline_record(item)
    changed=deepcopy(current)
    changed["acquisition_intent"]["sample_name"]="Other sample"
    item.apply_settings(changed)
    assert "sample_id" in "; ".join(item.validate_preliminary(record,item.make_plan(item.read_settings())))
