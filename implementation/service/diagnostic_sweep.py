"""Paced read-only discovery; raw unknown payloads remain useful in exported logs."""
from collections import deque
import time
from custom_obd import response_payloads, decode_codes
from elm_frames import response_frames, physical_request_header


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
    '23':('Fuel rail pressure','kPa',2,lambda a,b:(a*256+b)*10),
    '43':('Absolute engine load','%',2,lambda a,b:(a*256+b)*100/255),
    '45':('Relative throttle position','%',1,lambda a,b:a*100/255),
    '49':('Accelerator pedal D','%',1,lambda a,b:a*100/255),
    '4A':('Accelerator pedal E','%',1,lambda a,b:a*100/255),
    '4B':('Accelerator pedal F','%',1,lambda a,b:a*100/255),
    '59':('Absolute fuel rail pressure','kPa',2,lambda a,b:(a*256+b)*10),
    '5A':('Relative accelerator pedal','%',1,lambda a,b:a*100/255),
    '61':('Driver demanded torque','%',1,lambda a,b:a-125),
    '62':('Actual engine torque','%',1,lambda a,b:a-125),
    '63':('Reference engine torque','N·m',2,lambda a,b:a*256+b),
}


def _basic_observation(command, response):
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


DTC_FLAGS = ('testFailed','testFailedThisOperationCycle','pendingDTC','confirmedDTC',
             'testNotCompletedSinceLastClear','testFailedSinceLastClear',
             'testNotCompletedThisOperationCycle','warningIndicatorRequested')


def _decode_frame(command, frame):
    raw = frame['payload']
    if not frame['complete']:
        return {'error':frame['error'], 'payload':raw}
    if raw.startswith('7F'+command[:2]):
        return {'error':'ECU rejected read request', 'negativeResponseCode':raw[4:6], 'payload':raw}
    if command.startswith('19'):
        prefix='59'+command[2:4]
        if not raw.startswith(prefix):return None
        data=bytes.fromhex(raw[4:])
        if command=='1901FF':
            if len(data)!=4:return {'error':'Incomplete UDS DTC count response','payload':raw}
            return {'source':'uds-dtc-count','statusAvailabilityMask':f'{data[0]:02X}',
                    'dtcFormatIdentifier':f'{data[1]:02X}','dtcCount':int.from_bytes(data[2:],'big')}
        if command=='1902FF':
            if not data or (len(data)-1)%4:return {'error':'Incomplete UDS DTC status response','payload':raw}
            records=[]
            for offset in range(1,len(data),4):
                status=data[offset+3]
                records.append({'dtc':data[offset:offset+3].hex().upper(),'status':f'{status:02X}',
                                'flags':[name for bit,name in enumerate(DTC_FLAGS) if status & (1<<bit)]})
            return {'source':'uds-dtc-status','statusAvailabilityMask':f'{data[0]:02X}','records':records}
        if raw[4:10]!=command[4:10]:return {'error':'UDS DTC echo does not match request','payload':raw}
        return {'source':'uds-snapshot' if command[2:4]=='04' else 'uds-extended-data',
                'dtc':raw[4:10], 'payload':raw[10:]}
    prefix=f'{int(command[:2],16)+0x40:02X}'+command[2:]
    if command in ('03','07','0A'):prefix={'03':'43','07':'47','0A':'4A'}[command]
    if not raw.startswith(prefix):return None
    result=_basic_observation(command,raw)
    if command.startswith('06') and int(command[2:4],16)%32:
        data=bytes.fromhex(raw[2:])
        if len(data)%9:return {**result,'error':'Incomplete CAN monitor test record'}
        tests=[]
        for offset in range(0,len(data),9):
            item=data[offset:offset+9]
            tests.append({'monitorId':f'{item[0]:02X}','testId':f'{item[1]:02X}',
                          'unitScalingId':f'{item[2]:02X}',
                          'rawValue':item[3:5].hex().upper(),'rawMinimum':item[5:7].hex().upper(),
                          'rawMaximum':item[7:9].hex().upper(),
                          'interpretation':'Raw result; manufacturer scaling may be required'})
        result['tests']=tests
    return result


def observation(command, response):
    readings=[]
    for frame in response_frames(response):
        try:reading=_decode_frame(command,frame)
        except (ValueError,IndexError) as exc:reading={'error':'Invalid diagnostic payload: '+str(exc)[:120]}
        if reading is not None:readings.append({'ecu':frame['ecu'],**reading})
    if not readings:return {'source':command,'error':'No matching response'}
    good=[reading for reading in readings if not reading.get('error')]
    result={'source':command,'readings':readings}
    if good:
        result.update({key:value for key,value in good[0].items() if key!='ecu'})
        if command in ('03','07','0A'):
            result['codes']=list(dict.fromkeys(code for reading in good for code in reading['codes']))
        if any(reading.get('error') and not (reading.get('negativeResponseCode')=='78' and
               any(valid['ecu']==reading['ecu'] for valid in good)) for reading in readings):result['partial']=True
    else:result['error']=readings[0]['error']
    return result


# Consecutive optional-request timeouts tolerated before the session is dropped.
MAX_CONSECUTIVE_TIMEOUTS = 3


class DiagnosticSweep:
    def __init__(self, recorder):
        self.recorder=recorder
        self.settings=recorder.capture_settings()
        self.pending=deque()
        if self.settings['faultCodes']:self.pending.extend((None,cmd) for cmd in ('03','07','0A'))
        for enabled,command in (('liveData','0100'),('freezeFrame','020000'),('monitorTests','ATDPN'),('vehicleInfo','0900')):
            if self.settings[enabled]:self.pending.append((None,command))
        self.commands={};self.discovered={};self.failures={};self.next_at=0
        self.ecus=set();self.observed={};self.successful=set();self.snapshot_jobs=set()
        self.limitations=['Only exposed read-only diagnostics are accessible; proprietary live identifiers need definitions.',
                          'Generic OBD responders are not a scan of every vehicle module.',
                          'Freeze-frame discovery covers standard frame 0; proprietary histories are not discoverable.']
        self.last_coverage=None;self.protocol=None;self.timeouts=0
        self.marker_generation=getattr(recorder,'marker_generation',0)

    @staticmethod
    def key(header,command):return f'{header}:{command}' if header else command

    def _discover_ecus(self, response):
        for frame in response_frames(response):
            if not frame['complete']:continue
            header=physical_request_header(frame['ecu'])
            if header and header not in self.ecus:
                if len(self.ecus)>=32:
                    if 'ECU discovery limit reached' not in self.limitations:self.limitations.append('ECU discovery limit reached')
                    continue
                self.ecus.add(header)
                if self.settings['faultCodes']:
                    self.pending.extend((header,cmd) for cmd in ('1901FF','1902FF'))

    def ingest(self, command, response, requested=None, received=None, header=None):
        self._discover_ecus(response)
        if not self.settings['liveData'] and command.startswith('01'):return
        data=observation(command,response)
        key=self.key(header,command)
        self.observed[key]=time.monotonic()
        if data.get('error') or data.get('partial'):
            self.failures[key]=data.get('error') or 'Some ECU replies were incomplete'
        else:
            self.failures.pop(key,None);self.successful.add(key)
        self.recorder.record('diagnostic',{'command':command,'ecuHeader':header,
                                          'requestedAt':requested,'acquiredAt':received or time.time(),**data})
        if command=='1902FF':
            for reading in data.get('readings',[]):
                for item in reading.get('records',[]):
                    if item['status']=='00':continue
                    target=(header,item['dtc'])
                    if target in self.snapshot_jobs:continue
                    if len(self.snapshot_jobs)>=64:
                        if 'UDS detail limit reached (64 DTCs); all returned status records retained' not in self.limitations:
                            self.limitations.append('UDS detail limit reached (64 DTCs); all returned status records retained')
                        break
                    self.snapshot_jobs.add(target)
                    self.pending.extend((header,'19'+sub+item['dtc']+'FF') for sub in ('04','06'))
        return {'command':command,**data}

    def _coverage(self):
        scheduled={self.key(header,cmd) for header,cmd in self.commands}
        queried=len(scheduled & self.observed.keys())
        coverage={'discovering':bool(self.pending),
                  'supported':{mode:[f'{pid:02X}' for pid in sorted(pids)] for mode,pids in self.discovered.items()},
                  'unavailable':dict(self.failures),'scheduledReadings':len(scheduled),
                  'queriedReadings':queried,'successfulReadings':len(scheduled & self.successful),
                  'firstSweepComplete':bool(scheduled) and not self.pending and queried==len(scheduled),
                  'hasVehicleData':bool(self.successful),
                  'ecuHeaders':sorted(self.ecus),'protocol':self.protocol,'limitations':self.limitations,
                  'manufacturerDtcAccess':'discovered CAN responders' if self.ecus else 'No addressable CAN responders discovered'}
        if coverage!=self.last_coverage:
            self.recorder.set_coverage(coverage);self.recorder.record('coverage',coverage)
            self.last_coverage=coverage

    def _unavailable(self, job, now, message):
        header,command=job
        key=self.key(header,command)
        self.failures[key]=message[:160]
        self.observed[key]=now
        self.commands[job]=now+self.settings['snapshotIntervalSeconds']
        returned={'command':command,'source':command,'ecuHeader':header,'error':message[:160]}
        self.recorder.record('diagnostic',returned)
        self._coverage()
        return returned

    def step(self, transport):
        now=time.monotonic()
        marker=getattr(self.recorder,'marker_generation',0)
        if marker!=self.marker_generation:
            self.marker_generation=marker
            for job in self.commands:
                if job[1] in ('03','07','0A','1901FF','1902FF'):self.commands[job]=0
            # Only expedite known identifiers; never guess proprietary mappings.
            fast={'0B','10','23','49','4A','59','5A','61','62','69','70','7A','7B'}
            self.pending.extend((None,'01'+pid) for pid in sorted(fast) if int(pid,16) in self.discovered.get('01',set()))
        # Fault deadlines are independent of discovery and of a long PID sweep.
        urgent=[job for job,stamp in self.commands.items() if stamp<=now and job[1] in ('03','07','0A','1901FF','1902FF')]
        if urgent:job=min(urgent,key=lambda item:self.commands[item])
        elif now<self.next_at:return
        elif self.pending:job=self.pending.popleft()
        else:
            due=[job for job,stamp in self.commands.items() if stamp<=now]
            if not due:return
            job=min(due,key=lambda item:self.commands[item])
        self.next_at=now+self.settings['scanIntervalSeconds']
        header,command=job
        requested=time.time();restore=bool(header)
        try:
            transport.select_header(header)
            response=transport.query(command)
        except TimeoutError as exc:
            # Optional request: resync first so no late reply is attributed to a
            # later command. Repeated timeouts or a failed resync end the session.
            self.timeouts+=1
            if self.timeouts>=MAX_CONSECUTIVE_TIMEOUTS:
                restore=False;raise
            try:transport.resync()
            except Exception:
                restore=False;raise
            # ATSH may have been applied late; force functional addressing below.
            if header:transport.header=header
            self.next_at=time.monotonic()+self.settings['scanIntervalSeconds']
            return self._unavailable(job,now,str(exc))
        except ValueError as exc:
            return self._unavailable(job,now,str(exc))
        finally:
            if restore:transport.select_header(None)
        self.timeouts=0
        received=time.time();returned=None
        if command=='ATDPN' or (not header and len(command)>2 and int(command[2:4],16)%32==0):
            # A discovery request retried after a failure is answered now; it is
            # not a periodic reading and must not stay due forever.
            self.commands.pop(job,None)
        if command=='ATDPN':
            self.failures.pop('ATDPN',None)
            import re
            match=re.search(r'(?:^|[\r\n])A?([0-9A-C])\s*(?:>|$)',response.upper().replace('ATDPN','').strip())
            self.protocol=match[1] if match else None
            if self.protocol in ('6','7','8','9'):
                transport.protocol=self.protocol;self.pending.append((None,'0600'))
            else:self.failures['06']='Monitor and enhanced DTC discovery require CAN'
        elif not header and len(command)>2 and int(command[2:4],16)%32==0:
            self._discover_ecus(response)
            pids=supported(command,response);mode=command[:2];base=int(command[2:4],16)
            self.discovered.setdefault(mode,set()).update(pid for pid in pids if pid%32)
            bitmaps=payloads(command,response)
            if not bitmaps or any(len(raw)!=8 and not (mode=='09' and len(raw)==10 and raw.startswith('01')) for raw in bitmaps):
                self.failures[command]='Support bitmap unavailable or incomplete'
            else:self.failures.pop(command,None)
            for pid in sorted(pids):
                cmd=mode+f'{pid:02X}'+('00' if mode=='02' else '')
                if pid%32==0 and pid==base+32 and pid<=224:self.pending.append((None,cmd))
                elif pid%32:self.commands.setdefault((None,cmd),0)
            self.recorder.record('support',{'command':command,'pids':[f'{pid:02X}' for pid in sorted(pids)],
                                           'ecuReplies':response_frames(response)})
        else:
            returned=self.ingest(command,response,requested,received,header)
            interval=(self.settings['diagnosticIntervalSeconds'] if command in ('03','07','0A','1901FF','1902FF')
                      else self.settings['snapshotIntervalSeconds'] if command[:2] in ('02','06','09','19')
                      else self.settings['scanIntervalSeconds'])
            if returned.get('error'):interval=max(interval,self.settings['snapshotIntervalSeconds'])
            self.commands[job]=time.monotonic()+interval
        self._coverage()
        return returned
