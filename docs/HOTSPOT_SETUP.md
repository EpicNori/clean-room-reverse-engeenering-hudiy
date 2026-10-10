# Independent car hotspot setup

Our wireless Android Auto receiver needs its own protected 5 GHz network. A home
router is not required in the car. `provision_hotspot.py` prepares a new
NetworkManager profile and our private settings without reading the proprietary
Hudiy installation.

## Prerequisites

- Run as the same ordinary user who logs into the Pi desktop and launches our app.
  Do not run this installer with sudo: it must save settings for that user.
- Install `network-manager` and `python3-dbus`. NetworkManager must manage `wlan0`,
  which must support AP mode, 5 GHz and WPA2/CCMP. Our current native/Bluetooth
  handoff uses this adapter; selecting another adapter is not implemented.
- Set the Pi's actual Wi-Fi country through its system configuration. The
  installer does not change the regulatory domain. A hardware capability check
  alone cannot prove that a channel is usable in the current country.
- The desktop user needs NetworkManager permission to create/manage connections.
  The tool does not install a permissive Polkit policy or escalate privileges.
- Quit our app before first-time provisioning. Already valid setup can be checked
  while it is running. Keep Ethernet or local recovery access for first activation.

See the [Raspberry Pi configuration documentation](https://www.raspberrypi.com/documentation/computers/configuration.html)
for system configuration and the main [README](../README.md#run-on-the-raspberry-pi)
for native build/startup prerequisites. BlueZ, PBAP, HFP and PipeWire provisioning
remain separate; this tool does not turn a fresh OS image into a fully verified
car installation.

## Inspect, prepare, then activate

From the repository root on the Pi:

```sh
# Read-only hardware/profile/settings check; creates no files.
python3 implementation/launcher/provision_hotspot.py

# Fresh setup only: create an inactive profile and private configuration.
python3 implementation/launcher/provision_hotspot.py --apply

# Optional name for a fresh installation; existing names are retained.
python3 implementation/launcher/provision_hotspot.py --apply --ssid 'My car'

# Start our application afterward.
python3 implementation/launcher/launcher.py
```

For a fresh installation, preparation creates:

- NetworkManager profile `hudiy-recreation-car`, restricted to the desktop user,
  bound to `wlan0`, with autoconnect **off**.
- 5 GHz AP mode, channel 36, WPA2/RSN with CCMP and a randomly generated key. The
  key is passed over D-Bus rather than command-line arguments and never printed.
- Shared IPv4 `192.168.12.1/24`, with no default route from this profile. IPv6 is
  disabled. NetworkManager supplies the local DHCP service during activation.
- `~/.local/share/hudiy-recreation/wireless.json`, with `enabled: false`, the
  matching SSID/key, gateway and receiver port 5277. The directory is 0700 and
  the file is 0600, atomically published and flushed before success.

In our app's **Android Auto settings**, enable **Car Wi-Fi** and confirm the
network change. The existing runtime control activates the prepared profile,
saves the enabled choice and sets its boot autoconnect flag. A single Wi-Fi
adapter switches away from a previous client network at this step. Pair the
phone through our Bluetooth menu, allow Android Auto and keep the phone's VPN
off when it interferes with projection. Wireless admission still follows the
saved settings; automatic opening is a separate option.

Preparation itself never activates, deactivates or restarts a network. Repeating
`--apply` on a matching installation returns `changed: false`; it does not rotate
the key, replace settings or interrupt a phone session. `--ssid` only supplies a
name for a fresh installation.

## Conflicts and failed setup

The tool refuses duplicate car profiles, a profile without matching private
settings, settings without a profile, mismatched SSID/key/network/autoconnect,
oversized or public private settings, and symlinked targets. It does not replace
or remove an existing profile to resolve a conflict. Review such a configuration
locally rather than deleting credentials or connection profiles blindly.

If saving fresh private settings fails after profile creation, the tool attempts
to delete only the profile UUID it just created. A failed rollback is reported
explicitly. D-Bus timeout/permission errors may have an uncertain outcome; inspect
the resulting state before retrying. Error output excludes raw D-Bus settings.

## Verification and limits

On the reference Bookworm Pi / NetworkManager 1.42.4:

- The actual adapter reported AP, 5 GHz, WPA2/RSN and CCMP capabilities.
- A uniquely named inactive test profile was persisted through the same D-Bus
  adapter, its stored key matched, and it was deleted by its exact UUID afterward.
  The set of active connections was unchanged throughout.
- Private-file roundtrip produced 0600/0700 modes on the Pi.
- The existing migrated car profile was initially unbound to an interface. Its
  saved binding was aligned to `wlan0` without restarting the active connection.
  NetworkManager omits default-true autoconnect from some D-Bus replies; the
  checker now handles that correctly, with a regression test.
- Repeated production `--apply` then reported `installed: true, changed: false`
  while our live wireless projection remained connected.
- Eleven installer tests pass both on Windows and on the Pi. These use fake
  NetworkManager operations and do not activate a real network.

This verifies profile creation, ownership, persistence, repeated setup and
non-disruption. It does **not** establish a complete clean-image installation,
regulatory/channel availability, fresh phone pairing or unattended cold boot.

The profile and typed settings follow NetworkManager's
[AddConnection API](https://networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.Settings.html),
[Wi-Fi settings](https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html),
[security settings](https://networkmanager.dev/docs/api/latest/settings-802-11-wireless-security.html)
and [IPv4 shared settings](https://networkmanager.dev/docs/api/latest/settings-ipv4.html).
