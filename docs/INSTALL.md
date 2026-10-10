# Easy Raspberry Pi installation

Use **64-bit Raspberry Pi OS with Desktop**, Bookworm or Trixie, on a Pi with
at least 4 GiB free space. Configure the user, internet connection and actual
Wi-Fi country in Raspberry Pi Imager/system settings first. OS Lite and 32-bit
images are not supported by this installer.

## One-line setup

Open a terminal as your ordinary desktop user and paste:

```sh
bash -o pipefail -c 'curl -fsSL https://raw.githubusercontent.com/EpicNori/clean-room-reverse-engeenering-hudiy/main/install.sh | bash'
```

The command downloads and executes this repository's installer as your user.
It shows the plan and asks for confirmation and your sudo password for OS
steps. It builds from source, so allow time for downloads and native compilation.
No proprietary Hudiy installation, activation or API service is required.

To inspect the script before running it, clone this repository and run
`bash install.sh --check`, then `bash install.sh`. The read-only check requires
Git/Python and an existing checkout; it does not install packages or clone one.

## What the installer does

1. Checks the Pi, 64-bit OS, supported release, desktop/labwc and free disk space.
   It refuses root execution and installation while our car app is running.
2. Clones to `~/hudiy-recreation`, or updates an existing clean `main` checkout
   from the exact project remote with a fast-forward only. Another remote,
   branch, dirty checkout or symlinked target is retained and refused. Set
   `HUDIY_INSTALL_DIR` if you need a different directory.
3. Installs native build dependencies, BlueZ/OBEX/oFono, NetworkManager/DHCP,
   PipeWire/WirePlumber, Python OS packages and the standard Android USB rules.
4. Downloads the current official **Node 22 ARM64** release into our private user
   state directory, checks the official HTTPS checksum manifest, validates
   extraction paths/links and builds with that runtime. System Node stays unchanged.
   This checksum checks downloaded bytes; it is not an independent signature audit.
5. Runs `npm ci`, builds the frontend, runs frontend/backend checks, then compiles
   and tests the native receiver. Native compilation uses one job on smaller-memory
   boards, and at most two on larger ones.
6. Configures the user's WirePlumber HFP backend for oFono, with the appropriate
   0.4/Lua or 0.5/config format. Existing changed files receive timestamped backups.
7. Adds the desktop user to `dialout`, `video` and `plugdev`; enables Bluetooth and
   oFono; adds a narrowly scoped panel-backlight rule. It leaves the app unprivileged.
8. Backs up/selects our labwc startup. Default setup enables desktop autologin for
   this user so the app can open after boot. Use `--no-autologin` to keep OS login
   authentication; our app will then start after graphical login instead.
9. Attempts to prepare an **inactive protected car hotspot**, independently of
   Hudiy. Unsupported Wi-Fi/conflicting settings are reported while retaining the
   USB/dashboard installation. Setup neither switches your Wi-Fi connection nor
   silently overwrites existing car credentials.

The installer never automatically reboots. Reboot when convenient to apply
new group membership, user audio configuration and desktop startup. It does not
restart your display manager or enable the car network during installation.

## First use

- Pair the phone in **Connections**, allow contact sharing and accept Android Auto.
- For wireless projection, enable **Car Wi-Fi** in Android Auto settings when ready.
  A single Wi-Fi adapter switches from its previous network at that step. Keep
  Ethernet/local recovery access during the first activation. The generated Wi-Fi
  key stays private and is handed to the phone through our Bluetooth bootstrap.
- Bluetooth reconnect and automatic Android Auto opening are separate saved
  options. Choose each explicitly for your phone.
- Pair/select the powered ELM327 for required vehicle data. A separate Bluetooth
  receiver for the car radio is optional and selected separately in Sound.
- **Quit** returns to the desktop. **Ctrl+Alt+Shift+Q** also exits our app.

Installation cannot supply missing microphone, panel backlight, car power
controller, radio receiver or a powered vehicle. No real call/playback action
or ECU write is part of setup. Bluetooth conversation audio, cold boot/recovery,
fresh-image phone services and live OBD data still require hardware checks.
Sustained native audio currently has a documented queue-overflow issue.

## Options and retry

```sh
bash install.sh --check           # Inspect prerequisites without changes
bash install.sh --no-autologin    # Keep OS login authentication
bash install.sh --skip-hotspot    # Prepare USB/dashboard without a car AP
bash install.sh --yes             # Accept the printed default plan; sudo still applies
```

On failure, the installer stops before subsequent stages and keeps completed
package/build steps for retry. It does not roll back the whole OS package
transaction. Build failure cannot select startup or run our privileged system
helper. Changed configuration files are backed up; unrelated files, pairings and
private preferences are retained. An already valid hotspot is left unchanged.

If boot/login starts the app when you need the desktop, use Quit/the shortcut.
For startup recovery, inspect `~/.config/labwc/autostart` and its timestamped backup,
and remove only the managed `BEGIN HUDIY RECREATION` block. System autologin backups
are next to `/etc/lightdm/lightdm.conf` and the existing getty autologin file.
Dependencies are not automatically removed during recovery.

## Verification scope

The installer tests cover platform/root/Lite rejection, memory limits, checksum
selection/failure, safe archives/internal npm links, audio configuration versions,
idempotent user backups, read-only checks, running-app refusal, option handling and
build-failure gates. Mocked apply-flow tests never execute sudo or change services.

On the existing Bookworm Pi we also checked the actual package plan with
`apt-get --simulate`, piped bootstrap syntax/read-only execution, and a genuine
official Node 22.23.3 download/checksum/extraction/version run. Its running phone
session was not stopped to test installation. These checks do not establish an
end-to-end install/reboot on a freshly flashed Bookworm or Trixie image.

References: [Raspberry Pi system configuration](https://www.raspberrypi.com/documentation/computers/configuration.html),
[WirePlumber Bluetooth configuration](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html),
[official Node downloads](https://nodejs.org/en/download), and
[our hotspot setup](HOTSPOT_SETUP.md). The [backend rules](backend-rules.md)
record the exact local privilege boundaries.
