"""Physical wiring contracts shared by configuration, recipes and the workbook."""
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
import yaml

from control_app.devices.t660_service import T660Service
from control_app.workflows.timing_recipe_manager import TimingRecipeError, TimingRecipeManager


ROOT = Path(__file__).resolve().parents[2]


def document(name):
    return yaml.safe_load((ROOT / 'instrument' / name).read_text(encoding='utf-8'))


def test_probe_and_pump_maps_and_physical_clock_have_separate_owners():
    config = document('hardware_configuration.yaml')
    devices = config['devices']
    assert devices['t660_1']['channel_map'] == {
        'A': 'hf2li_extref', 'B': 'mircat_trig_in', 'C': 't660_2_trig_in', 'D': None,
    }
    assert devices['t660_2']['channel_map'] == {
        'A': 'ndyag_fire', 'B': 'ndyag_q_switch', 'C': 'mircat_db9_pin_4_process_trigger', 'D': None,
    }
    assert devices['t660_1']['trigger_input']['connected'] is False
    assert devices['t660_2']['trigger_input']['source_device'] == 't660_1'
    assert devices['t660_2']['trigger_input']['source_channel'] == 'C'
    clock = config['timing_routes']['clock_distribution']
    assert clock['source'] == 't660_2.CLOCK'
    assert clock['frequency_hz'] == 10_000_000
    assert clock['source_mode'] == devices['t660_2']['clock_connector']['mode'] == 'OUT'
    assert clock['t660_1_mode'] == devices['t660_1']['clock_connector']['mode'] == 'IN'
    assert set(clock['destinations']) == {'t660_1.CLOCK', 'hf2li.clock_input'}
    assert clock['hf2li_clock_source'] == 'external'
    assert T660Service('t660_2', devices['t660_2'])._supports_frames_engine()
    assert not T660Service('t660_1', devices['t660_1'])._supports_frames_engine()


def test_hf2li_nested_routes_agree_and_dio1_is_unconnected():
    config = document('hardware_configuration.yaml')
    inputs = config['devices']['hf2li']['timing_inputs']
    assert inputs['extref']['source_device'] == 't660_1'
    assert inputs['extref']['source_channel'] == 'A'
    assert inputs['daq_trigger'].get('source_device') is None
    assert inputs['daq_trigger'].get('source_channel') is None
    assert inputs['daq_trigger']['connected'] is False
    observed = config['timing_routes']['observed_timing_inputs']
    assert [observed[f'mircat_db9_pin_{pin}']['hf2li_dio_bit'] for pin in (1, 2, 3)] == [20, 21, 22]
    assert observed['mircat_db9_pin_2']['picoscope_input'] == 'EXT'
    optional = config['timing_routes']['optional_acquisition_window']
    assert optional['connected'] is False
    assert optional['candidate_source'] == 't660_2.D'


def test_breakout_rows_match_timing_chain_and_scope_branch():
    wiring = document('wiring_map.yaml')
    assert wiring['critical_timing_chain']['t660_1']['CHD'] is None
    assert wiring['critical_timing_chain']['t660_2']['CHD'] is None
    breakout = wiring['breakouts']['hf2li_dio_breakout']
    assert breakout['timing_inputs']['DIO0_EXT_REF'] == 't660_1.CHA'
    assert breakout['timing_inputs'].get('DIO1_DAQ_TRIGGER') is None
    mircat = wiring['breakouts']['mircat_db9_breakout']
    assert mircat['pin_4']['source'] == 't660_2.CHC'
    pin2 = mircat['pin_2']
    assert 'hf2li.DIO21' in str(pin2)
    assert 'picoscope' in str(pin2).lower() and 'EXT' in str(pin2).upper()


@pytest.mark.parametrize('unit', ['t660_1', 't660_2'])
def test_recipe_cannot_enable_either_spare_channel(unit):
    manager = TimingRecipeManager()
    recipe = manager.load_recipe('instrument/recipes/safe_idle.yaml')
    recipe['t660'][unit]['channels']['D']['enabled'] = True
    with pytest.raises(TimingRecipeError, match='spare and unwired'):
        manager.validate_recipe(recipe)


def test_workbook_current_connections_include_probe_pump_spares_and_direct_ext():
    # Read the standard XLSX format without importing an Excel authoring package.
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(ROOT / 'instrument/wiring_table.xlsx') as package:
        strings = []
        if 'xl/sharedStrings.xml' in package.namelist():
            strings = [''.join(si.itertext()) for si in ET.fromstring(package.read('xl/sharedStrings.xml'))]
        rows = []
        for row in ET.fromstring(package.read('xl/worksheets/sheet1.xml')).findall('.//s:row', ns):
            values = []
            for cell in row.findall('s:c', ns):
                value = cell.find('s:v', ns)
                if cell.get('t') == 's': text = strings[int(value.text)]
                elif cell.get('t') == 'inlineStr': text = ''.join(cell.find('s:is', ns).itertext())
                else: text = value.text if value is not None else ''
                values.append(text)
            rows.append(values)
    assert any(row[:4] == ['CH B', 'Output', 'TRIG IN', 'MIRcat'] for row in rows)
    assert any(row[:4] == ['CH A', 'Output', 'EXT DB9 pin 7: Fire', 'YAG'] for row in rows)
    assert sum(row[:3] == ['CH D', 'Output', 'SPARE / DISCONNECTED'] for row in rows) == 2
    assert any(row[:4] == ['EXT Trigger', 'Input', 'DB9 pin 2: Tuned / Sweep Active', 'MIRcat'] for row in rows)
    assert any(row[:4] == ['DB9 pin 2: Tuned / Sweep Active', 'Output', 'DIO 21; EXT', 'HF2LI; PicoScope'] for row in rows)
