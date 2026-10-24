# Automatic diagnostic capture verification — 24 October 2026

The change requires no vehicle profile. Software verification uses synthetic
responses only; it does not establish hardware compatibility or a repair diagnosis.

- Backend: 237 tests, 233 passed and four platform-specific checks skipped on
  Windows. Includes a real loopback ELM transport that discovers two ECU
  responders and requests UDS fault/status/details at their derived addresses.
- Protocol/evidence regressions cover interleaved ECUs, CAN and legacy headers,
  incomplete lengths and missing sequence frames, transport padding, negative
  versus valid-empty UDS responses, long/partial replies, timeout extension while
  bytes arrive, raw/structured chunk reconstruction, per-reading CSV timestamps,
  discovery-independent fault deadlines, marker requests, rejected enhanced
  addressing fallback, disabled categories, private persistence and write-command
  rejection. The existing custom-sensor test's incorrect declared payload length
  was corrected from eight to seven bytes; truncated replies now fail validation.
- Frontend: all 35 Node tests pass; Vite production and Sites packaging succeed.
  Dashboard production dependency audit: zero known advisories.
- Browser: production build served at isolated loopback port 8767. Verified manual
  Start, automatic capability/ECU discovery, Mark fault, Stop & save, saved coverage
  and CSV export. The synthetic session retained one marker, UDS count/status
  replies, eight of eight scheduled readings queried, seven successful and one
  explicitly unavailable. No real vehicle identifier or recording is published.
- Security review: vehicle requests remain strictly read-only and bounded;
  enhanced targets derive only from standard responders. Existing Host/Origin,
  body limits, private filesystem/export guards and path validation remain.
  Marker API rejects extra fields, cross-origin requests and inactive sessions.

The Raspberry Pi was deliberately left running at the owner's request. This
revision was not installed or restarted there. Powered-vehicle, legacy adapter,
extended UDS, gateway/module coverage, touchscreen and ignition/power-cut tests
remain hardware acceptance work. The earlier real recording cannot acquire
missing information retroactively. Exact scope and reconstruction rules are in
[OBD_CAPTURE.md](OBD_CAPTURE.md); API boundaries are in [backend rules](backend-rules.md).
