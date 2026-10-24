"""Private, bounded diagnostic sessions. Only the OBD polling worker talks to the car."""
import copy
import csv
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import queue
import re
import threading
import time
import uuid

from runtime_support import save_json

SESSION_ID = re.compile(r'\d{8}T\d{6}Z-[0-9a-f]{12}')
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_SESSIONS = 20
MIB = 1024 * 1024
DEFAULT_SETTINGS = {'autoRecord':False, 'rawReplies':True, 'samples':True, 'customSensors':True,
                    'liveData':True, 'freezeFrame':True, 'monitorTests':True, 'vehicleInfo':True, 'faultCodes':True,
                    'scanIntervalSeconds':1, 'sampleIntervalSeconds':1, 'diagnosticIntervalSeconds':30,
                    'snapshotIntervalSeconds':60, 'maxSessionMiB':32, 'maxTotalMiB':256, 'maxSessions':20}


def validate_settings(data):
    if not isinstance(data,dict) or set(data)!=set(DEFAULT_SETTINGS):raise ValueError('Provide the complete logging settings')
    for key in ('autoRecord','rawReplies','samples','customSensors','liveData','freezeFrame','monitorTests','vehicleInfo','faultCodes'):
        if type(data[key]) is not bool:raise ValueError(f'{key} must be boolean')
    for key,low,high in (('scanIntervalSeconds',1,30),('sampleIntervalSeconds',1,60),('diagnosticIntervalSeconds',10,300),('snapshotIntervalSeconds',10,600),('maxSessionMiB',1,64),('maxTotalMiB',16,1024),('maxSessions',1,100)):
        if type(data[key]) is not int or not low<=data[key]<=high:raise ValueError(f'{key} must be an integer from {low} to {high}')
    if data['maxSessionMiB']>data['maxTotalMiB']:raise ValueError('Session size must not exceed total storage')
    return copy.deepcopy(data)


def safe_cell(value):
    if type(value) in (int,float) and math.isfinite(value):return value
    text = '' if value is None else str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


class OBDRecorder:
    def __init__(self, root=None, max_file=MAX_FILE, max_total=MAX_TOTAL, max_sessions=MAX_SESSIONS, export_root=None):
        self.root = Path(root) if root else Path.home()/'.local/share/hudiy-recreation/obd-logs'
        self.max_file, self.max_total, self.max_sessions = max_file, max_total, max_sessions
        self.lock = threading.RLock()
        self.export_lock = threading.Lock()
        self.export_write_lock = threading.Lock()
        self.export_root = Path(export_root) if export_root else Path.home()/'Downloads/coscarOS-OBD-Logs'
        self.active = None
        self.jobs = None
        self.thread = None
        self.finishing = False
        self.error = None
        self.auto_record = False
        self.settings = copy.deepcopy(DEFAULT_SETTINGS)
        self.session_settings = None
        self.last_sample = None
        self.coverage = {}
        self.generation = 0
        self.marker_generation = 0
        self.has_vehicle_data = False
        try:
            self._directory()
            path = self.root/'settings.json'
            if path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024:
                data = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(data,dict) and set(data)=={'autoRecord'}:data={**DEFAULT_SETTINGS,**data}
                self.settings=validate_settings(data)
                self.auto_record=self.settings['autoRecord']
                self.max_file=self.settings['maxSessionMiB']*MIB;self.max_total=self.settings['maxTotalMiB']*MIB;self.max_sessions=self.settings['maxSessions']
            # Sessions without a completed footer remain downloadable and are explicitly interrupted.
            for item in self._sessions():
                if item.get('state') == 'recording':
                    item.update(state='interrupted', reason='Service stopped before recording was finalized', endedAt=None)
                    self._meta(item)
        except (OSError, ValueError, TypeError):
            self.error = 'Diagnostic storage is unavailable'

    def _directory(self):
        if any(p.is_symlink() for p in [self.root, *self.root.parents]):
            raise ValueError('Log storage must not contain symbolic links')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == 'posix': os.chmod(self.root, 0o700)

    def _path(self, identifier, suffix='.jsonl'):
        if not isinstance(identifier, str) or not SESSION_ID.fullmatch(identifier):
            raise ValueError('Invalid log session')
        self._directory()
        path = self.root/(identifier+suffix)
        if path.is_symlink(): raise ValueError('Symbolic log files are not allowed')
        return path

    def _meta(self, item):
        path = self._path(item['id'], '.meta.json')
        if path.with_name(path.name+'.tmp').is_symlink(): raise ValueError('Invalid log metadata')
        save_json(path, item)

    def _sessions(self):
        self._directory()
        found = []
        # Fixed maximum count avoids reading unrelated or unbounded directory contents.
        for path in sorted(self.root.glob('*.jsonl'), reverse=True):
            if len(found) >= 100: break
            if not SESSION_ID.fullmatch(path.stem) or path.is_symlink() or not path.is_file(): continue
            item = {'id':path.stem, 'startedAt':None, 'endedAt':None, 'state':'interrupted',
                    'reason':'Recording metadata is missing', 'events':None, 'mode':'unknown'}
            meta = self._path(path.stem, '.meta.json')
            try:
                if meta.stat().st_size <= 8192:
                    data = json.loads(meta.read_text(encoding='utf-8'))
                    valid=isinstance(data,dict) and data.get('id')==path.stem
                    valid=valid and data.get('state') in ('recording','complete','interrupted') and data.get('mode') in ('live','simulator','disconnected','unknown')
                    valid=valid and type(data.get('events')) is int and 0<=data['events']<2**31
                    valid=valid and type(data.get('startedAt')) in (int,float) and math.isfinite(data['startedAt'])
                    valid=valid and (data.get('endedAt') is None or type(data['endedAt']) in (int,float) and math.isfinite(data['endedAt']))
                    valid=valid and (data.get('reason') is None or isinstance(data['reason'],str) and len(data['reason'])<=512)
                    if valid:
                        item.update({key:data[key] for key in item if key in data})
                        if 'captureSettings' in data:item['captureSettings']=validate_settings(data['captureSettings'])
                        if type(data.get('sessionLimitBytes')) is int:item['sessionLimitBytes']=data['sessionLimitBytes']
                        if isinstance(data.get('captureSummary'),dict):item['captureSummary']=data['captureSummary']
            except (OSError, ValueError): pass
            item['bytes'] = path.stat().st_size
            found.append(item)
        return sorted(found,key=lambda item:(item.get('startedAt') or 0,item['id']),reverse=True)

    def snapshot(self):
        with self.lock:
            try:
                sessions = self._sessions()
                if self.active:
                    sessions = [copy.deepcopy(self.active) if s['id'] == self.active['id'] else s for s in sessions]
            except (OSError, ValueError): sessions = []; self.error = 'Diagnostic storage is unavailable'
            return {'recording':bool(self.active), 'finishing':self.finishing, 'active':copy.deepcopy(self.active),
                    'sessions':sessions, 'autoRecord':self.auto_record, 'error':self.error,
                    'coverage':copy.deepcopy(self.coverage), 'generation':self.generation,
                    'settings':copy.deepcopy(self.settings),
                    'limits':{'sessionBytes':self.max_file, 'totalBytes':self.max_total, 'sessions':self.max_sessions}}

    def set_auto(self, enabled):
        if type(enabled) is not bool: raise ValueError('autoRecord must be boolean')
        return self.set_settings({**self.settings,'autoRecord':enabled})

    def set_settings(self, data):
        settings=validate_settings(data)
        with self.lock:
            self._directory()
            path = self.root/'settings.json'
            if path.is_symlink() or path.with_name(path.name+'.tmp').is_symlink(): raise ValueError('Invalid logging settings')
            save_json(path, settings)
            self.settings=settings;self.auto_record=settings['autoRecord']
            self.max_file=settings['maxSessionMiB']*MIB;self.max_total=settings['maxTotalMiB']*MIB;self.max_sessions=settings['maxSessions']
        return self.snapshot()

    def capture_settings(self):
        with self.lock:return copy.deepcopy(self.session_settings or self.settings)

    def start(self, context=None):
        with self.lock:
            if self.active: return self.snapshot()
            if self.finishing: raise ConnectionError('The previous recording is still finishing')
            self._directory()
            sessions = self._sessions()
            if len(sessions) >= self.max_sessions or sum(s['bytes'] for s in sessions) >= self.max_total:
                raise ValueError('Log storage is full. Export and remove a finished session first.')
            identifier = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:12]
            path = self._path(identifier)
            fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os, 'O_NOFOLLOW', 0), 0o600)
            stream = os.fdopen(fd, 'wb')
            now = time.time()
            item = {'id':identifier, 'startedAt':now, 'endedAt':None, 'state':'recording', 'reason':None,
                    'events':0, 'bytes':0, 'mode':(context or {}).get('mode', 'disconnected')}
            item['captureSettings']=copy.deepcopy(self.settings)
            item['sessionLimitBytes']=min(self.max_file,self.max_total-sum(s['bytes'] for s in sessions))
            try: self._meta(item)
            except Exception:
                stream.close(); path.unlink(); raise
            self.active = item; self.error = None; self.coverage = {}; self.generation += 1
            self.has_vehicle_data = False
            self.session_settings=copy.deepcopy(self.settings);self.last_sample=None
            jobs = queue.Queue(maxsize=256); self.jobs = jobs
            budget = min(self.max_file, self.max_total-sum(s['bytes'] for s in sessions))
            item['sessionLimitBytes']=budget
            item['captureSettings']=copy.deepcopy(self.session_settings)
            self.thread = threading.Thread(target=self._write, args=(stream, jobs, item, budget), daemon=True)
            self.record('session', {'version':2, 'context':context or {}, 'readOnly':True,
                        'captureSettings':copy.deepcopy(self.session_settings),
                        'scope':'Advertised 01/02/06/09, 03/07/0A, discovered CAN ECU UDS fault status/details, configured 01/22, raw exchanges and per-reading times'})
            self.thread.start()
        return self.snapshot()

    def record(self, kind, data):
        with self.lock:
            if not self.active or self.finishing: return
            settings=self.session_settings or self.settings
            if kind=='exchange' and not settings['rawReplies']:return
            if kind=='sample':
                if not settings['samples']:return
                now=time.monotonic()
                if self.last_sample is not None and now-self.last_sample<settings['sampleIntervalSeconds']:return
                self.last_sample=now
                if any(type(value) in (int,float) and math.isfinite(value) for value in data.get('values',{}).values()):
                    self.has_vehicle_data=True
            if kind=='diagnostic' and not data.get('error'):self.has_vehicle_data=True
            event = {'timestamp':time.time(), 'elapsed':round(time.time()-self.active['startedAt'], 6), 'type':kind, 'data':copy.deepcopy(data)}
            try:
                line = json.dumps(event, allow_nan=False, separators=(',', ':')).encode('utf-8')+b'\n'
                if len(line)<=24576:self.jobs.put_nowait(line)
                else:
                    # Long decoded responses remain reconstructable in bounded events.
                    serialized=json.dumps(data,allow_nan=False,separators=(',',':'))
                    if len(serialized)>1024*1024:raise ValueError('Diagnostic event exceeded size limit')
                    chunks=[serialized[i:i+4096] for i in range(0,len(serialized),4096)]
                    event_id=uuid.uuid4().hex
                    for index,chunk in enumerate(chunks):
                        part={**event,'type':kind+'-part','data':{'eventId':event_id,'part':index,
                              'parts':len(chunks),'encoding':'json','content':chunk}}
                        self.jobs.put_nowait(json.dumps(part,separators=(',',':')).encode()+b'\n')
            except (queue.Full, ValueError, TypeError):
                self.finishing = True
                self.error = 'Recording stopped: diagnostic queue or event limit exceeded; session is incomplete'
                self.active['reason'] = self.error

    def _write(self, stream, jobs, item, budget):
        last_sync = time.monotonic()
        reason = None
        try:
            while True:
                try: line = jobs.get(timeout=.1)
                except queue.Empty:
                    if time.monotonic()-last_sync>=1:
                        stream.flush();os.fsync(stream.fileno());last_sync=time.monotonic()
                    with self.lock:
                        if self.finishing: break
                    continue
                if item['bytes']+len(line)+2048 > budget:
                    reason = 'Storage limit reached'; break
                stream.write(line)
                with self.lock: item['events'] += 1; item['bytes'] += len(line)
                if time.monotonic()-last_sync >= 1:
                    stream.flush(); os.fsync(stream.fileno()); last_sync = time.monotonic()
            reason = reason or item.get('reason') or 'Stopped by user'
            with self.lock:
                summary=self._capture_summary()
                item['captureSummary']=summary
            end = json.dumps({'timestamp':time.time(), 'type':'end', 'data':{'reason':reason,'captureSummary':summary}}, separators=(',', ':')).encode()+b'\n'
            if item['bytes']+len(end) <= budget:
                stream.write(end); item['bytes'] += len(end); item['events'] += 1
            stream.flush(); os.fsync(stream.fileno())
        except OSError:
            reason = 'Storage write failed; session may be incomplete'
        finally:
            try:stream.close()
            except OSError:reason='Storage close failed; session may be incomplete'
            with self.lock:
                item.update(state='complete' if reason in ('Stopped by user', 'Service shutdown') else 'interrupted', endedAt=time.time(), reason=reason)
                if item['state']=='interrupted': self.error = reason
                try: self._meta(item)
                except (OSError, ValueError): self.error = 'Could not finalize log metadata; session may be incomplete'
                self.active = None; self.finishing = False

    def stop(self, reason='Stopped by user'):
        with self.lock:
            if self.active:
                self.active['reason'] = self.active.get('reason') or reason
                self.finishing = True
            thread = self.thread
        if thread: thread.join(timeout=4)
        return self.snapshot()

    def close(self): self.stop('Service shutdown')

    def _capture_summary(self):
        coverage=self.coverage
        return {'hasVehicleData':self.has_vehicle_data or coverage.get('hasVehicleData',False),
                'firstSweepComplete':coverage.get('firstSweepComplete',False),
                'scheduledReadings':coverage.get('scheduledReadings',0),
                'queriedReadings':coverage.get('queriedReadings',0),
                'successfulReadings':coverage.get('successfulReadings',0),
                'unavailableReadings':len(coverage.get('unavailable',{})),
                'ecuCount':len(coverage.get('ecuHeaders',[])),
                'scope':'Exposed read-only diagnostics; not all proprietary vehicle data'}

    def mark(self):
        with self.lock:
            if not self.active or self.finishing:raise ValueError('Start recording before marking a fault')
            self.marker_generation+=1
            self.record('marker',{'label':'Power loss / engine warning','marker':self.marker_generation})
        return self.snapshot()

    def connection(self, connected, mode, error=None):
        if connected and self.auto_record and not self.active and not self.finishing:
            try: self.start({'connected':True, 'mode':mode, 'automatic':True})
            except (OSError, ValueError, ConnectionError) as exc: self.error = str(exc)
        if connected:
            with self.lock:
                if self.active:self.active['mode']=mode
        self.record('connection', {'connected':connected, 'mode':mode, 'error':error})

    def begin_connection(self, mode):
        if self.auto_record and not self.active and not self.finishing:
            try:self.start({'connected':False,'mode':mode,'automatic':True})
            except (OSError,ValueError,ConnectionError) as exc:self.error=str(exc)
        self.record('connection-attempt',{'mode':mode})

    def exchange(self, command, response=None, error=None, header=None, started=None):
        received=time.time()
        # Preserve long/partial traffic in bounded events; parts share one exchange ID.
        exchange_id=uuid.uuid4().hex
        truncated=bool(response and len(response)>65536) or bool(error)
        response=response[:65536] if response else None
        chunks=[response[i:i+4096] for i in range(0,len(response),4096)] if response else [None]
        for index,chunk in enumerate(chunks):
            self.record('exchange', {'command':command, 'ecuHeader':header, 'requestedAt':started,
                                    'receivedAt':received,'durationSeconds':max(0,received-started) if started is not None else None,
                                    'exchangeId':exchange_id,'part':index,'parts':len(chunks),
                                    'response':chunk,'responseTruncated':truncated,'responseComplete':not truncated,
                                    'error':str(error)[:512] if error else None})

    def set_coverage(self, coverage):
        with self.lock:
            self.coverage = copy.deepcopy(coverage)
            if self.active:self.active['captureSummary']=self._capture_summary()

    def remove(self, identifier, confirmed):
        if confirmed is not True: raise ValueError('Confirm removal of this saved recording')
        with self.lock:
            if self.active and self.active['id']==identifier: raise ValueError('Stop recording before removing it')
            path = self._path(identifier)
            if not path.is_file(): raise FileNotFoundError('Recording not found')
            path.unlink()
            self._path(identifier, '.meta.json').unlink(missing_ok=True)
        return self.snapshot()

    def preview(self, identifier):
        with self.lock:
            path=self._path(identifier)
            fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        with os.fdopen(fd,'rb') as stream:
            size=os.fstat(stream.fileno()).st_size
            start=max(0,size-65536);stream.seek(start);lines=stream.read(65536).splitlines()
        if start:lines=lines[1:]
        events=[]
        for line in lines:
            try:
                event=json.loads(line)
                if isinstance(event,dict):events.append(event)
            except (ValueError,TypeError):pass
        return {'id':identifier,'events':events[-40:]}

    def export(self, identifier, format):
        if not self.export_lock.acquire(blocking=False):raise ConnectionError('Another export is still being prepared')
        try:return self._export(identifier,format)
        finally:self.export_lock.release()

    def _export(self, identifier, format):
        if format not in ('jsonl', 'csv'): raise ValueError('Choose JSONL or CSV')
        with self.lock:
            if self.active and self.active['id']==identifier: raise ValueError('Stop recording before exporting it')
            path = self._path(identifier)
            if path.stat().st_size > 64*MIB: raise ValueError('Recording exceeds the export size limit')
            fd = os.open(path, os.O_RDONLY|getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as stream: raw = stream.read(64*MIB+1)
        if len(raw)>64*MIB: raise ValueError('Recording exceeds the export size limit')
        if format=='jsonl': return raw, 'application/x-ndjson'
        output = io.StringIO(newline=''); writer = csv.writer(output)
        writer.writerow(['timestamp_utc','elapsed_seconds','type','command','ecu_header','source','value','unit','error','raw_response','data_json'])
        builtin_units={'speed':'km/h','rpm':'rpm','coolant':'°C','load':'%','throttle':'%','voltage':'V'}
        derived_units={'acceleration':'m/s²','range':'km','averageConsumption':'L/100 km','zeroToHundred':'s','bestZeroToHundred':'s'}
        custom_units={}
        for line in raw.splitlines():
            try:
                event = json.loads(line); data = event.get('data', {})
                stamp = datetime.fromtimestamp(event['timestamp'], timezone.utc).isoformat()
                row = [stamp,event.get('elapsed'),event.get('type'),data.get('command'),data.get('ecuHeader'),data.get('source'),data.get('value'),data.get('unit'),data.get('error'),data.get('response'),json.dumps(data, ensure_ascii=False)]
                writer.writerow([safe_cell(value) for value in row])
                if event.get('type')=='definitions':
                    custom_units={sensor['id']:sensor['unit'] for sensor in data.get('config',{}).get('sensors',[])}
                if event.get('type')=='sample':
                    for source,value in data.get('values',{}).items():
                        if type(value) not in (int,float):continue
                        key=source.split(':',1)[-1]
                        unit=custom_units.get(key,'') if source.startswith('custom:') else derived_units.get(key,'') if source.startswith('derived:') else builtin_units.get(key,'')
                        acquired=data.get('acquiredAt',{}).get(source,event['timestamp'])
                        if type(acquired) not in (int,float) or not math.isfinite(acquired):acquired=event['timestamp']
                        reading_stamp=datetime.fromtimestamp(acquired,timezone.utc).isoformat()
                        elapsed=event.get('elapsed')
                        if type(elapsed) in (int,float):elapsed=round(elapsed+acquired-event['timestamp'],6)
                        cells=[reading_stamp,elapsed,'reading','','',source if ':' in source else 'builtin:'+source,value,unit,'','','']
                        writer.writerow([safe_cell(cell) if index!=6 else value for index,cell in enumerate(cells)])
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                writer.writerow(['','','invalid_record','','','','','','Truncated or invalid record retained in JSONL','',''])
            if output.tell()>128*MIB: raise ValueError('CSV exceeds the export size limit')
        return ('\ufeff'+output.getvalue()).encode('utf-8'), 'text/csv; charset=utf-8'

    def save_export(self, identifier, format):
        body,_=self.export(identifier,format)
        with self.export_write_lock:
            root=self.export_root
            if any(p.is_symlink() for p in [root,*root.parents]):raise ValueError('Export folder must not contain symbolic links')
            root.mkdir(parents=True,exist_ok=True,mode=0o700)
            name=f'obd-{identifier}.{format}'
            path=root/name;tmp=root/(name+'.tmp')
            if path.is_symlink() or tmp.is_symlink():raise ValueError('Invalid export file')
            total=sum(p.stat().st_size for p in root.glob('obd-*') if p.is_file() and not p.is_symlink())
            if total-(path.stat().st_size if path.exists() else 0)+len(body)>self.max_total:raise ValueError('Export folder is full; move older exports before saving more')
            flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
            fd=os.open(tmp,flags,0o600)
            try:
                with os.fdopen(fd,'wb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
                tmp.replace(path)
            except Exception:
                tmp.unlink(missing_ok=True);raise
        return {'filename':name,'directory':'Downloads/coscarOS-OBD-Logs'}
