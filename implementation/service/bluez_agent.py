"""Owned BlueZ pairing agent and wireless-AA profile with touch confirmation."""
import copy
import socket
import struct
import threading
import time
from bluetooth_devices import ADDRESS, DEVICE_PATH
from runtime_support import field

AA_UUID='4de17a00-52cb-11e6-bdf4-0800200c9a66'
AGENT_PATH='/org/epicnori/hudiy_recreation/agent'
PROFILE_PATH='/org/epicnori/hudiy_recreation/android_auto'
AA_CHANNEL=22
SERVICE_RECORD=f'''<?xml version="1.0" encoding="UTF-8" ?>
<record><attribute id="0x0001"><sequence><uuid value="{AA_UUID}"/></sequence></attribute>
<attribute id="0x0004"><sequence><sequence><uuid value="0x0100"/></sequence>
<sequence><uuid value="0x0003"/><uint8 value="{AA_CHANNEL}"/></sequence></sequence></attribute>
<attribute id="0x0005"><sequence><uuid value="0x1002"/></sequence></attribute>
<attribute id="0x0100"><text value="Android Auto Wireless"/></attribute></record>'''


def wifi_frame(message_id,payload):
    if type(message_id) is not int or not 1<=message_id<=7 or len(payload)>4096:raise ValueError('Invalid Wi-Fi handshake frame')
    return struct.pack('>HH',len(payload),message_id)+payload


class BluezAgent:
    def __init__(self,bluetooth,wireless,projection):
        self.bluetooth,self.wireless,self.projection=bluetooth,wireless,projection
        self.lock=threading.RLock()
        self.condition=threading.Condition(self.lock)
        self.pending=None
        self.pairing_busy=False
        self.answer=None
        self.generation=0
        self.stop=threading.Event()
        self.worker=None
        self.bus=None
        self.ready=False
        self.error=''
        self.connection=None
        self.connection_thread=None
        self.restart_thread=None
        self.reconnect_thread=None
        self.last_reconnect=float("-inf")
        self.manual_until=0
        self.paused=False
        self.transport_preference='auto'
        self.connection_lock=threading.RLock()
        self.wireless_status={'connected':False,'lastMessage':None,'credentialRequests':0,'error':''}

    def snapshot(self):
        with self.lock:return {'pairingAvailable':self.ready,'pairingBusy':self.pairing_busy,'pairing':copy.deepcopy(self.pending),'pairingError':self.error,'wirelessHandshake':dict(self.wireless_status)}

    def prompt(self,path,kind,code=''):
        if not DEVICE_PATH.fullmatch(str(path)):raise ValueError('Invalid pairing device')
        with self.condition:
            if self.pending:raise ConnectionError('Another pairing request is pending')
            devices=self.bluetooth.snapshot()['devices']
            device=next((d for d in devices if str(path).endswith('/dev_'+d['address'].replace(':','_'))),None)
            if not device:raise ValueError('Pairing device is not in the discovered list')
            self.generation+=1
            self.pending={'id':self.generation,'kind':kind,'code':code,'name':device['name']}
            self.answer=None
            self.condition.wait_for(lambda:self.answer is not None or self.stop.is_set(),timeout=30)
            result=self.answer
            self.pending=None;self.answer=None
            if result is None or result is False:raise ConnectionError('Pairing was cancelled')
            return result

    def confirm(self,identifier,accepted,pin=None):
        if type(identifier) is not int or type(accepted) is not bool:raise ValueError('Invalid pairing confirmation')
        with self.condition:
            if not self.pending or self.pending['id']!=identifier:raise ValueError('Pairing request has expired')
            if self.pending['kind']=='pin' and accepted:
                if pin not in ('0000','1234'):raise ValueError('Choose the adapter PIN')
                self.answer=pin
            else:
                if pin is not None:raise ValueError('PIN is not expected for this request')
                self.answer=accepted
            self.condition.notify_all()
        return {'accepted':True}

    def pair(self,address):
        if not self.ready or not isinstance(address,str) or not ADDRESS.fullmatch(address):raise ConnectionError('Pairing agent is unavailable')
        devices=self.bluetooth.snapshot()['devices']
        device=next((d for d in devices if d['address']==address and not d['paired']),None)
        if not device:raise ValueError('Choose a discovered unpaired device')
        with self.lock:
            if self.pending or self.pairing_busy:raise ConnectionError('Finish the pending pairing first')
            self.pairing_busy=True;self.error=''
        def request():
            bus=None
            try:
                import dbus
                bus=dbus.SystemBus(private=True)
                manager=dbus.Interface(bus.get_object('org.bluez','/'),'org.freedesktop.DBus.ObjectManager')
                objects=manager.GetManagedObjects(timeout=3)
                paths=[str(p) for p,interfaces in objects.items() if DEVICE_PATH.fullmatch(str(p)) and
                    str(interfaces.get('org.bluez.Device1',{}).get('Address','')).upper()==address]
                if len(paths)!=1:raise ConnectionError('Bluetooth device disappeared')
                path=paths[0]
                dbus.Interface(bus.get_object('org.bluez',path),'org.bluez.Device1').Pair(timeout=45)
                dbus.Interface(bus.get_object('org.bluez',path),'org.freedesktop.DBus.Properties').Set('org.bluez.Device1','Trusted',True,timeout=3)
            except Exception:
                with self.lock:self.error='Pairing failed or was cancelled; try again'
            finally:
                with self.lock:self.pairing_busy=False
                if bus:bus.close()
        try:threading.Thread(target=request,daemon=True).start()
        except RuntimeError:
            with self.lock:self.pairing_busy=False
            raise ConnectionError('Pairing worker could not start') from None
        return {'accepted':True,'message':'Confirm the Bluetooth pairing code'}

    def start(self):
        if self.bluetooth.enabled and not self.worker:
            self.worker=threading.Thread(target=self._run,daemon=True);self.worker.start()
            self.reconnect_thread=threading.Thread(target=self._reconnect_loop,daemon=True)
            self.reconnect_thread.start()

    def _run(self):
        while not self.stop.is_set():
            self._run_once()
            self.stop.wait(2)

    def _run_once(self):
        agent_manager=profile_manager=None
        registered_agent=registered_profile=False
        try:
            import dbus
            import dbus.service
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib
            owner=self
            class Agent(dbus.service.Object):
                @dbus.service.method('org.bluez.Agent1',in_signature='',out_signature='')
                def Release(self):owner.ready=False
                @dbus.service.method('org.bluez.Agent1',in_signature='',out_signature='')
                def Cancel(self):
                    with owner.condition:owner.answer=False;owner.condition.notify_all()
                @dbus.service.method('org.bluez.Agent1',in_signature='o',out_signature='s')
                def RequestPinCode(self,device):
                    try:return owner.prompt(device,'pin')
                    except Exception:raise dbus.exceptions.DBusException('Pairing rejected',name='org.bluez.Error.Rejected')
                @dbus.service.method('org.bluez.Agent1',in_signature='ou',out_signature='')
                def RequestConfirmation(self,device,passkey):
                    try:owner.prompt(device,'confirm',f'{int(passkey):06}')
                    except Exception:raise dbus.exceptions.DBusException('Pairing rejected',name='org.bluez.Error.Rejected')
                @dbus.service.method('org.bluez.Agent1',in_signature='o',out_signature='')
                def RequestAuthorization(self,device):
                    try:owner.prompt(device,'confirm')
                    except Exception:raise dbus.exceptions.DBusException('Pairing rejected',name='org.bluez.Error.Rejected')
                @dbus.service.method('org.bluez.Agent1',in_signature='os',out_signature='')
                def AuthorizeService(self,device,uuid):
                    props=dbus.Interface(owner.bus.get_object('org.bluez',device),'org.freedesktop.DBus.Properties').GetAll('org.bluez.Device1',timeout=3)
                    if not props.get('Paired'):raise dbus.exceptions.DBusException('Pair first',name='org.bluez.Error.Rejected')
                @dbus.service.method('org.bluez.Agent1',in_signature='ouq',out_signature='')
                def DisplayPasskey(self,device,passkey,entered):pass
                @dbus.service.method('org.bluez.Agent1',in_signature='os',out_signature='')
                def DisplayPinCode(self,device,pincode):pass
                @dbus.service.method('org.bluez.Agent1',in_signature='o',out_signature='u')
                def RequestPasskey(self,device):raise dbus.exceptions.DBusException('Use numeric comparison',name='org.bluez.Error.Rejected')
            class Profile(dbus.service.Object):
                @dbus.service.method('org.bluez.Profile1',in_signature='',out_signature='')
                def Release(self):owner._close_connection()
                @dbus.service.method('org.bluez.Profile1',in_signature='oha{sv}',out_signature='')
                def NewConnection(self,device,fd,properties):
                    props=dbus.Interface(owner.bus.get_object('org.bluez',device),'org.freedesktop.DBus.Properties').GetAll('org.bluez.Device1',timeout=3)
                    if not props.get('Paired') or not owner.wireless_allowed():
                        raise dbus.exceptions.DBusException('Paired phone and car Wi-Fi required',name='org.bluez.Error.Rejected')
                    owner._close_connection()
                    connection=socket.socket(fileno=fd.take())
                    connection.settimeout(1)
                    with owner.connection_lock:owner.connection=connection
                    owner.connection_thread=threading.Thread(target=owner._handshake,args=(connection,),daemon=True)
                    owner.connection_thread.start()
                @dbus.service.method('org.bluez.Profile1',in_signature='o',out_signature='')
                def RequestDisconnection(self,device):owner._close_connection()
            self.bus=dbus.SystemBus(private=True,mainloop=DBusGMainLoop())
            agent=Agent(self.bus,AGENT_PATH);profile=Profile(self.bus,PROFILE_PATH)
            agent_manager=dbus.Interface(self.bus.get_object('org.bluez','/org/bluez'),'org.bluez.AgentManager1')
            agent_manager.RegisterAgent(AGENT_PATH,'DisplayYesNo',timeout=3);registered_agent=True
            agent_manager.RequestDefaultAgent(AGENT_PATH,timeout=3)
            profile_manager=dbus.Interface(self.bus.get_object('org.bluez','/org/bluez'),'org.bluez.ProfileManager1')
            profile_manager.RegisterProfile(PROFILE_PATH,AA_UUID,dbus.Dictionary({
                'Name':'Android Auto Wireless','Role':'server','Channel':dbus.UInt16(AA_CHANNEL),
                'RequireAuthentication':True,'RequireAuthorization':True,'AutoConnect':False,
                'ServiceRecord':SERVICE_RECORD},signature='sv'),timeout=3);registered_profile=True
            self.ready=True
            context=GLib.MainContext.default()
            while not self.stop.is_set():
                for _ in range(20):
                    if not context.pending():break
                    context.iteration(False)
                self.stop.wait(.05)
        except Exception:
            with self.lock:self.error='Independent Bluetooth agent could not register';self.ready=False
        finally:
            self.ready=False
            self._close_connection()
            if registered_profile:
                try:profile_manager.UnregisterProfile(PROFILE_PATH,timeout=3)
                except Exception:pass
            if registered_agent:
                try:agent_manager.UnregisterAgent(AGENT_PATH,timeout=3)
                except Exception:pass
            if self.bus:self.bus.close();self.bus=None

    def _start_frame(self):
        credentials=self.wireless.credentials()
        return wifi_frame(1,field(1,credentials['ipAddress'])+field(2,credentials['port']))

    def wireless_allowed(self):
        state=self.projection.snapshot()
        with self.lock:return (not self.paused and self.transport_preference!='usb' and self.wireless.credentials().get('enabled') is True
            and (state.get('connectionAllowed') is True or time.monotonic()<self.manual_until))

    def automatic_reconnect(self):
        state=self.projection.snapshot()
        if (not self.ready or state.get('available') is not True or
            state.get('automaticConnectionAllowed') is not True or state.get('options',{}).get('autoConnect',True) is False or state.get('connected') or
            state.get('sessionStarting') or not self.wireless_allowed()):return
        now=time.monotonic()
        with self.lock:
            if now-self.last_reconnect<30:return
            self.last_reconnect=now
        with self.connection_lock:connected=self.connection is not None
        try:
            if connected:self.retrigger()
            else:self.bluetooth.retry_android_auto()
        except OSError:pass

    def _reconnect_loop(self):
        while not self.stop.is_set():
            try:self.automatic_reconnect()
            except Exception:
                with self.lock:self.wireless_status['error']='Automatic connection is waiting for Bluetooth'
            self.stop.wait(5)

    def request_connection(self):
        with self.lock:
            self.manual_until=time.monotonic()+5
            self.paused=False

    def pause_connection(self):
        with self.lock:
            self.manual_until=0
            self.paused=True
        self._close_connection()

    def connection_settings(self, enabled):
        with self.lock:
            self.manual_until=0
            self.last_reconnect=float("-inf")
            if enabled:
                self.paused=False
                self.transport_preference="auto"

    def select_transport(self,transport):
        if transport not in ('usb','wifi'):raise ValueError('Select USB or Wi-Fi')
        with self.lock:self.transport_preference=transport
        if transport=='usb':self._close_connection()

    def _handshake(self,connection):
        pending=bytearray()
        with self.lock:self.wireless_status.update(connected=True,error='')
        try:
            connection.sendall(self._start_frame())
            while not self.stop.is_set():
                try:part=connection.recv(4096)
                except socket.timeout:continue
                if not part:break
                pending.extend(part)
                if len(pending)>8192:raise ValueError('Wireless handshake exceeds limit')
                while len(pending)>=4:
                    size,kind=struct.unpack('>HH',pending[:4])
                    if size>4096:raise ValueError('Wireless frame exceeds limit')
                    if len(pending)<size+4:break
                    del pending[:size+4]
                    with self.lock:self.wireless_status['lastMessage']=kind
                    if kind==2:
                        with self.lock:self.wireless_status['credentialRequests']+=1
                        config=self.wireless.credentials()
                        # Current AP address; never expose credentials through HTTP or logs.
                        bssid=__import__('pathlib').Path('/sys/class/net/wlan0/address').read_text().strip().upper()
                        payload=field(1,config['ssid'])+field(2,config['passphrase'])+field(3,bssid)+field(4,8)+field(5,1)
                        connection.sendall(wifi_frame(3,payload))
        except (OSError,ValueError):
            with self.lock:self.wireless_status['error']='Wireless handoff ended; reconnect the paired phone'
        finally:
            with self.lock:self.wireless_status['connected']=False
            with self.connection_lock:
                if self.connection is connection:self.connection=None
            connection.close()

    def retrigger(self):
        if not self.wireless_allowed():return
        with self.connection_lock:
            if self.connection:self.connection.sendall(self._start_frame())

    def reconnect_after_layout(self):
        if self.restart_thread and self.restart_thread.is_alive():return
        def request():
            if self.stop.wait(1):return
            for _ in range(16):
                if not self.projection.snapshot().get('connected'):
                    try:self.retrigger()
                    except OSError:pass
                    return
                if self.stop.wait(.5):return
        self.restart_thread=threading.Thread(target=request,daemon=True)
        self.restart_thread.start()

    def _close_connection(self):
        with self.connection_lock:
            if self.connection:
                try:self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                self.connection.close();self.connection=None

    def close(self):
        self.stop.set()
        with self.condition:self.answer=False;self.condition.notify_all()
        self._close_connection()
        if self.worker:self.worker.join(timeout=4)
        if self.reconnect_thread:self.reconnect_thread.join(timeout=4)
