"""Bounded ELM327 Mode 01 sensor polling. No arbitrary vehicle commands."""
from collections import deque
import copy
import re
import socket
import threading
import time

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
    def __init__(self,port,projection=None):
        self.sock=None
        self.serial=None
        self.native=None
        self.closed=False
        if port=='hudiy':
            if not projection or not projection.enabled or not projection.snapshot().get('nativeOBDConnected'):
                raise ConnectionError('Turn on the paired ELM327 and connect it in Hudiy')
            self.native=projection
        elif re.fullmatch(r'bluetooth://(?:[0-9A-F]{2}:){5}[0-9A-F]{2}/(?:[1-9]|[12][0-9]|30)',port):
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
        if command not in {'ATZ','ATE0','ATL0','ATH0','ATS0','ATSP0'} and command not in {'01'+p for p in PIDS}:
            raise ValueError('Command is not in the read-only sensor allowlist')
        if self.closed:raise ConnectionError('OBD session closed')
        if self.native:return self.native.query_obd(command)
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
        self.auto_projection=None
        self.independent_settings=None
        self.automatic=False
        self.supervisor=None
        self.shutdown=threading.Event()
        self.retry_at=0
        self.state={'connected':False,'mode':'disconnected','port':None,'values':{},'history':[],'error':None,'timestamp':None}
    def snapshot(self):
        with self.lock:return {**copy.deepcopy(self.state),'automatic':self.automatic}
    def disconnect(self):
        with self.lifecycle:
            self.automatic=False
            self._disconnect()

    def start(self,projection):
        """Follow the installed head unit's OBD connection; never own RFCOMM."""
        if projection.enabled and not self.supervisor:
            self.auto_projection=projection
            self.automatic=True
            self.supervisor=threading.Thread(target=self._automatic_run,daemon=True)
            self.supervisor.start()

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
                    with self.lock:self.state.update(connected=False,mode='disconnected',values={},history=[],timestamp=None,error=str(exc)[:512])
                return
            if self.shutdown.is_set() or not self.automatic or not self.auto_projection:return
            state=self.auto_projection.snapshot()
            ready=state.get('available') and state.get('nativeOBDConnected') and not state.get('exitRequested')
            if not ready:
                self.retry_at=0
                if self.snapshot()['port']=='hudiy':self._disconnect()
                return
            if self.snapshot()['connected'] or time.monotonic()<self.retry_at:return
            self.retry_at=time.monotonic()+30
            try:self._connect('hudiy',self.auto_projection)
            except (OSError,ValueError,RuntimeError) as exc:
                with self.lock:self.state.update(connected=False,mode='disconnected',values={},history=[],timestamp=None,error=str(exc)[:512])

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
        with self.lock:self.state.update(connected=False,mode='disconnected',port=None,values={},history=[],timestamp=None)
    def connect(self,port,projection=None):
        with self.lifecycle:
            self._connect(port,projection)
            self.automatic=(port=='hudiy' and self.auto_projection is not None) or (self.independent_settings is not None and port.startswith('bluetooth://'))
            self.retry_at=time.monotonic()+30

    def _connect(self,port,projection=None):
        self._disconnect()
        transport=Transport(port,projection)
        try:
            if not transport.native:
                identity=transport.query('ATZ')
                if 'ELM' not in identity.upper():raise RuntimeError('Device did not identify as ELM327')
                for command in ('ATE0','ATL0','ATH0','ATS0','ATSP0'):transport.query(command)
        except Exception:
            transport.close()
            raise
        self.transport=transport
        self.stop_event=threading.Event()
        with self.lock:self.state.update(connected=True,mode='simulator' if port.startswith('tcp:') else 'live',port=port,values={},history=[],error=None)
        self.worker=threading.Thread(target=self._poll,args=(transport,self.stop_event),daemon=True)
        self.worker.start()
    def _poll(self,transport,stop):
        history=deque(maxlen=120)
        try:
            while not stop.is_set():
                values={}
                for pid,(key,_,_) in PIDS.items():
                    if stop.is_set():return
                    values[key]=decode(pid,transport.query('01'+pid))
                stamp=time.time()
                history.append({'timestamp':stamp,**values})
                with self.lock:self.state.update(values=values,history=list(history),timestamp=stamp)
                stop.wait(.25)
        except Exception as exc:
            if not stop.is_set():
                with self.lock:self.state.update(connected=False,mode='disconnected',values={},history=[],timestamp=None,error=str(exc)[:512])
        finally:transport.close()
