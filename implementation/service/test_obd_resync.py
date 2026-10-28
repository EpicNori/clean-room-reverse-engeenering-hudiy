"""Timeout recovery must never shift ELM327 replies onto later commands."""
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

from diagnostic_sweep import DiagnosticSweep, MAX_CONSECUTIVE_TIMEOUTS
from obd import Transport, decode
from obd_logging import OBDRecorder


class FakeELM:
    """Byte-level ELM327 stand-in. A stalled request answers only after the client
    gave up: 'late' delivers the old reply before the next byte is handled,
    'interrupt' lets the next byte stop the adapter like a real ELM327."""
    def __init__(self, replies, stalled=(), mode='late', mute=False):
        self.replies = {'ATI':'ELM327 v1.5', 'ATSH7DF':'OK', 'ATSH7E0':'OK', **replies}
        self.stalled = list(stalled); self.mode = mode; self.mute = mute
        self.out = bytearray(); self.line = bytearray(); self.busy = None
        self.sent = []; self.last = None; self.lock = threading.Lock()

    def sendall(self, data):
        with self.lock:
            for byte in data:
                if self.busy is not None:
                    stalled, self.busy = self.busy, None
                    if self.mode == 'late':
                        self.out += (self.replies.get(stalled, 'NO DATA')+'\r\r>').encode()
                    else:
                        self.out += b'STOPPED\r\r>'; continue  # the interrupting byte is consumed
                if byte != 13:
                    self.line.append(byte); continue
                command = self.line.decode(); self.line.clear()
                if command == '':command = self.last  # real ELM327: bare CR repeats
                self.sent.append(command); self.last = command
                if self.mute:continue
                if command in self.stalled:
                    self.stalled.remove(command); self.busy = command; continue
                self.out += (self.replies.get(command, '?')+'\r\r>').encode()

    write = sendall

    def _take(self, size):
        with self.lock:
            # Separate replies arrive in separate reads, as with real timing gaps.
            end = self.out.find(b'>')
            size = min(size, end+1) if end >= 0 else size
            part = bytes(self.out[:size]); del self.out[:size]
        if not part:time.sleep(.01)
        return part

    def recv(self, size):
        part = self._take(size)
        if not part:raise socket.timeout()
        return part

    def close(self):pass


class FakeSerial(FakeELM):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.resets = 0

    def read(self, size):return self._take(size)

    def reset_input_buffer(self):
        with self.lock:self.out.clear(); self.resets += 1


LIVE = {'010C':'7E8 04 41 0C 1A F8', '010D':'7E8 03 41 0D 3C', '0902':'7E8 10 14 49 02 01 57 30 4C',
        '0900':'7E8 06 49 00 14 00 00 00', '1902FF':'7E8 07 59 02 FF 01 23 45 A8'}


def transport(adapter, serial=False):
    t = Transport.__new__(Transport)
    t.closed = False; t.observer = None; t.protocol = '6'; t.header = None
    t.sock, t.serial = (None, adapter) if serial else (adapter, None)
    t.QUERY_TIMEOUT = .1; t.RESYNC_QUIET = .05; t.RESYNC_DEADLINE = .6
    return t


class TransportResyncTests(unittest.TestCase):
    def test_without_resync_a_late_reply_shifts_every_following_answer(self):
        t = transport(FakeELM(LIVE, stalled=['0902']))
        with self.assertRaises(TimeoutError):t.query('0902')
        self.assertIsNone(decode('0C', t.query('010C')))  # receives the 0902 reply

    def test_late_reply_and_extra_prompt_are_discarded(self):
        for mode in ('late', 'interrupt'):
            with self.subTest(mode=mode):
                adapter = FakeELM(LIVE, stalled=['0902'], mode=mode); t = transport(adapter)
                t.observer = Mock()
                with self.assertRaises(TimeoutError):t.query('0902')
                t.resync()
                self.assertEqual(decode('0C', t.query('010C')), 1726)
                self.assertEqual(decode('0D', t.query('010D')), 60)
                # Only identity probes were added; a bare CR would repeat 0902.
                self.assertTrue(all(cmd in ('0902', 'ATI', 'TI', '010C', '010D') for cmd in adapter.sent))
                self.assertEqual(adapter.sent.count('0902'), 1)
                probe = [c for c in t.observer.exchange.call_args_list if c.args[0] == 'ATI'][0]
                self.assertIsNone(probe.kwargs['error'])
                if mode == 'late':self.assertIn('49 02', probe.args[1])

    def test_serial_resync_clears_the_input_buffer(self):
        adapter = FakeSerial(LIVE, stalled=['0902']); t = transport(adapter, serial=True)
        with self.assertRaises(TimeoutError):t.query('0902')
        t.resync()
        self.assertEqual(adapter.resets, 1)
        self.assertEqual(decode('0C', t.query('010C')), 1726)

    def test_resync_failure_raises_connection_error(self):
        cases = {'silent':FakeELM(LIVE, mute=True), 'garbage':FakeELM({**LIVE, 'ATI':'?'})}
        for name, adapter in cases.items():
            with self.subTest(name=name):
                t = transport(adapter); t.observer = Mock()
                with self.assertRaises(ConnectionError):t.resync()
                self.assertLessEqual(adapter.sent.count('ATI'), Transport.RESYNC_PROBES)
                self.assertIsInstance(t.observer.exchange.call_args.kwargs['error'], ConnectionError)
        closed = Mock(); closed.recv.return_value = b''
        with self.assertRaises(ConnectionError):transport(closed).resync()


class SweepTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.rec = OBDRecorder(self.folder.name); self.rec.start()
        self.sweep = DiagnosticSweep(self.rec); self.sweep.pending.clear()

    def tearDown(self):
        self.rec.stop(); self.folder.cleanup()

    def run_job(self, t, job):
        self.sweep.pending.append(job); self.sweep.next_at = 0
        return self.sweep.step(t)

    def test_single_optional_timeout_is_reported_unavailable_and_sweep_continues(self):
        adapter = FakeELM(LIVE, stalled=['0900']); t = transport(adapter)
        result = self.run_job(t, (None, '0900'))
        self.assertEqual(result['source'], '0900'); self.assertIn('prompt', result['error'])
        self.assertNotIn('payloads', result); self.assertNotIn('value', result)
        self.assertIn('0900', self.rec.coverage['unavailable'])
        self.assertTrue(self.rec.snapshot()['recording'])
        self.assertEqual(decode('0C', t.query('010C')), 1726)
        # The retry succeeds and the discovery job is no longer permanently due.
        self.sweep.commands[(None, '0900')] = 0; self.sweep.next_at = 0
        self.sweep.step(t)
        self.assertNotIn((None, '0900'), self.sweep.commands)
        self.assertNotIn('0900', self.rec.coverage['unavailable'])

    def test_headered_timeout_restores_functional_addressing_after_resync(self):
        adapter = FakeELM(LIVE, stalled=['1902FF'], mode='interrupt'); t = transport(adapter)
        result = self.run_job(t, ('7E0', '1902FF'))
        self.assertIn('error', result); self.assertIn('7E0:1902FF', self.rec.coverage['unavailable'])
        self.assertEqual(adapter.sent[-1], 'ATSH7DF'); self.assertIsNone(t.header)
        self.assertLess(adapter.sent.index('ATI'), adapter.sent.index('ATSH7DF'))
        self.assertEqual(decode('0D', t.query('010D')), 60)

    def test_consecutive_optional_timeouts_end_the_session(self):
        jobs = [(None, '0900'), (None, '0902'), (None, '0904')]
        adapter = FakeELM(LIVE, stalled=[cmd for _, cmd in jobs]); t = transport(adapter)
        for job in jobs[:MAX_CONSECUTIVE_TIMEOUTS-1]:self.assertIn('error', self.run_job(t, job))
        probes = adapter.sent.count('ATI')
        with self.assertRaises(TimeoutError):self.run_job(t, jobs[MAX_CONSECUTIVE_TIMEOUTS-1])
        self.assertEqual(adapter.sent.count('ATI'), probes)  # no resync on the failing path

    def test_successful_reply_resets_the_timeout_count(self):
        # Headerless 010C reply: no ECU discovery, so no UDS jobs are queued in between.
        adapter = FakeELM({**LIVE, '010C':'410C1AF8'}, stalled=['0900', '0902', '0904', '0906'])
        t = transport(adapter)
        for job in ((None, '0900'), (None, '0902'), (None, '010C'), (None, '0904'), (None, '0906')):
            self.run_job(t, job)
        self.assertEqual(self.sweep.timeouts, 2)

    def test_failed_resync_propagates_connection_error(self):
        t = Mock(); t.query.side_effect = TimeoutError('ELM327 did not return a prompt')
        t.resync.side_effect = ConnectionError('ELM327 did not resynchronise after a timeout')
        with self.assertRaises(ConnectionError):self.run_job(t, ('7E0', '1902FF'))
        self.assertNotIn(unittest.mock.call(None), t.select_header.call_args_list)


if __name__=='__main__':unittest.main()
