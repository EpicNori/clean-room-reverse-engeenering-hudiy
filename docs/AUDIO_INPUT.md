# Microphones and audio capture

Open **Settings → Audio → Audio input**, or use the microphone link on **Sound**.

1. Plug in a USB microphone and tap **Refresh devices**. For a Bluetooth microphone, use **Pair Bluetooth device** first. A Bluetooth device appears only when Linux exposes an input for its capture-capable audio profile; pairing an output-only radio receiver does not create a microphone.
2. Select **System default** to follow Linux's current default, or select a specific enumerated microphone. Unsupported entries remain visible but cannot be selected. The receiver currently needs 16 kHz, mono, signed 16-bit capture; it does not yet convert other formats.
3. Set **Input volume** (0–100%) and **Mute input**, then tap **Save input settings**. **Discard changes** restores the last saved values. Changes remain drafts until saved. The device list refreshes periodically without overwriting a draft.

Gain is a software attenuation of outgoing PCM, so it does not depend on optional hardware gain support. Mute and volume zero send silent PCM while an existing Android Auto capture request is active. Opening this page, refreshing, saving or pairing does not start recording. There is no microphone test recorder and no audio file is stored.

A specifically selected microphone stays selected when unplugged. It reports unavailable instead of silently choosing a different input, and it is eligible again when its device ID returns. System default intentionally follows default-device changes. Device changes during an existing voice capture request restart only that owned capture source. If the initial open request fails, another Android Auto voice request is needed after fixing the device.

The native receiver waits for the backend's saved capture preferences before accepting microphone capture, so a saved mute is not temporarily bypassed during startup. Settings are privately saved in `~/.local/share/hudiy-recreation/input.json` and resent whenever the backend reconnects to our native socket. “Saved” means durable storage; the status separately checks the native settings echo and actual capture state.

## Scope and verification

These controls select **Android Auto voice input** in our independent Qt receiver. They do not alter the system-wide default source, route HFP/oFono conversation audio, configure Bluetooth profiles, grant OS permissions, or change optional Bluetooth radio output. A microphone may need Linux device/profile setup before it can appear.

Local checks cover strict schemas, unknown/unsupported device rejection, persistence/reload, missing-device preservation, write-failure rollback, native echo vs saved state, snapshot isolation, offline/unconfigured behavior, menu migration and the loopback HTTP boundaries. Browser checks use an explicitly labeled synthetic fixture, never a real microphone. Native compilation and all six CTests now pass on the reference Bookworm Pi. Its microphone status is available/applied with capture inactive but currently enumerates no inputs. All real USB/Bluetooth/Android Auto audio acceptance remains unchecked; use the [README hardware checklist](../README.md#microphones-and-audio-capture).

The native integration uses Qt's [audio-input discovery and hotplug notifications](https://doc.qt.io/qt-6/qmediadevices.html) and [QAudioSource device/format capture and state/error reporting](https://doc.qt.io/qt-6/qaudiosource.html), with APIs compatible with the existing Qt 6.4 baseline. Newer callback-only APIs are not required.
