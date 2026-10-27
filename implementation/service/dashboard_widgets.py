"""Validated data-only dashboard layouts, independent of live phone/vehicle data."""
import copy
import datetime
import hashlib
import json
import re
import threading
import uuid
from pathlib import Path
from runtime_support import save_json

TYPES = {'clock', 'navigation', 'music', 'phone', 'connections', 'shortcuts', 'sensor', 'diagnostics'}
SOURCES = {'speed', 'rpm', 'coolant', 'load', 'throttle', 'voltage'}
DISPLAYS = {'block', 'arc', 'ticks', 'chart'}
DEFAULT_APPEARANCE = {'surface':'classic','backdrop':'aurora','accent':'theme','opacity':84,'blur':12,'radius':22,'gap':12,'motion':True}

def widget(identifier, kind, x, y, w=2, h=1, title='', source='', display='block'):
    return dict(id=identifier,type=kind,x=x,y=y,w=w,h=h,title=title,source=source,display=display)

DEFAULT_CONFIG = {'version':1,'enabled':False,'appearance':DEFAULT_APPEARANCE,'widgets':[
    widget('clock','clock',0,0,title='Clock'),
    widget('navigation','navigation',0,1,h=2,title='Navigation'),
    widget('music','music',2,0,h=3,title='Now playing'),
    widget('phone','phone',4,0,title='Phone'),
    widget('connections','connections',4,1,title='Connections'),
    widget('shortcuts','shortcuts',4,2,title='Quick access'),
]}

class DashboardConflict(ValueError):
    pass

def integer(value, low, high):
    return type(value) is int and low <= value <= high

def plain(value, maximum):
    return isinstance(value,str) and len(value)<=maximum and all(c.isprintable() for c in value)

def overlap(a,b):
    return a['x']<b['x']+b['w'] and a['x']+a['w']>b['x'] and a['y']<b['y']+b['h'] and a['y']+a['h']>b['y']

def validate_config(value):
    if not isinstance(value,dict) or set(value)!={'version','enabled','appearance','widgets'} or type(value['version']) is not int or value['version']!=1 or type(value['enabled']) is not bool:
        raise ValueError('Unsupported dashboard layout format')
    a=value['appearance']
    if not isinstance(a,dict) or set(a)!=set(DEFAULT_APPEARANCE):raise ValueError('Invalid appearance fields')
    if a['surface'] not in ('classic','glass') or a['backdrop'] not in ('aurora','midnight','sunrise','graphite'):
        raise ValueError('Choose a supported dashboard appearance')
    if not isinstance(a['accent'],str) or (a['accent']!='theme' and not re.fullmatch(r'#[0-9a-fA-F]{6}',a['accent'])):raise ValueError('Invalid dashboard accent')
    for key,low,high in [('opacity',55,100),('blur',0,24),('radius',0,36),('gap',4,24)]:
        if not integer(a[key],low,high):raise ValueError('Invalid appearance value: '+key)
    if type(a['motion']) is not bool:raise ValueError('Motion must be a boolean')
    items=value['widgets']
    if not isinstance(items,list) or len(items)>16:raise ValueError('Use at most 16 widgets')
    ids=set()
    for index,item in enumerate(items):
        if not isinstance(item,dict) or set(item)!={'id','type','title','source','display','x','y','w','h'}:raise ValueError('Invalid widget fields')
        identifier=item['id']
        if not isinstance(identifier,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}',identifier) or identifier in ids:raise ValueError('Invalid or duplicate widget identifier')
        ids.add(identifier)
        if item['type'] not in TYPES or not plain(item['title'],48):raise ValueError('Invalid widget type or title')
        if item['type']=='sensor':
            if item['source'] not in SOURCES or item['display'] not in DISPLAYS:raise ValueError('Invalid sensor source or display')
        elif item['source']!='' or item['display']!='block':raise ValueError('Only vehicle widgets select a sensor/display')
        if not all(integer(item[k],lo,hi) for k,lo,hi in [('x',0,5),('y',0,7),('w',1,6),('h',1,4)]) or item['x']+item['w']>6 or item['y']+item['h']>8:raise ValueError('Widget is outside the dashboard grid')
        if any(overlap(item,other) for other in items[:index]):raise ValueError('Dashboard widgets overlap')
    return copy.deepcopy(value)

def make_pack(config):
    return {'format':'coscaros.dashboard','version':1,'name':'My dashboard','config':validate_config(config)}

class DashboardStore:
    def __init__(self,enabled=False,path=None,export_root=None):
        self.enabled=enabled
        self.path=Path(path) if path else Path.home()/'.local/share/hudiy-recreation/dashboard-widgets.json'
        self.export_root=Path(export_root) if export_root else Path.home()/'Downloads/coscarOS-Layouts'
        self.lock=threading.RLock()
        self.config=copy.deepcopy(DEFAULT_CONFIG)
        if enabled:
            try:
                if self.path.stat().st_size>16384:raise ValueError('Layout exceeds size limit')
                self.config=validate_config(json.loads(self.path.read_text(encoding='utf-8')))
            except (OSError,ValueError,TypeError,KeyError):pass
    def snapshot(self):
        with self.lock:
            raw=json.dumps(self.config,sort_keys=True,separators=(',',':')).encode()
            return {'available':self.enabled,'config':copy.deepcopy(self.config),'revision':hashlib.sha256(raw).hexdigest()}
    def save(self,data):
        if not self.enabled:raise ConnectionError('Device dashboard storage requires the Pi application')
        if not isinstance(data,dict) or set(data)!={'revision','config'} or not isinstance(data['revision'],str):raise ValueError('Save requires a revision and configuration')
        config=validate_config(data['config'])
        with self.lock:
            if data['revision']!=self.snapshot()['revision']:raise DashboardConflict('Layout changed in another window. Reload before saving.')
            save_json(self.path,config)
            self.config=config
            return {**self.snapshot(),'saved':True}
    def export(self):
        if not self.enabled:raise ConnectionError('Device export requires the Pi application')
        with self.lock:
            if self.export_root.exists() and len(list(self.export_root.glob('*.json')))>=100:raise ValueError('Move older layout exports before creating another file')
            name='coscaros-dashboard-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.json'
            save_json(self.export_root/name,make_pack(self.config))
            return {'saved':True,'fileName':name}
