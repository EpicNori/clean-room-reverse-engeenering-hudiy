# Automatic diagnostic capture

The recorder discovers exposed diagnostic capabilities without a make, model,
year, VIN lookup, internet connection or vehicle profile. Start recording before
the symptom, or enable **Record on OBD connection**. All existing capture
categories default to enabled; saved category, timing, recording-mode and storage
choices remain configurable.

## What is captured

- Every advertised standard Mode 01 live identifier, standard Mode 02 frame-zero
  identifier, CAN Mode 06 monitor and Mode 09 information identifier, including
  identifiers without a built-in numeric decoder. Unknown payloads remain hex.
- Stored, pending and permanent generic fault-code requests, with separate
  unavailable, negative, incomplete and valid-empty results.
- Read-only UDS fault count/format (`19 01 FF`) and fault/status records
  (`19 02 FF`) from actual discovered standard CAN diagnostic responders.
  Nonzero-status DTCs additionally request available snapshot records
  (`19 04 <DTC> FF`) and extended data (`19 06 <DTC> FF`). Raw manufacturer DTCs,
  status masks and status flags are retained without invented descriptions.
- Every configured custom sensor, independently of visible tiles, plus selected
  dashboard samples and session estimates according to the capture settings.
- Raw request/reply traffic, ECU source and requested address, request/receive
  times, connection events, errors, coverage and fault markers.

CAN headers stay enabled when supported. Different ECU messages are not merged.
ISO-TP and numbered ELM replies are checked for length and sequence; transport
padding is removed. Incomplete messages remain raw/error evidence and never
become sensor values. ISO 9141/KWP display headers are also recognized, but UDS
discovery is restricted to CAN.

Read-only discovery derives physical addresses only from actual standard
responders: `7E8–7EF` to `7E0–7E7`, or `18DAF1xx` to `18DAxxF1`. It does not
guess a manufacturer, sweep arbitrary CAN addresses, enter extended sessions,
authenticate, clear codes, change settings, or operate actuators.

## Timing and power-loss events

Discovery is interleaved with ordinary polling. Fault refresh deadlines take
priority over queued discovery and live-data sweeps. The adapter still executes
requests sequentially; configured intervals are minimum delays, not guaranteed
sample rates. Each diagnostic reading and each dashboard source has its own
acquisition time. CSV reading rows use that time rather than the batch-save time.
Motion estimates use the speed reading's acquisition time and retain existing
gap invalidation.

Use **Mark fault / power loss** during a recording to save an event timestamp and
expedite known fault reads and advertised relevant live identifiers. This does
not identify the cause or reconstruct information from before recording began.

## Capture coverage and saved files

Coverage shows discovered identifiers/ECUs, scheduled versus queried/successful
readings, unavailable responses and whether the first scheduled sweep finished.
Coverage events are saved in JSONL; the footer and private metadata retain a
compact capture summary after restart. A connection-only session is labelled
as having no usable vehicle responses. A saved file can still be a partial
diagnostic capture; file completion and capture coverage are separate facts.

Raw replies up to 64 KiB are retained as ordered `exchange` events. Incoming
data extends a three-second idle timeout, with a thirty-second hard deadline.
When a reply
needs multiple events, join `response` values by `exchangeId`, in `part` order
from zero through `parts - 1`. `responseComplete` is false for partial transport
failures or the explicit reply ceiling. Timeout/disconnect partial bytes are
retained before reconnecting; they are not reused for a later command.

Structured data exceeding a single bounded event is stored as `<type>-part`
events. Join `content` by `eventId` and `part`, then parse the resulting JSON.
The original event time is retained on every part. Consumers must flag missing
parts. JSONL is the complete evidence stream; CSV retains the same chunk and
coverage metadata in `data_json`.

## What “all” cannot mean

This captures exposed supported diagnostics within the selected categories and
explicit storage/transport limits. It cannot expose every proprietary signal,
every module behind a gateway, protected data, undocumented Mode 22 identifiers,
legacy manufacturer fault protocols or proprietary freeze-frame histories.
Standard freeze-frame discovery currently covers frame zero. Unsupported UDS
reads stay visibly unavailable; their failure does not imply an empty fault list.
Descriptions and scaling for manufacturer monitor/snapshot data can require
manufacturer definitions; raw data is retained rather than guessed.

Discovery is capped at 32 standard CAN responders. UDS detail requests cover up
to 64 distinct nonzero-status DTCs per connection; every returned fault/status
record remains raw and structured even when that detail limit is reached, and
coverage reports the limit. The existing queue/session/storage ceilings still
stop visibly instead of silently dropping data. Decoded events also have a
1 MiB ceiling. No finite capture guarantees enough evidence to diagnose every
intermittent fault.

Protocol references: [ELM327 display framing](https://www.elmelectronics.com/wp-content/uploads/2020/05/ELM327DSL.pdf),
[UDS ReadDTCInformation](https://udsoncan.readthedocs.io/en/latest/udsoncan/services.html#readdtcinformation-0x19).
These are protocol references, not added runtime dependencies.
