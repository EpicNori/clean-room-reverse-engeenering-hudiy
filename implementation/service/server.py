"""Loopback-only dashboard server with an explicit, bounded action API."""
import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote,urlsplit
from obd import OBD
from phonebook import Phonebook
from layout import LayoutStore
from updates import UpdateSettings
from bluetooth_devices import BluetoothDevices
from live_media import with_bluetooth_media
from display import DisplayBrightness
from calls import PhoneCalls
from standalone_projection import StandaloneProjection
from independent_obd import IndependentOBDSettings
from independent_wireless import IndependentWireless
from bluez_agent import BluezAgent
from independent_audio_route import IndependentAudioRoute
from audio_settings import AudioSettings

ROOT=Path(__file__).resolve().parents[1]/'dashboard'/'dist'/'client'
obd=OBD()
STANDALONE=os.environ.get('HUDIY_STANDALONE')=='1'
projection=StandaloneProjection(enabled=STANDALONE)
phonebook=Phonebook(enabled=projection.enabled)
layout=LayoutStore(enabled=projection.enabled)
updates=UpdateSettings(projection, phonebook)
audio_dsp=AudioSettings(projection)
bluetooth=BluetoothDevices(enabled=projection.enabled)
native_obd=IndependentOBDSettings(bluetooth,obd)
display=DisplayBrightness(enabled=projection.enabled)
calls=PhoneCalls(enabled=projection.enabled)
wireless=IndependentWireless(projection)
agent=BluezAgent(bluetooth,wireless,projection) if projection.enabled else None
radio_output=IndependentAudioRoute(bluetooth,projection,calls,enabled=projection.enabled)
ALLOWED_PORTS={8766,4173}

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)
    def log_message(self,format,*args):pass
    def trusted_host(self):
        try:
            host=urlsplit('http://'+self.headers.get('Host',''))
            return host.hostname in {'127.0.0.1','localhost'} and host.port in ALLOWED_PORTS
        except ValueError:return False
    def send(self,code,body,ctype='application/json'):
        if isinstance(body,(dict,list)):body=json.dumps(body,allow_nan=False).encode()
        elif isinstance(body,str):body=body.encode()
        self.send_response(code)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if not self.trusted_host():return self.send(403,{'error':'Untrusted Host header'})
        path=urlsplit(self.path).path
        if path=='/api/projection':return self.send(200,with_bluetooth_media(projection.data_snapshot(),bluetooth.media_snapshot()))
        if path=='/api/phonebook':return self.send(200,phonebook.snapshot())
        if path=='/api/bluetooth':return self.send(200,{**bluetooth.snapshot(),**(agent.snapshot() if agent else {})})
        if path=='/api/display':return self.send(200,display.snapshot())
        if path=='/api/audio-route':return self.send(200,radio_output.snapshot())
        if path=='/api/audio-settings':return self.send(200,audio_dsp.snapshot())
        if path=='/api/wireless':
            try:return self.send(200,wireless.snapshot())
            except (OSError,ValueError):return self.send(503,{'error':'Native wireless settings unavailable'})
        if path=='/api/obd-settings':
            try:return self.send(200,native_obd.snapshot())
            except (OSError,ValueError):return self.send(503,{'error':'Native OBD settings unavailable'})
        if path=='/api/projection/coverart':
            image,ctype=projection.image_snapshot()
            return self.send(200,image,ctype) if image else self.send(404,{'error':'No Android Auto cover art'})
        if path=='/api/status':
            state=projection.snapshot()
            book=phonebook.status()
            phone=projection.phone_snapshot()
            call_state=calls.snapshot()
            if call_state['available']:phone.update(connected=True,call=call_state['call'],microphoneMuted=call_state.get('microphoneMuted'))
            if not phone['connected'] and book['connected']:phone.update(connected=True,name=book['name'])
            return self.send(200,{'obd':obd.snapshot(),'phone':phone,'projection':state,'platform':sys.platform,'layout':layout.snapshot() if layout.enabled else None,'updates':updates.snapshot() if updates.enabled else None,'capabilities':{'obd':True,'phone':call_state['available'],'phonebook':book['available'],'phoneStatus':state['available'],'projection':state['available'],'radio':False}})
        if path.startswith('/api/'):return self.send(404,{'error':'Unknown API endpoint'})
        relative=unquote(path).lstrip('/') or 'index.html'
        candidate=(ROOT/relative).resolve()
        if not candidate.is_relative_to(ROOT.resolve()):return self.send(403,{'error':'Path is outside the application'})
        if not candidate.is_file():return self.send(404,{'error':'File not found'})
        self.send(200,candidate.read_bytes(),mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream')
    def do_POST(self):
        if not self.trusted_host():return self.send(403,{'error':'Untrusted Host header'})
        origin=self.headers.get('Origin')
        if origin:
            try:o=urlsplit(origin); valid=o.scheme=='http' and o.hostname in {'127.0.0.1','localhost'} and o.port in ALLOWED_PORTS
            except ValueError:valid=False
            if not valid:return self.send(403,{'error':'Cross-origin actions are forbidden'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.send(415,{'error':'Use application/json'})
        if self.path!='/api/action':return self.send(404,{'error':'Unknown action endpoint'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=4096:return self.send(413,{'error':'Action body must be 1–4096 bytes'})
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError('Action body must be an object')
            name=data.get('action')
            if name=='bluetooth-pair':
                if set(data)!={'action','address'}:raise ValueError('Pairing requires only a device address')
                if not agent:return self.send(501,{'error':'Independent pairing requires the Pi application'})
                return self.send(200,agent.pair(data['address']))
            if name=='bluetooth-pair-confirm':
                if set(data) not in ({'action','id','accepted'},{'action','id','accepted','pin'}):raise ValueError('Unexpected pairing confirmation arguments')
                if not agent:return self.send(501,{'error':'Independent pairing requires the Pi application'})
                return self.send(200,agent.confirm(data['id'],data['accepted'],data.get('pin')))
            if name in {'phone-call','phone-answer','phone-end','phone-microphone'}:
                expected={'action','number','confirmed'} if name=='phone-call' else {'action','muted'} if name=='phone-microphone' else {'action'}
                if set(data)!=expected:raise ValueError('Unexpected phone action arguments')
                if not calls.enabled:return self.send(501,{'error':'Phone controls require Bluetooth HFP on the Pi'})
                operation={'phone-call':'dial','phone-answer':'answer','phone-end':'end','phone-microphone':'mute'}[name]
                return self.send(200,calls.command(operation,data.get('number'),data.get('confirmed',False),data.get('muted')))
            if name in {'bluetooth-connect','bluetooth-disconnect','bluetooth-autoconnect'}:
                expected={'action','address','enabled'} if name=='bluetooth-autoconnect' else {'action','address','confirmed'} if name=='bluetooth-disconnect' else {'action','address'}
                if set(data)!=expected:raise ValueError('Unexpected connection arguments')
                if not bluetooth.enabled:return self.send(501,{'error':'Bluetooth connections require the Pi'})
                if name=='bluetooth-disconnect' and (projection.phone_snapshot().get('call',{}).get('state') in (1,2,3) or calls.snapshot().get('call',{}).get('state') in (1,2,3)):raise ConnectionError('End the phone call before disconnecting Bluetooth')
                operation={'bluetooth-connect':'connect','bluetooth-disconnect':'disconnect','bluetooth-autoconnect':'automatic'}[name]
                return self.send(200,bluetooth.connection(operation,data['address'],data.get('enabled'),data.get('confirmed',False)))
            if name=='display-brightness':
                if set(data)!={'action','brightness'}:raise ValueError('Brightness accepts only a percentage')
                if not display.enabled:return self.send(501,{'error':'Physical brightness requires the Pi'})
                return self.send(200,display.set(data['brightness']))
            if name=='obd-native-settings':
                if set(data)!={'action','address','channel'}:raise ValueError('OBD settings require only address and channel')
                if calls.snapshot().get('call',{}).get('state') in (1,2,3):raise ConnectionError('End the phone call before changing OBD settings')
                return self.send(200,native_obd.save(data['address'],data['channel']))
            if name=='wireless-hotspot':
                if set(data)!={'action','enabled','confirmed'}:raise ValueError('Unexpected wireless settings arguments')
                if not projection.enabled:return self.send(501,{'error':'Car hotspot settings require the Pi'})
                if calls.snapshot().get('call',{}).get('state') in (1,2,3):raise ConnectionError('End the phone call before changing Wi-Fi')
                return self.send(200,wireless.save(data['enabled'],data['confirmed']))
            if name=='audio-radio-output':
                if set(data)!={'action','address'}:raise ValueError('Unexpected radio output arguments')
                if not radio_output.enabled:return self.send(501,{'error':'Radio output requires the Pi'})
                if calls.snapshot().get('call',{}).get('state') in (1,2,3):raise ConnectionError('End the phone call before changing the radio output')
                return self.send(200,radio_output.save(data['address']))
            if name=='audio-settings':
                if set(data)!={'action','settings'}:raise ValueError('Audio settings accept only the settings object')
                return self.send(200,audio_dsp.save(data['settings']))
            if name=='application-quit':
                if set(data)!={'action'}:raise ValueError('Quit accepts no arguments')
                if not projection.enabled:return self.send(501,{'error':'Quit is available in the Pi application'})
                return self.send(200,projection.request_exit())
            if name in {'bluetooth-scan','bluetooth-scan-stop','bluetooth-remove'}:
                if not bluetooth.enabled:return self.send(501,{'error':'Bluetooth controls require the Pi'})
                expected={'action','address','confirmed'} if name=='bluetooth-remove' else {'action'}
                if set(data)!=expected:raise ValueError('Unexpected Bluetooth action arguments')
                operation={'bluetooth-scan':'scan','bluetooth-scan-stop':'stop','bluetooth-remove':'remove'}[name]
                return self.send(200,bluetooth.command(operation,data.get('address'),data.get('confirmed',False)))
            if name=='bluetooth-pair-menu':
                if set(data)!={'action'}:raise ValueError('Pairing menu accepts no arguments')
                if agent:return self.send(200,bluetooth.command('stop' if bluetooth.snapshot().get('scanActive') else 'scan'))
                return self.send(501,{'error':'Pairing requires our BlueZ agent on the Pi'})
            if name=='bluetooth-media':
                if set(data)!={'action','operation'}:raise ValueError('Bluetooth playback requires only operation')
                if not bluetooth.enabled:return self.send(501,{'error':'Bluetooth playback requires the Pi host'})
                return self.send(200,bluetooth.playback(data['operation']))
            if name=='refresh-settings':
                if set(data)!={'action','updates'}:raise ValueError('Refresh settings require only updates')
                if not updates.enabled:return self.send(501,{'error':'Live refresh settings require the Pi host'})
                return self.send(200,updates.save(data['updates']))
            if name=='layout-settings':
                if set(data)!={'action','layout'}:raise ValueError('Layout settings require only a layout')
                if not layout.enabled:return self.send(501,{'error':'Durable layout requires the Pi host'})
                return self.send(200,layout.save(data['layout']))
            if name=='projection-settings':
                if not projection.enabled:return self.send(501,{'error':'Android Auto settings require the Pi projection host'})
                settings={key:value for key,value in data.items() if key!='action'}
                previous=projection.snapshot()['options']
                result=projection.settings(settings)
                if STANDALONE and result['options']['taskbarVisible']!=previous['taskbarVisible']:
                    agent.reconnect_after_layout()
                return self.send(200,result)
            if name=='projection-layout-apply':
                if set(data)!={'action'}:raise ValueError('Layout apply does not accept arguments')
                return self.send(200,projection.request_layout())
            if name=='projection-host-stop':
                if set(data)!={'action'}:raise ValueError('Host stop does not accept arguments')
                if not projection.enabled:raise ValueError('Projection host is disabled')
                projection.stop_runtime()
                return self.send(200,{'accepted':True})
            if name=='obd-connect':
                port=data.get('port')
                if port=='bluetooth':
                    port=native_obd.port()
                    if not port:raise ConnectionError('Select a paired ELM327 adapter first')
                if not isinstance(port,str) or len(port)>100:raise ValueError('Invalid serial port')
                obd.connect(port)
                return self.send(200,{'message':'ELM327 connected'})
            if name=='obd-disconnect':
                obd.disconnect()
                return self.send(200,{'message':'OBD disconnected'})
            if name=='audio-volume':
                value=data.get('volume')
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<=value<=100:raise ValueError('Volume must be 0–100')
                if sys.platform!='linux':return self.send(501,{'error':'PipeWire integration requires Linux'})
                subprocess.run(['wpctl','set-volume','@DEFAULT_AUDIO_SINK@',str(value/100)],check=True,timeout=3,capture_output=True)
                return self.send(200,{'message':f'Volume {value}'})
            if name=='projection':
                if not projection.enabled:return self.send(501,{'error':'Android Auto requires our native Pi application'})
                if data.get('projection','android')!='android':raise ValueError('Only Android Auto is supported by this application')
                result=projection.action(data.get('operation'))
                if agent and data.get('operation') in {'usb','wifi'}:agent.select_transport(data['operation'])
                if agent and data.get('operation') in {'resume','wifi'}:
                    state=projection.snapshot()
                    if data.get('operation')=='wifi' and state.get('transport')=='usb':agent.reconnect_after_layout()
                    elif not state.get('connected') and state.get('transport')!='usb':agent.retrigger()
                return self.send(200,result)
            if name=='phone-refresh':
                if set(data)!={'action','view'}:raise ValueError('Phone refresh requires only a view')
                if not phonebook.enabled:return self.send(501,{'error':'Contacts require Bluetooth phonebook access on the Pi'})
                return self.send(200,phonebook.refresh(data.get('view')))
            if name in {'phone-refresh','phone-call','phone-end','bluetooth-scan','bluetooth-list'}:
                return self.send(501,{'error':'This integration is not implemented; no device action was performed'})
            return self.send(400,{'error':'Unknown or unsupported action'})
        except (ValueError,TypeError) as exc:return self.send(400,{'error':str(exc)})
        except Exception as exc:return self.send(503,{'error':str(exc)})

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8766)
    args=parser.parse_args()
    if args.port not in ALLOWED_PORTS:parser.error('Supported ports: 8766 or 4173')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    projection.start()
    if projection.enabled:obd.start_independent(native_obd)
    phonebook.start()
    bluetooth.start()
    if agent:agent.start()
    radio_output.start()
    calls.start()
    display.start()
    server.timeout=2
    print(f'Dashboard service: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        if agent:agent.close()
        radio_output.close();calls.close();bluetooth.close();phonebook.close();projection.close();obd.close();server.server_close()
if __name__=='__main__':main()
