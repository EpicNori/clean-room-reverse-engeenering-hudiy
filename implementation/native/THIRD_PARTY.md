# Native runtime licensing and source

This directory is licensed under **GPL-3.0-or-later**, including the independently written host and its integration with the GPL protocol library. See `LICENSE`. The existing MIT license continues to apply to the separately distributed dashboard/backend sources.

The build fetches the protocol library from [OpenAuto Prodigy](https://github.com/mrmees/openauto-prodigy), pinned to commit `3afc5dd8bbacb5ce68e109189b18b14b251fabef`. Only `libs/prodigy-oaa-protocol` is linked. Its protobuf submodule [Open Android Auto](https://github.com/mrmees/open-android-auto) is pinned upstream to `5ff4aa218dd33913237993f2968bf70e16dc464e` and also retains its GPL notices.

The channel capability construction in `main.cpp` adapts the upstream `src/core/aa/ServiceDiscoveryBuilder.cpp` at that pinned revision. Our wireless handshake follows the wire fields in the upstream protobuf definitions. The native host, USB transport, private IPC, touchscreen surface and application lifecycle are implemented here. No upstream dashboard, branding or proprietary Hudiy binary/assets are bundled.

Qt, FFmpeg, libusb, OpenSSL and Protobuf retain their respective licenses. A distributor of a native binary must provide its corresponding source, this directory's modifications, the exact protocol dependency/submodule sources, build instructions and license notices under their applicable terms. Do not advertise the linked native executable as MIT-only.

The independently implemented peaking EQ in `audio_dsp.hpp` uses mathematical coefficient formulae described in the [W3C Audio EQ Cookbook](https://www.w3.org/TR/audio-eq-cookbook/), with Q 1.4 to match our Web Audio graph. It does not import a proprietary audio implementation. Signal tests are in `test_audio_dsp.cpp`.

The bounded threaded output in `audio_output.hpp` and its regression probes are our own GPL implementation using Qt's public API. They do not copy an upstream audio implementation. Qt 6.4-compatible sink feeding is isolated from the graphical event loop; no newer callback-only audio API is required.
