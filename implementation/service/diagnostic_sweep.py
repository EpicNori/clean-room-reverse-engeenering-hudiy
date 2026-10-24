"""Paced read-only discovery; raw unknown payloads remain useful in exported logs."""
from collections import deque
import time
from custom_obd import response_payloads, decode_codes


def payloads(command, response):
    mode = int(command[:2], 16)
    prefix = f'{mode+0x40:02X}'+command[2:]
    return [frame[len(prefix):] for frame in response_payloads(response, prefix)]


def supported(command, response):
    base = int(command[2:4], 16)
    result = set()
    for raw in payloads(command, response):
        # Mode 09 adapters can include the number of following data items.
        if command.startswith('09') and len(raw)==10 and raw.startswith('01'): raw=raw[2:]
        if len(raw)!=8: continue
        bits = int(raw,16)
        result.update(base+i+1 for i in range(32) if bits & (1 << (31-i)) and base+i+1<=255)
    return result


# Common numeric fields are decoded; the complete raw response is always retained.
NUMERIC = {
    '04':('Engine load','%',1,lambda a,b:a*100/255),
    '05':('Coolant temperature','°C',1,lambda a,b:a-40),
    '06':('Short fuel trim bank 1','%',1,lambda a,b:(a-128)*100/128),
    '07':('Long fuel trim bank 1','%',1,lambda a,b:(a-128)*100/128),
    '08':('Short fuel trim bank 2','%',1,lambda a,b:(a-128)*100/128),
    '09':('Long fuel trim bank 2','%',1,lambda a,b:(a-128)*100/128),
    '0A':('Fuel pressure','kPa',1,lambda a,b:a*3),
    '0B':('Intake manifold pressure','kPa',1,lambda a,b:a),
    '0C':('Engine speed','rpm',2,lambda a,b:(a*256+b)/4),
    '0D':('Vehicle speed','km/h',1,lambda a,b:a),
    '0E':('Timing advance','°',1,lambda a,b:a/2-64),
    '0F':('Intake air temperature','°C',1,lambda a,b:a-40),
    '10':('Mass air flow','g/s',2,lambda a,b:(a*256+b)/100),
    '11':('Throttle position','%',1,lambda a,b:a*100/255),
    '1F':('Engine run time','s',2,lambda a,b:a*256+b),
    '21':('Distance with MIL on','km',2,lambda a,b:a*256+b),
    '2F':('Fuel level','%',1,lambda a,b:a*100/255),
    '30':('Warmups since codes cleared','count',1,lambda a,b:a),
    '31':('Distance since codes cleared','km',2,lambda a,b:a*256+b),
    '33':('Barometric pressure','kPa',1,lambda a,b:a),
    '42':('Control module voltage','V',2,lambda a,b:(a*256+b)/1000),
    '46':('Ambient air temperature','°C',1,lambda a,b:a-40),
    '4D':('Time with MIL on','min',2,lambda a,b:a*256+b),
    '4E':('Time since codes cleared','min',2,lambda a,b:a*256+b),
    '52':('Ethanol fuel','%',1,lambda a,b:a*100/255),
    '5C':('Oil temperature','°C',1,lambda a,b:a-40),
    '5E':('Fuel rate','L/h',2,lambda a,b:(a*256+b)/20),
}


def observation(command, response):
    if command in ('03','07','0A'):
        frames=response_payloads(response,{'03':'43','07':'47','0A':'4A'}[command])
        codes = decode_codes('\r'.join('43'+frame[2:] for frame in frames))
        return {'source':{'03':'stored-codes','07':'pending-codes','0A':'permanent-codes'}[command], 'codes':codes}
    frames = payloads(command, response)
    if not frames: return {'source':command, 'error':'No matching response'}
    result = {'source':command, 'payloads':frames}
    pid = command[2:4]
    if command[:2] in ('01','02') and pid in NUMERIC:
        label,unit,size,formula = NUMERIC[pid]
        raw = bytes.fromhex(frames[0])
        if len(raw)>=size: result.update(label=label,unit=unit,value=round(formula(raw[0],raw[1] if size>1 else 0),6))
    if command=='0101' and len(frames[0])>=2:
        byte=int(frames[0][:2],16);result.update(mil=bool(byte&128),dtcCount=byte&127)
    return result


class DiagnosticSweep:
    def __init__(self, recorder):
        self.recorder=recorder
        self.settings=recorder.capture_settings()
        self.pending=deque()
        if self.settings['faultCodes']:self.pending.extend(['03','07','0A'])
        for enabled,command in (('liveData','0100'),('freezeFrame','020000'),('monitorTests','ATDPN'),('vehicleInfo','0900')):
            if self.settings[enabled]:self.pending.append(command)
        self.commands={}; self.discovered={}; self.failures={}; self.next_at=0
        self.modes06=False

    def step(self, transport):
        now=time.monotonic()
        if now<self.next_at:return
        self.next_at=now+self.settings['scanIntervalSeconds']
        returned=None
        if self.pending: command=self.pending.popleft()
        else:
            due=[cmd for cmd,stamp in self.commands.items() if stamp<=now]
            if not due:return
            command=min(due,key=lambda cmd:self.commands[cmd])
        # Restore the standard header after custom ECU reads.
        transport.select_header(None)
        response=transport.query(command)
        if command=='ATDPN':
            self.modes06=any(line.strip().rstrip('>') in ('6','7','8','9','A6','A7','A8','A9') for line in response.upper().replace('ATDPN','').splitlines())
            if self.modes06:self.pending.append('0600')
            else:self.failures['06']='Monitor discovery requires a CAN protocol'
        elif len(command)>2 and int(command[2:4],16)%32==0:
            pids=supported(command,response); mode=command[:2]; base=int(command[2:4],16)
            self.discovered.setdefault(mode,set()).update(pid for pid in pids if pid%32)
            if not pids and not payloads(command,response):self.failures[command]='Support bitmap unavailable'
            for pid in sorted(pids):
                if pid%32==0 and pid==base+32 and pid<=224:self.pending.append(mode+f'{pid:02X}'+('00' if mode=='02' else ''))
                elif pid%32:self.commands.setdefault(mode+f'{pid:02X}'+('00' if mode=='02' else ''),0)
            self.recorder.record('support',{'command':command,'pids':[f'{pid:02X}' for pid in sorted(pids)]})
        else:
            try: data=observation(command,response)
            except ValueError as exc: data={'source':command,'error':str(exc)}
            self.recorder.record('diagnostic',{'command':command,**data})
            returned={'command':command,**data}
            if data.get('error'):self.failures[command]=data['error']
            else:self.failures.pop(command,None)
            self.commands[command]=now+(self.settings['diagnosticIntervalSeconds'] if command in ('03','07','0A') else self.settings['snapshotIntervalSeconds'] if command[:2] in ('02','06','09') else self.settings['scanIntervalSeconds'])
        self.recorder.set_coverage({'discovering':bool(self.pending),'supported':{mode:[f'{pid:02X}' for pid in sorted(pids)] for mode,pids in self.discovered.items()},'unavailable':dict(self.failures),'scheduledReadings':len(self.commands)})
        return returned
