import copy
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dashboard_widgets import DashboardStore,DashboardConflict,DEFAULT_CONFIG,validate_config,make_pack,widget

class DashboardWidgetTests(unittest.TestCase):
    def test_default_preserves_original_and_returns_defensive_copies(self):
        store=DashboardStore(False)
        snapshot=store.snapshot()
        self.assertFalse(snapshot['available']);self.assertFalse(snapshot['config']['enabled'])
        snapshot['config']['widgets'].clear()
        self.assertEqual(store.snapshot()['config'],DEFAULT_CONFIG)
        with self.assertRaises(ConnectionError):store.save({'revision':snapshot['revision'],'config':DEFAULT_CONFIG})
    def test_device_layout_survives_reload_with_private_atomic_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private/dashboard.json';store=DashboardStore(True,path)
            config=copy.deepcopy(DEFAULT_CONFIG);config['enabled']=True;config['appearance'].update(surface='glass',accent='#aabbcc',blur=0)
            config['widgets'][0]['title']='My clock'
            before=store.snapshot()['revision'];saved=store.save({'revision':before,'config':config})
            self.assertTrue(saved['saved']);self.assertNotEqual(saved['revision'],before)
            self.assertEqual(DashboardStore(True,path).snapshot()['config'],config)
            self.assertFalse(path.with_name(path.name+'.tmp').exists())
            if os.name=='posix':self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
    def test_conflicting_window_cannot_overwrite_a_newer_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            store=DashboardStore(True,Path(folder)/'dashboard.json');before=store.snapshot()
            config=copy.deepcopy(DEFAULT_CONFIG);config['enabled']=True
            store.save({'revision':before['revision'],'config':config})
            with self.assertRaises(DashboardConflict):store.save({'revision':before['revision'],'config':DEFAULT_CONFIG})
            self.assertEqual(store.snapshot()['config'],config)
    def test_failed_storage_never_acknowledges_or_changes_memory(self):
        store=DashboardStore(True,Path('/unused/dashboard.json'));before=store.snapshot()
        config=copy.deepcopy(DEFAULT_CONFIG);config['enabled']=True
        with patch('dashboard_widgets.save_json',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):store.save({'revision':before['revision'],'config':config})
        self.assertEqual(store.snapshot(),before)
    def test_rejects_overlap_outside_grid_duplicate_ids_and_boolean_coordinates(self):
        for patch_value in ({'x':2},{'x':6},{'y':8},{'w':7},{'h':5},{'x':True}):
            config=copy.deepcopy(DEFAULT_CONFIG);config['widgets'][0].update(patch_value)
            with self.assertRaises(ValueError):validate_config(config)
        config=copy.deepcopy(DEFAULT_CONFIG);config['widgets'][1]['id']='clock'
        with self.assertRaises(ValueError):validate_config(config)
    def test_rejects_executable_unbounded_or_unknown_appearance(self):
        for key,value in [('accent','url(https://example.com)'),('blur',25),('opacity',54),('radius',True),('gap',float('nan')),('surface','html'),('motion',1)]:
            config=copy.deepcopy(DEFAULT_CONFIG);config['appearance'][key]=value
            with self.assertRaises((ValueError,TypeError)):validate_config(config)
        for key in ('script','url','css','path'):
            config=copy.deepcopy(DEFAULT_CONFIG);config[key]='arbitrary'
            with self.assertRaises(ValueError):validate_config(config)
    def test_sensor_views_are_allowlisted_and_never_contain_measurements(self):
        for display in ('block','arc','ticks','chart'):
            config=copy.deepcopy(DEFAULT_CONFIG);config['widgets']=[widget('sensor','sensor',0,0,title='RPM',source='rpm',display=display)]
            self.assertEqual(validate_config(config),config)
        config['widgets'][0]['source']='shell'
        with self.assertRaises(ValueError):validate_config(config)
        config['widgets'][0]['source']='speed';config['widgets'][0]['value']=100
        with self.assertRaises(ValueError):validate_config(config)
    def test_widget_count_and_plain_text_titles_are_bounded(self):
        config=copy.deepcopy(DEFAULT_CONFIG)
        for title in ('a'*49,'line\nnext','\x00'):
            config['widgets'][0]['title']=title
            with self.assertRaises(ValueError):validate_config(config)
        config=copy.deepcopy(DEFAULT_CONFIG);config['widgets']*=3
        with self.assertRaises(ValueError):validate_config(config)
    def test_corrupt_or_oversized_file_preserves_original_default(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'dashboard.json'
            for contents in ('{broken','x'*16385):
                path.write_text(contents)
                self.assertEqual(DashboardStore(True,path).snapshot()['config'],DEFAULT_CONFIG)
                self.assertEqual(path.read_text(),contents)
    def test_exports_fixed_format_to_owned_folder_without_private_live_data(self):
        with tempfile.TemporaryDirectory() as folder:
            store=DashboardStore(True,Path(folder)/'dashboard.json',Path(folder)/'exports')
            result=store.export();name=result['fileName']
            self.assertNotIn('/',name);self.assertTrue(name.endswith('.json'))
            self.assertEqual(json.loads((store.export_root/name).read_text()),make_pack(DEFAULT_CONFIG))
            if os.name=='posix':self.assertEqual(stat.S_IMODE((store.export_root/name).stat().st_mode),0o600)
    def test_export_count_limit_never_removes_previous_files(self):
        with tempfile.TemporaryDirectory() as folder:
            export=Path(folder)/'exports';export.mkdir()
            for index in range(100):(export/f'{index}.json').write_text('{}')
            store=DashboardStore(True,Path(folder)/'dashboard.json',export)
            with self.assertRaises(ValueError):store.export()
            self.assertEqual(len(list(export.iterdir())),100)
