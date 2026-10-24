"""Bounded ELM327 read-only sensor and trouble-code polling. No arbitrary vehicle commands."""
from collections import deque
import copy
import re
import socket
import threading
import time
from custom_obd import decode_sensor, decode_codes
from driving_stats import DrivingStats
from diagnostic_sweep import DiagnosticSweep

PIDS={'04':('load',1,lambda b:b[0]*100/255),'05':('coolant',1,lambda b:b[0]-40),'0C':('rpm',2,lambda b:(b[0]*256+b[1])/4),'0D':('speed',1,lambda b:b[0]),'11':('throttle',1,lambda b:b[0]*100/255),'42':('voltage',2,lambda b:(b[0]*256+b[1])/1000)}

def decode(pid,response):
    """Locate a valid sensor frame, including echoed commands and CAN headers."""
    if pid not in PIDS:
        raise ValueError('Unsupported PID')
    compact=re.sub(r'\s+','',response.upper())
    _,size,formula=PIDS[pid]
    match=re.search('41'+pid+r'([0-9A-F]{'+str(size*2)+'})',compact)
    if not match:
        return None
    return round(formula(bytes.fromhex(match.group(1))),2)

class Transport:
    def __init__(self,port):
        self.sock=None
        self.serial=None
        self.closed=False
        self.observer=None
        self.protocol=None
        self.header=None
        if re.fullmatch(r'bluetooth://(?:[0-9A-F]{2}:){5}[0-9A-F]{2}/(?:[1-9]|[12][0-9]|30)',port):
            address, channel = port[len('bluetooth://'):].split('/')
            self.sock=socket.socket(socket.AF_BLUETOOTH,socket.SOCK_STREAM,socket.BTPROTO_RFCOMM)
            try:
                self.sock.settimeout(3)
                self.sock.connect((address,int(channel)))
                self.sock.settimeout(.3)
            except Exception:
                self.sock.close()
                raise
        elif re.fullmatch(r'tcp://127\.0\.0\.1:\d{1,5}',port):
            number=int(port.rsplit(':',1)[1])
            if not 1024<=number<=65535:
                raise ValueError('Simulator port must be 1024–65535')
            self.sock=socket.create_connection(('127.0.0.1',number),timeout=2)
            self.sock.settimeout(.3)
        elif re.fullmatch(r'/dev/(ttyUSB\d+|ttyACM\d+|rfcomm\d+)|COM\d{1,3}',port):
            try:
                import serial
            except ImportError as exc:
                raise RuntimeError('Install pyserial to connect a serial ELM327 adapter') from exc
            self.serial=serial.Serial(port,38400,timeout=.3,write_timeout=1)
        else:
            raise ValueError('Choose /dev/ttyUSBn, /dev/ttyACMn, /dev/rfcommn, COMn, or a loopback simulator')
    def query(self,command):
        if not isinstance(command,str) or (command not in {'ATZ','ATE0','ATL0','ATH0','ATS0','ATSP0','ATDPN','03','07','0A'} and not re.fullmatch(r'01[0-9A-F]{2}|02[0-9A-F]{2}00|(?:06|09)[0-9A-F]{2}|22[0-9A-F]{4}|ATSH(?:[0-7][0-9A-F]{2}|[01][0-9A-F]{7})',command)):
            raise ValueError('Command is not in the read-only sensor allowlist')
        started=time.time()
        try:
            result=self._query(command)
        except Exception as exc:
            if self.observer:self.observer.exchange(command,error=exc,header=self.header,started=started)
            raise
        if self.observer:self.observer.exchange(command,result,header=self.header,started=started)
        return result
    def _query(self,command):
        if self.closed:raise ConnectionError('OBD session closed')
        data=(command+'\r').encode('ascii')
        if self.sock:self.sock.sendall(data)
        else:self.serial.write(data)
        result=b''
        deadline=time.monotonic()+3
        while time.monotonic()<deadline and len(result)<4096:
            try:
                part=self.sock.recv(512) if self.sock else self.serial.read(512)
            except socket.timeout:
                continue
            if not part and self.sock:raise ConnectionError('ELM327 connection closed')
            result+=part
            if b'>' in result:return result.decode('ascii',errors='replace')
        raise TimeoutError('ELM327 did not return a prompt')
    def select_header(self,header=None):
        if header==self.header:return
        if self.protocol is None:
            result=self.query('ATDPN').upper().replace('ATDPN','')
            found=re.search(r'(?:^|[\r\n])A?([0-9A-C])\s*(?:>|$)',result.strip())
            if not found:raise ValueError('ELM327 did not identify its active protocol')
            self.protocol=found.group(1)
        if self.protocol not in {'6','7','8','9'}:raise ValueError('Custom ECU headers require a CAN protocol')
        is29=self.protocol in {'7','9'}
        if header is not None and len(header)!=(8 if is29 else 3):raise ValueError('ECU header does not match the active CAN protocol')
        target=header or ('18DB33F1' if is29 else '7DF')
        if 'OK' not in self.query('ATSH'+target).upper():raise ValueError('ELM327 rejected this ECU header')
        self.header=header

    def query_sensor(self,sensor):
        self.select_header(sensor['header'])
        return self.query(sensor['mode']+sensor['pid'])

    def close(self):
        self.closed=True
        if self.sock:self.sock.close()
        if self.serial:self.serial.close()

class OBD:
    def __init__(self):
        self.lock=threading.RLock()
        self.lifecycle=threading.Lock()
        self.stop_event=threading.Event()
        self.worker=None
        self.transport=None
        self.independent_settings=None
        self.automatic=False
        self.supervisor=None
        self.shutdown=threading.Event()
        self.custom_dashboard=None
        self.recorder=None
        self.retry_at=0
        self.state={'custom':{},'customRevision':None,'derived':{},'diagnostics':{'codes':[], 'error':None,'timestamp':None},'connected':False,'mode':'disconnected','port':None,'values':{},'history':[],'error':None,'timestamp':None}
    def snapshot(self):
        with self.lock:return {**copy.deepcopy(self.state),'automatic':self.automatic}
    def disconnect(self):
        with self.lifecycle:
            self.automatic=False
            self._disconnect()


    def start_independent(self,settings):
        self.independent_settings=settings
        self.automatic=True
        if not self.supervisor:
            self.supervisor=threading.Thread(target=self._automatic_run,daemon=True)
            self.supervisor.start()

    def reconnect_independent(self):
        with self.lifecycle:
            self._disconnect()
            self.automatic=True
            self.retry_at=0

    def _automatic_run(self):
        while not self.shutdown.is_set():
            self._automatic_tick()
            self.shutdown.wait(5)

    def _automatic_tick(self):
        with self.lifecycle:
            if self.independent_settings:
                if self.shutdown.is_set() or not self.automatic:return
                port=self.independent_settings.port()
                current=self.snapshot()
                if not port:
                    if current['connected']:self._disconnect()
                    return
                if current['connected'] or time.monotonic()<self.retry_at:return
                self.retry_at=time.monotonic()+30
                try:self._connect(port)
                except (OSError,ValueError,RuntimeError) as exc:
                    if self.recorder:self.recorder.connection(False,'disconnected',str(exc))
                    with self.lock:self.state.update(connected=False,mode='disconnected',values={},history=[],timestamp=None,error=str(exc)[:512],custom={},customRevision=None,derived={},diagnostics={'codes':[],'error':None,'timestamp':None})
                return

    def close(self):
        self.shutdown.set()
        if self.supervisor:self.supervisor.join(timeout=5)
        self.disconnect()
    def _disconnect(self):
        self.stop_event.set()
        if self.transport:
            try:self.transport.close()
            except OSError:pass
        if self.worker:self.worker.join(timeout=4)
        if self.worker and self.worker.is_alive():raise RuntimeError('Previous OBD session is still stopping')
        self.transport=None
        self.worker=None
        if self.recorder:self.recorder.connection(False,'disconnected')
        with self.lock:self.state.update(connected=False,mode='disconnected',port=None,values={},history=[],timestamp=None,custom={},customRevision=None,derived={},diagnostics={'codes':[],'error':None,'timestamp':None})
    def connect(self,port):
        with self.lifecycle:
            self._connect(port)
            self.automatic=self.independent_settings is not None and port.startswith('bluetooth://')
            self.retry_at=time.monotonic()+30

    def _connect(self,port):
        self._disconnect()
        mode='simulator' if port.startswith('tcp:') else 'live'
        if self.recorder:self.recorder.begin_connection(mode)
        try:transport=Transport(port)
        except Exception as exc:
            if self.recorder:self.recorder.connection(False,'disconnected',str(exc))
            raise
        transport.observer=self.recorder
        try:
            identity=transport.query('ATZ')
            if 'ELM' not in identity.upper():raise RuntimeError('Device did not identify as ELM327')
            for command in ('ATE0','ATL0','ATH0','ATS0','ATSP0'):transport.query(command)
        except Exception as exc:
            if self.recorder:self.recorder.connection(False,'disconnected',str(exc))
            transport.close()
            raise
        if self.recorder:self.recorder.connection(True,mode)
        self.transport=transport
        self.stop_event=threading.Event()
        with self.lock:self.state.update(connected=True,mode='simulator' if port.startswith('tcp:') else 'live',port=port,values={},history=[],error=None)
        self.worker=threading.Thread(target=self._poll,args=(transport,self.stop_event),daemon=True)
        self.worker.start()
    def _poll(self,transport,stop):
        history=deque(maxlen=120)
        stats=DrivingStats(); revision=None; custom={}; due={}; diagnostic_due=0
        diagnostics={'codes':[],'error':None,'timestamp':None}; stats_signature=None; sensor_signature=None; mapping_revision=None
        sweep=None; logging_generation=None
        try:
            while not stop.is_set():
                logging=bool(self.recorder and self.recorder.active and not self.recorder.finishing)
                if logging and self.recorder.generation!=logging_generation:
                    logging_generation=self.recorder.generation;sweep=DiagnosticSweep(self.recorder)
                    self.recorder.record('definitions',self.custom_dashboard.snapshot() if self.custom_dashboard else {})
                    self.recorder.record('connection',{'connected':True,'mode':self.snapshot()['mode']})
                config=self.custom_dashboard.snapshot() if self.custom_dashboard else None
                if config and config['revision']!=revision:
                    revision=config['revision']; mapping_revision=config['mappingRevision']
                    if logging:self.recorder.record('definitions',config)
                    if sensor_signature!=config['config']['sensors']:
                        custom={};due={};sensor_signature=config['config']['sensors']
                    signature=(config['config']['range'],config['config']['sensors'])
                    if signature!=stats_signature:stats.reset(); stats_signature=signature
                if config:transport.select_header(None)
                values={}
                for pid,(key,_,_) in PIDS.items():
                    if stop.is_set():return
                    values[key]=decode(pid,transport.query('01'+pid))
                if config:
                    dashboard=config['config']
                    wanted={w['source'] for w in dashboard['widgets']}|{dashboard['range']['fuelLevel'],dashboard['range']['fuelRate']}
                    if logging and self.recorder.capture_settings()['customSensors']:wanted|={'custom:'+sensor['id'] for sensor in dashboard['sensors']}
                    custom={sid:reading for sid,reading in custom.items() if 'custom:'+sid in wanted}
                    budget=2
                    for sensor in sorted(dashboard['sensors'],key=lambda s:due.get(s['id'],0)):
                        if stop.is_set():return
                        sid=sensor['id']
                        if budget<=0:break
                        if 'custom:'+sid not in wanted or time.monotonic()<due.get(sid,0):continue
                        budget-=1; due[sid]=time.monotonic()+sensor['interval']
                        try:
                            value=decode_sensor(sensor,transport.query_sensor(sensor))
                            custom[sid]={'value':value,'error':None,'timestamp':time.time()}
                        except ValueError as exc:custom[sid]={'value':None,'error':str(exc)[:160],'timestamp':time.time()}
                    if (not logging or not self.recorder.capture_settings()['faultCodes']) and 'errors' in wanted and time.monotonic()>=diagnostic_due:
                        transport.select_header(None); diagnostic_due=time.monotonic()+30
                        try:diagnostics={'codes':decode_codes(transport.query('03')),'error':None,'timestamp':time.time()}
                        except ValueError as exc:diagnostics={'codes':[],'error':str(exc)[:160],'timestamp':time.time()}
                stamp=time.time()
                derived=stats.update(stamp,values,custom,config['config']['range']) if config else {}
                for key,value in derived.items():values['derived:'+key]=value
                if config:
                    for sensor in config['config']['sensors']:
                        sample=custom.get(sensor['id'],{})
                        if sample.get('timestamp') and stamp-sample['timestamp']>max(3,sensor['interval']*2):
                            sample={'value':None,'error':'Reading is stale','timestamp':sample['timestamp']}; custom[sensor['id']]=sample
                        values['custom:'+sensor['id']]=sample.get('value')
                history.append({'timestamp':stamp,'customRevision':mapping_revision,**values})
                with self.lock:self.state.update(values=values,history=list(history),timestamp=stamp,custom=copy.deepcopy(custom),customRevision=mapping_revision,derived=derived,diagnostics=copy.deepcopy(diagnostics))
                if logging:
                    self.recorder.record('sample',{'timestamp':stamp,'mode':self.snapshot()['mode'],'values':values,'custom':custom,'derived':derived,'diagnostics':diagnostics,'mappingRevision':mapping_revision})
                    if sweep:
                        observation=sweep.step(transport)
                        if observation and observation.get('source')=='stored-codes':
                            diagnostics={'codes':observation.get('codes',[]),'error':observation.get('error'),'timestamp':time.time()}
                            with self.lock:self.state['diagnostics']=copy.deepcopy(diagnostics)
                stop.wait(.25)
        except Exception as exc:
            if not stop.is_set():
                if self.recorder:self.recorder.connection(False,'disconnected',str(exc))
                with self.lock:self.state.update(connected=False,mode='disconnected',values={},history=[],timestamp=None,error=str(exc)[:512],custom={},customRevision=None,derived={},diagnostics={'codes':[],'error':None,'timestamp':None})
        finally:transport.close()
