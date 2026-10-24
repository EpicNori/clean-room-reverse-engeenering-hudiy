"""Decode ELM display framing without combining different ECU responses.

CAN ISO-TP length and sequence checks are independent of vehicle make/model.
Incomplete messages remain inspectable but must never become sensor values.
"""
import re


def response_frames(response):
    frames = []
    numbered = None
    declared = None
    streams = {}

    def finish(item, error=None):
        data = item['payload']
        expected = item.get('expectedBytes')
        if expected is not None:
            if len(data) < expected * 2:
                error = error or 'Incomplete response'
            data = data[:expected * 2]
        frames.append({'ecu': item.get('ecu'), 'payload': data,
                       'complete': error is None, 'error': error})

    for line in str(response).upper().replace('>', '\n').splitlines():
        line = line.strip()
        match = re.fullmatch(r'([0-9A-F]+):\s*([0-9A-F\s]+)', line)
        if match:
            index = int(match[1], 16)
            body = re.sub(r'\s+', '', match[2])
            if index == 0:
                if numbered is not None:
                    finish(numbered)
                numbered = {'ecu': None, 'payload': body, 'expectedBytes': declared, 'next': 1}
                declared = None
            elif numbered is not None:
                if index != numbered['next']:
                    finish(numbered, 'Missing or out-of-order ELM line')
                    numbered = None
                else:
                    numbered['payload'] += body
                    numbered['next'] += 1
            continue
        if numbered is not None:
            finish(numbered)
            numbered = None
        compact = re.sub(r'\s+', '', line)
        if re.fullmatch(r'[0-9A-F]{3}', compact):
            declared = int(compact, 16)
            continue
        if not compact or not re.fullmatch(r'[0-9A-F]+', compact):
            declared = None
            continue
        ecu = None
        tokens = line.split()
        # ISO 9141/J1850 and KWP replies retain their three-byte header/checksum.
        legacy=(len(compact)>=12 and (compact[:4] in ('486B','686B') or
                (0x80<=int(compact[:2],16)<0xC0 and compact[2:4]=='F1')))
        if legacy:
            length=int(compact[:2],16)&0x3F if compact[2:4]=='F1' else None
            finish({'ecu':'legacy:'+compact[4:6], 'payload':compact[6:-2], 'expectedBytes':length})
            continue
        if len(tokens) > 1 and (re.fullmatch(r'[0-7][0-9A-F]{2}',tokens[0]) or re.fullmatch(r'[01][0-9A-F]{7}',tokens[0])):
            ecu = tokens[0]
            body = ''.join(tokens[1 + (len(tokens[1]) == 1):])
        elif len(compact) % 2 and len(compact) >= 7:
            ecu, body = compact[:3], compact[3:]
        elif compact.startswith(('18DA', '18DB')) and len(compact) >= 12:
            ecu, body = compact[:8], compact[8:]
        else:
            body = compact
        if len(body) % 2:
            frames.append({'ecu': ecu, 'payload': body, 'complete': False, 'error': 'Odd hex length'})
            continue
        if not body:
            continue
        first = int(body[:2], 16)
        if ecu is None:
            # Plain ATH0 payloads, including negative responses; omit command echoes.
            if first >= 0x40:
                finish({'ecu': None, 'payload': body})
            continue
        if first < 0x10:
            finish({'ecu': ecu, 'payload': body[2:], 'expectedBytes': first})
        elif first < 0x20:
            if ecu in streams:
                finish(streams.pop(ecu), 'Replaced incomplete ISO-TP message')
            if len(body) < 4:
                continue
            streams[ecu] = {'ecu': ecu, 'payload': body[4:],
                            'expectedBytes': int(body[:4], 16) & 0xFFF, 'next': 1}
        elif first < 0x30:
            item = streams.get(ecu)
            if item is None:
                frames.append({'ecu': ecu, 'payload': body, 'complete': False,
                               'error': 'ISO-TP continuation without first frame'})
            elif (first & 15) != item['next']:
                finish(streams.pop(ecu), 'Missing or out-of-order ISO-TP frame')
            else:
                item['payload'] += body[2:]
                item['next'] = (item['next'] + 1) & 15
                if len(item['payload']) >= item['expectedBytes'] * 2:
                    finish(streams.pop(ecu))
        elif first >= 0x40:
            # Legacy ISO/KWP headers or adapters already reassembling CAN payloads.
            finish({'ecu': ecu, 'payload': body})
    if numbered is not None:
        finish(numbered)
    for item in streams.values():
        finish(item, 'Incomplete ISO-TP response')
    return frames


def response_payloads(response, prefix):
    return [frame['payload'] for frame in response_frames(response)
            if frame['complete'] and frame['payload'].startswith(prefix)]


def physical_request_header(ecu):
    """Only derive addresses from actual standard diagnostic CAN responders."""
    if ecu and re.fullmatch(r'7E[8-F]', ecu):
        return f'{int(ecu, 16)-8:03X}'
    if ecu and re.fullmatch(r'18DAF1[0-9A-F]{2}', ecu):
        return '18DA' + ecu[-2:] + 'F1'
    return None
