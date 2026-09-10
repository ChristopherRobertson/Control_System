from dataclasses import replace
import json

import numpy as np
import pytest

from control_app.measurement_modules.repeated_rapid_scan.data import NativeMovie, NativeScan, NativeStream, ScanTrajectory
from control_app.measurement_modules.repeated_rapid_scan.persistence import load_run, save_run


def native_record():
    ticks=np.array([2**62+1,2**62+2,2**62+9],np.uint64)
    values=np.array([1.23456789012345,np.nan,-0.0],dtype=np.float64)
    sample=NativeStream(ticks,values,flags={"clipped":np.array([False,True,False])},
                        timestamp_unit_s=1e-9,timestamp_origin=2**62)
    trajectory=ScanTrajectory(ticks,np.array([1900.,1901.,1902.]),"axis-native",timestamp_unit_s=1e-9,timestamp_origin=2**62)
    movie=NativeMovie("partial-movie",.003,(NativeScan(7,sample,trajectory),),(),"dual","condition-1",status="interrupted")
    return {"run_id":"run-1","mode":"dual","condition_id":"condition-1", "native_movies":(movie,),
            "raw_chunks":{"/device/demods/0/sample":[{"timestamp":ticks,"x":values}]},
            "restoration":{"success":False,"errors":["RF restore failed"]},
            "excluded_records":[b"raw-invalid-payload"],"status":"interrupted","notes":"No automatic retry"}


def test_rrs_lossless_native_partial_rejected_and_cleanup_round_trip(tmp_path):
    original=native_record()
    output=save_run(tmp_path/"host-reserved",record=original)
    assert output==tmp_path/"host-reserved"
    saved=load_run(output,expected_mode="dual",expected_condition_id="condition-1")
    restored=saved.record
    old=original["native_movies"][0].scans[0].sample
    new=restored["native_movies"][0].scans[0].sample
    assert new.timestamps_s.dtype==np.dtype("uint64")
    assert old.timestamps_s.tobytes()==new.timestamps_s.tobytes()
    assert old.values.tobytes()==new.values.tobytes()
    assert restored["restoration"]==original["restoration"]
    assert restored["excluded_records"]==[b"raw-invalid-payload"]
    assert restored["native_movies"][0].status=="interrupted"
    assert restored["raw_chunks"]["/device/demods/0/sample"][0]["timestamp"].tobytes()==old.timestamps_s.tobytes()


def test_rrs_run_compatibility_explicit_ids_versions_and_mode(tmp_path):
    output=save_run(tmp_path,record=native_record())
    with pytest.raises(ValueError,match="mode mismatch"):
        load_run(output,expected_mode="single")
    with pytest.raises(ValueError,match="Condition mismatch"):
        load_run(output,expected_condition_id="wrong")
    manifest=json.loads((output/"run.json").read_text())
    manifest["schema_version"]=99
    (output/"run.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match="schema"):
        load_run(output)


def test_rrs_existing_run_is_never_overwritten_and_ids_cannot_escape(tmp_path):
    output=save_run(tmp_path,"dual","run-a",record=native_record())
    assert output==tmp_path/"repeated_rapid_scan"/"dual"/"run-a"
    previous=(output/"native.npz").read_bytes()
    with pytest.raises(FileExistsError): save_run(output,record=native_record())
    assert (output/"native.npz").read_bytes()==previous
    with pytest.raises(ValueError): save_run(tmp_path,"dual","../escape",record=native_record())


def test_rrs_storage_failure_retains_partial_write_and_native_in_memory(tmp_path,monkeypatch):
    original=native_record()
    ticks=original["native_movies"][0].scans[0].sample.timestamps_s.copy()
    def fail(handle,**arrays):
        handle.write(b"partial-native")
        raise OSError("storage full")
    monkeypatch.setattr(np,"savez",fail)
    with pytest.raises(OSError,match="storage full"):
        save_run(tmp_path,record=original)
    assert not (tmp_path/"run.json").exists()
    assert len(list(tmp_path.glob("native.*.partial.npz")))==1
    np.testing.assert_array_equal(original["native_movies"][0].scans[0].sample.timestamps_s,ticks)


def test_rrs_inventory_is_information_not_a_digest_acceptance_gate(tmp_path):
    output=save_run(tmp_path,record=native_record())
    manifest=json.loads((output/"run.json").read_text())
    manifest["array_inventory"]={}
    manifest["informational_checksum"]="changed"
    (output/"run.json").write_text(json.dumps(manifest))
    assert load_run(output).record["status"]=="interrupted"
