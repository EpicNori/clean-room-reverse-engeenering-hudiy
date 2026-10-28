"""Explicit HFP call control through the already installed oFono service."""
import copy
import re
import sys
import threading
import time
from bluetooth_devices import read_devices

NUMBER=re.compile(r'\+?[0-9]{3,20}')
STATES={'incoming':1,'waiting':1,'dialing':2,'alerting':2,'active':3,'held':3}
ONGOING=('active','dialing','alerting')
# Errors meaning oFono/BlueZ left the bus or our connection died; proxies must be rebuilt.
LOST=('org.freedesktop.DBus.Error.ServiceUnknown','org.freedesktop.DBus.Error.NameHasNoOwner','org.freedesktop.DBus.Error.Disconnected')
MAX_FAILURES=6


def service_lost(error):
    name=getattr(error,'get_dbus_name',None)
    return callable(name) and name() in LOST


def dial_number(value):
    if not isinstance(value,str) or len(value)>64:raise ValueError('Enter a phone number')
    number=re.sub(r'[ ()-]','',value)
    if not NUMBER.fullmatch(number):raise ValueError('Use 3–20 digits, optionally starting with +')
    return number


class PhoneCalls:
    def __init__(self,enabled=False):
        self.enabled=enabled and sys.platform=='linux'
        self.lock=threading.RLock()
        self.operation_lock=threading.RLock()
        self.stop=threading.Event()
        self.worker=None
        self.bus=self.dbus=self.modems=self.bluez=None
        self.modem=None
        self.calls={}
        self.muted=None
        # Commands wait briefly for the background refresh instead of failing at once.
        self.command_wait=5;self.refresh_interval=5;self.retry_interval=3
        self.data={'available':False,'call':{},'error':'Connect one paired phone with Bluetooth calls enabled'}

    def snapshot(self):
        with self.lock:return copy.deepcopy(self.data)

    def _interface(self,path,name):
        return self.dbus.Interface(self.bus.get_object('org.ofono',path),name)

    def _select(self):
        _,_,devices=read_devices(self.bluez.GetManagedObjects(timeout=3))
        connected={d['_path'] for d in devices if d['paired'] and d['connected']}
        candidates=[str(path) for path,props in self.modems.GetModems(timeout=3)
            if str(path).startswith('/hfp/') and str(path)[4:] in connected and props.get('Type')=='hfp'
            and props.get('Powered') and props.get('Online') and 'org.ofono.VoiceCallManager' in props.get('Interfaces',[])]
        if len(candidates)!=1:raise ConnectionError('Connect one paired phone with Bluetooth calls enabled')
        return candidates[0]

    def _valid_call(self,path):
        return bool(self.modem and re.fullmatch(re.escape(self.modem)+r'/voicecall[0-9]+',str(path)))

    def _publish(self):
        with self.lock:
            visible=[props for props in self.calls.values() if props.get('State') in STATES]
            first=visible[0] if visible else {}
            self.data={'available':bool(self.modem),'call':{'state':STATES.get(first.get('State'),0),
                'status':str(first.get('State','')),'number':str(first.get('LineIdentification',''))[:64],
                'name':str(first.get('Name',''))[:128],'count':len(visible)},'microphoneMuted':self.muted,'error':''}

    def _refresh(self):
        selected=self._select()
        with self.lock:
            changed=selected!=self.modem
            if changed:self.modem=selected;self.calls={}
        if changed:
            calls=self._interface(selected,'org.ofono.VoiceCallManager').GetCalls(timeout=3)
            with self.lock:self.calls={str(p):dict(props) for p,props in list(calls)[:16] if self._valid_call(p)}
        try:
            value=self._interface(selected,'org.ofono.CallVolume').GetProperties(timeout=3).get('Muted')
            with self.lock:self.muted=bool(value) if value is not None else None
        except Exception:
            with self.lock:self.muted=None
        self._publish()

    def _added(self,call,props,path=None):
        with self.lock:
            if path==self.modem and self._valid_call(call) and len(self.calls)<16:self.calls[str(call)]=dict(props)
        self._publish()

    def _removed(self,call,path=None):
        with self.lock:
            if path==self.modem:self.calls.pop(str(call),None)
        self._publish()

    def _changed(self,key,value,path=None):
        with self.lock:
            if str(path) in self.calls and key in ('State','LineIdentification','Name'):self.calls[str(path)][str(key)]=value
        self._publish()

    def command(self,operation,number=None,confirmed=False,muted=None):
        if operation not in ('dial','answer','end','mute'):raise ValueError('Unsupported phone operation')
        if operation=='mute' and type(muted) is not bool:raise ValueError('Microphone mute must be boolean')
        if operation=='dial':
            number=dial_number(number)
            if confirmed is not True:raise ValueError('Confirm the number before calling')
        if not self.enabled or not self.bus:raise ConnectionError('Bluetooth calling unavailable')
        if not self.operation_lock.acquire(timeout=self.command_wait):raise ConnectionError('Phone operation in progress')
        try:
            # The worker may have dropped the bus for a rebuild while we waited.
            if not self.bus:raise ConnectionError('Bluetooth calling unavailable')
            self._refresh()
            manager=self._interface(self.modem,'org.ofono.VoiceCallManager')
            # Revalidate current calls immediately before changing a real call.
            calls=[(str(p),dict(props)) for p,props in list(manager.GetCalls(timeout=3))[:16]]
            calls=[(p,props) for p,props in calls if self._valid_call(p) and props.get('State') in STATES]
            if operation=='dial':
                if calls:raise ConnectionError('End the current call before calling another number')
                manager.Dial(number,'default',timeout=3)
            else:
                if operation=='end' and len(calls)>1:
                    # Call waiting/hold: end only the single call in progress; oFono keeps the other one.
                    calls=[(p,props) for p,props in calls if props.get('State') in ONGOING]
                    if len(calls)!=1:raise ConnectionError('Choose the call to end on the phone')
                if len(calls)!=1:raise ConnectionError('One current call is required')
                path,props=calls[0]
                call=self._interface(path,'org.ofono.VoiceCall')
                if operation=='mute':
                    if props.get('State')!='active' or self.muted is None:raise ConnectionError('Microphone control requires an active call')
                    self._interface(self.modem,'org.ofono.CallVolume').SetProperty('Muted',self.dbus.Boolean(muted),timeout=3)
                    with self.lock:self.muted=muted
                    self._publish()
                elif operation=='answer':
                    if props.get('State')!='incoming':raise ConnectionError('There is no incoming call to answer')
                    call.Answer(timeout=3)
                else:call.Hangup(timeout=3)
            return {'accepted':True,'message':'Call request sent to the phone'}
        finally:self.operation_lock.release()

    def start(self):
        if self.enabled and not self.worker:
            self.worker=threading.Thread(target=self._run,daemon=True);self.worker.start()

    def _run(self):
        # oFono may start after us or restart; rebuild the bus and proxies each round.
        while not self.stop.is_set():
            self._run_once()
            self.stop.wait(self.retry_interval)

    def _run_once(self):
        matches=[]
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib
            self.dbus=dbus
            self.bus=dbus.SystemBus(private=True,mainloop=DBusGMainLoop())
            self.modems=self._interface('/','org.ofono.Manager')
            self.bluez=dbus.Interface(self.bus.get_object('org.bluez','/'),'org.freedesktop.DBus.ObjectManager')
            for handler,name,interface in ((self._added,'CallAdded','org.ofono.VoiceCallManager'),
                    (self._removed,'CallRemoved','org.ofono.VoiceCallManager'),(self._changed,'PropertyChanged','org.ofono.VoiceCall')):
                matches.append(self.bus.add_signal_receiver(handler,signal_name=name,dbus_interface=interface,bus_name='org.ofono',path_keyword='path'))
            context=GLib.MainContext.default();next_refresh=0;failures=0
            while not self.stop.is_set():
                for _ in range(20):
                    if not context.pending():break
                    context.iteration(False)
                if time.monotonic()>=next_refresh:
                    next_refresh=time.monotonic()+self.refresh_interval
                    try:
                        with self.operation_lock:self._refresh()
                        failures=0
                    except Exception as exc:
                        with self.lock:
                            self.modem=None;self.calls={}
                            self.data={'available':False,'call':{},'error':'Connect one paired phone with Bluetooth calls enabled'}
                        # ConnectionError is the normal "no suitable phone" result, not a broken proxy.
                        if not isinstance(exc,ConnectionError):failures+=1
                        if service_lost(exc) or failures>=MAX_FAILURES:raise
                self.stop.wait(.25)
        except Exception:
            with self.lock:self.data={'available':False,'call':{},'error':'The installed oFono calling service is unavailable'}
        finally:
            for match in matches:
                try:match.remove()
                except Exception:pass
            # Wait for a running command before closing the bus it uses.
            with self.operation_lock:
                bus,self.bus,self.modems,self.bluez=self.bus,None,None,None
                # Signals may have been missed; force GetCalls after the rebuild.
                with self.lock:self.modem=None;self.calls={}
            if bus:
                try:bus.close()
                except Exception:pass

    def close(self):
        self.stop.set()
        if self.worker:self.worker.join(timeout=4)
