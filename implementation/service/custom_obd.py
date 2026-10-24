"""Validated personal OBD dashboard and bounded read-only sensor formulas."""
import ast
import copy
import json
import math
import operator
from pathlib import Path
import re
import threading
from runtime_support import save_json

BUILTINS = {'speed', 'rpm', 'coolant', 'load', 'throttle', 'voltage'}
DERIVED = {'acceleration', 'range', 'zeroToHundred', 'bestZeroToHundred', 'averageConsumption'}
IDENTIFIER = re.compile(r'[a-z][a-z0-9_-]{0,39}')
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
             ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
             ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor}
DEFAULT_CONFIG = {'sensors': [], 'widgets': [
    {'id': 'speed', 'source': 'builtin:speed', 'title': '', 'view': 'value', 'x': 0, 'y': 0, 'w': 1, 'h': 1},
    {'id': 'rpm', 'source': 'builtin:rpm', 'title': '', 'view': 'gauge', 'x': 1, 'y': 0, 'w': 1, 'h': 1},
    {'id': 'coolant', 'source': 'builtin:coolant', 'title': '', 'view': 'value', 'x': 2, 'y': 0, 'w': 1, 'h': 1},
    {'id': 'errors', 'source': 'errors', 'title': '', 'view': 'value', 'x': 0, 'y': 1, 'w': 1, 'h': 2},
    {'id': 'acceleration', 'source': 'derived:acceleration', 'title': '', 'view': 'graph', 'x': 1, 'y': 1, 'w': 2, 'h': 2},
], 'range': {'tankLitres': None, 'fuelLevel': None, 'fuelRate': None}}


def formula_tree(expression):
    if not isinstance(expression, str) or not 0 < len(expression) <= 96:
        raise ValueError('Use a formula of at most 96 characters')
    try: tree = ast.parse(expression, mode='eval')
    except (SyntaxError, ValueError, RecursionError) as exc: raise ValueError('Invalid formula') from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > 48: raise ValueError('Formula is too complex')
    for node in nodes:
        if isinstance(node, (ast.Expression, ast.Load, ast.UAdd, ast.USub, *OPERATORS)):
            continue
        if isinstance(node, ast.Constant) and type(node.value) in (int, float) and math.isfinite(node.value) and abs(node.value) <= 1e9:
            continue
        if isinstance(node, ast.Name) and node.id in 'ABCDEFGH' and len(node.id) == 1:
            continue
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            continue
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            continue
        raise ValueError('Formulas allow Aâ€“H, numbers and arithmetic/bitwise operators only')
    return tree


def calculate(expression, payload):
    tree = formula_tree(expression)
    def visit(node):
        if isinstance(node, ast.Constant): result = node.value
        elif isinstance(node, ast.Name):
            index = ord(node.id)-65
            if index >= len(payload): raise ValueError('Response has too few bytes for this formula')
            result = payload[index]
        elif isinstance(node, ast.UnaryOp): result = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp):
            try: result = OPERATORS[type(node.op)](visit(node.left), visit(node.right))
            except (ArithmeticError, TypeError) as exc: raise ValueError('Formula cannot be evaluated for these bytes') from exc
        else: return visit(node.body)
        if not math.isfinite(result) or abs(result) > 1e12: raise ValueError('Formula result exceeds the supported range')
        return result
    return round(visit(tree), 6)


def text(value, limit, label, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()) or any(ord(c)<32 for c in value):
        raise ValueError(f'Invalid {label}')
    return value.strip()


def validate_config(value):
    if not isinstance(value, dict) or set(value) != {'sensors','widgets','range'}:
        raise ValueError('Dashboard requires sensors, widgets and range settings')
    sensors, widgets = value['sensors'], value['widgets']
    if not isinstance(sensors,list) or len(sensors)>8 or not isinstance(widgets,list) or len(widgets)>16:
        raise ValueError('Use at most 8 custom sensors and 16 tiles')
    ids=set()
    for sensor in sensors:
        if not isinstance(sensor,dict) or set(sensor)!={'id','label','unit','mode','pid','header','bytes','formula','min','max','decimals','interval'}:
            raise ValueError('Invalid custom sensor fields')
        sid=sensor['id']
        if not isinstance(sid,str) or not IDENTIFIER.fullmatch(sid) or sid in ids: raise ValueError('Invalid or duplicate sensor ID')
        ids.add(sid)
        text(sensor['label'],40,'sensor name'); text(sensor['unit'],16,'unit',True)
        if sensor['mode'] not in ('01','22'): raise ValueError('Only read-only Mode 01 and 22 sensors are supported')
        if not isinstance(sensor['pid'],str) or not re.fullmatch(r'[0-9A-F]{2}' if sensor['mode']=='01' else r'[0-9A-F]{4}',sensor['pid']):
            raise ValueError('PID must contain 2 hex digits for Mode 01 or 4 for Mode 22')
        header=sensor['header']
        if header is not None and (not isinstance(header,str) or not re.fullmatch(r'[0-9A-F]{3}|[0-9A-F]{8}',header) or int(header,16)>(0x7ff if len(header)==3 else 0x1fffffff)):
            raise ValueError('ECU header must be an 11-bit or 29-bit CAN identifier')
        for field,low,high in (('bytes',1,8),('decimals',0,3),('interval',1,60)):
            if type(sensor[field]) is not int or not low<=sensor[field]<=high: raise ValueError(f'Invalid {field}')
        tree=formula_tree(sensor['formula'])
        if any(isinstance(n,ast.Name) and ord(n.id)-65>=sensor['bytes'] for n in ast.walk(tree)):
            raise ValueError('Formula refers to bytes outside the selected response size')
        for field in ('min','max'):
            if type(sensor[field]) not in (int,float) or not math.isfinite(sensor[field]) or abs(sensor[field])>1e9: raise ValueError('Invalid display range')
        if sensor['min']>=sensor['max']: raise ValueError('Maximum must be greater than minimum')
    sources={'builtin:'+id for id in BUILTINS}|{'derived:'+id for id in DERIVED}|{'custom:'+id for id in ids}|{'errors'}
    used=set()
    for widget in widgets:
        if not isinstance(widget,dict) or set(widget)!={'id','source','title','view','x','y','w','h'}: raise ValueError('Invalid tile fields')
        if not isinstance(widget['id'],str) or not IDENTIFIER.fullmatch(widget['id']) or widget['id'] in used: raise ValueError('Invalid or duplicate tile ID')
        used.add(widget['id']); text(widget['title'],40,'tile title',True)
        if widget['source'] not in sources or widget['view'] not in ('value','gauge','gauge2','graph'): raise ValueError('Choose an available data source and display')
        if widget['source']=='errors' and widget['view']!='value': raise ValueError('Messages use the block display')
        for field,low,high in (('x',0,3),('y',0,7),('w',1,2),('h',1,2)):
            if type(widget[field]) is not int or not low<=widget[field]<=high: raise ValueError('Tile is outside the grid')
        if widget['x']+widget['w']>4 or widget['y']+widget['h']>8: raise ValueError('Tile is outside the grid')
    for i,a in enumerate(widgets):
        for b in widgets[i+1:]:
            if a['x']<b['x']+b['w'] and b['x']<a['x']+a['w'] and a['y']<b['y']+b['h'] and b['y']<a['y']+a['h']:
                raise ValueError('Tiles cannot overlap')
    settings=value['range']
    if not isinstance(settings,dict) or set(settings)!={'tankLitres','fuelLevel','fuelRate'}: raise ValueError('Invalid range settings')
    if settings['tankLitres'] is not None and (type(settings['tankLitres']) not in (int,float) or not math.isfinite(settings['tankLitres']) or not 1<=settings['tankLitres']<=250): raise ValueError('Tank capacity must be 1â€“250 litres')
    for field in ('fuelLevel','fuelRate'):
        if settings[field] is not None and settings[field] not in sources-{'errors'}-{'derived:'+id for id in DERIVED}:
            raise ValueError('Range inputs must refer to existing sensor readings')
    return copy.deepcopy(value)


class RevisionConflict(ValueError): pass


class CustomOBDStore:
    def __init__(self,enabled=False,path=None):
        self.enabled=enabled
        self.path=path or Path.home()/'.local/share/hudiy-recreation/custom-obd.json'
        self.lock=threading.RLock(); self.revision=0; self.mapping_revision=0; self.config=copy.deepcopy(DEFAULT_CONFIG)
        if enabled:
            try:
                if self.path.is_symlink() or self.path.stat().st_size>16384: raise ValueError('Invalid dashboard file')
                raw=json.loads(self.path.read_text(encoding='utf-8'))
                if set(raw) not in ({'version','revision','config'},{'version','revision','mappingRevision','config'}) or raw['version']!=1 or type(raw['revision']) is not int or not 0<=raw['revision']<2**31: raise ValueError('Invalid dashboard file')
                mapping_revision=raw.get('mappingRevision',raw['revision'])
                if type(mapping_revision) is not int or not 0<=mapping_revision<=raw['revision']:raise ValueError('Invalid mapping revision')
                self.config=validate_config(raw['config']); self.revision=raw['revision']; self.mapping_revision=mapping_revision
            except (OSError,ValueError,TypeError): pass
    def snapshot(self):
        with self.lock: return {'enabled':self.enabled,'revision':self.revision,'mappingRevision':self.mapping_revision,'config':copy.deepcopy(self.config)}
    def save(self,data):
        if not self.enabled: raise ConnectionError('Device dashboard storage requires our Pi application')
        if not isinstance(data,dict) or set(data)!={'revision','config'} or type(data['revision']) is not int: raise ValueError('Save requires a revision and configuration')
        config=validate_config(data['config'])
        if len(json.dumps(config).encode())>15000: raise ValueError('Dashboard exceeds size limit')
        with self.lock:
            if data['revision']!=self.revision: raise RevisionConflict('The dashboard changed in another window. Reload before saving.')
            if self.path.is_symlink(): raise ValueError('Invalid dashboard file')
            revision=self.revision+1
            if revision>=2**31: raise ValueError('Dashboard revision limit reached')
            mapping_revision=revision if config['sensors']!=self.config['sensors'] else self.mapping_revision
            save_json(self.path,{'version':1,'revision':revision,'mappingRevision':mapping_revision,'config':config})
            self.config=config; self.revision=revision; self.mapping_revision=mapping_revision
            return self.snapshot()


from elm_frames import response_payloads


def decode_sensor(sensor,response):
    prefix=('41' if sensor['mode']=='01' else '62')+sensor['pid']
    for frame in response_payloads(response,prefix):
        raw=frame[len(prefix):]
        if len(raw)>=sensor['bytes']*2:
            return calculate(sensor['formula'],bytes.fromhex(raw[:sensor['bytes']*2]))
    raise ValueError('No matching data from this sensor')


def decode_codes(response):
    frames=response_payloads(response,'43')
    if not frames:raise ValueError('No supported trouble-code response')
    codes=[]
    for frame in frames:
        raw=frame[2:]
        if not raw or len(raw)%2:raise ValueError('Incomplete trouble-code response')
        data=bytes.fromhex(raw)
        if len(data)%2:
            count=data[0]; data=data[1:]
            if count*2>len(data) or any(data[count*2:]):raise ValueError('Incomplete trouble-code response')
            data=data[:count*2]
        for i in range(0,len(data),2):
            a,b=data[i:i+2]
            if not a and not b:continue
            code=f'{"PCBU"[a>>6]}{(a>>4)&3}{a&15:X}{b:02X}'
            if code not in codes:codes.append(code)
    return codes[:32]
