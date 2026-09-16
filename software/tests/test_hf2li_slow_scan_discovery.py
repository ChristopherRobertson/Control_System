"""Slow Scan verifies requested filters instead of enumerating every choice."""
import pytest
from test_regular_phase_scan import ConfigurationOnlyHF2
from control_app.devices.hf2li_service import HF2LIConfigurationError


@pytest.mark.parametrize('dual', [False, True])
def test_selected_filter_discovery_retains_auto_values_and_restores(dual):
    service = ConfigurationOnlyHF2()
    before = dict(service.nodes)
    result = service.discover_slow_scan_capabilities(dual=dual)
    assert result['verified']
    for profile in ((result['sample'], result['reference']) if dual else (result,)):
        assert profile['orders'] == (4,)
        assert profile['timeconstants_by_order'] == {4: (.001,)}
        assert profile['rates_sps']
    assert service.nodes == before
    # No exploratory filter sweeps: each selected detector gets two TC writes
    # (set and idempotence readback), then one restoration write per demod.
    tc_writes = [value for path, value in service.writes if path.endswith('/timeconstant')]
    assert len(tc_writes) == (10 if dual else 8)
    assert set(tc_writes) == {.001}


def test_explicit_filters_are_checked_independently():
    service = ConfigurationOnlyHF2()
    before = dict(service.nodes)
    result = service.discover_slow_scan_capabilities(dual=True, filter_requests={
        0: {'order': 2, 'timeconstant_s': 2e-5}, 3: {'order': 6, 'timeconstant_s': 5e-5}})
    assert result['sample']['timeconstants_by_order'] == {2: (2e-5,)}
    assert result['reference']['timeconstants_by_order'] == {6: (5e-5,)}
    assert service.nodes == before


@pytest.mark.parametrize('filter_request', [{'order': 0}, {'order': True}, {'timeconstant_s': -1}, {'timeconstant_s': float('nan')}])
def test_bad_filter_request_restores_original_nodes(filter_request):
    service = ConfigurationOnlyHF2()
    before = dict(service.nodes)
    with pytest.raises(HF2LIConfigurationError):
        service.discover_slow_scan_capabilities(filter_requests={0: filter_request})
    assert service.nodes == before


def test_filter_probe_reduction_keeps_the_same_sample_rate_choices():
    full, selected = ConfigurationOnlyHF2(), ConfigurationOnlyHF2()
    old = full.discover_phase_scan_capabilities()
    new = selected.discover_slow_scan_capabilities()
    assert old['rates_sps'] == new['rates_sps']
    assert old['timing_rate_sps'] == new['timing_rate_sps']
    assert len(selected.writes) < len(full.writes) / 2

