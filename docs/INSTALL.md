# Easy Raspberry Pi installation

Use **64-bit Raspberry Pi OS with Desktop**, Bookworm or Trixie, on a Pi with
at least 4 GiB free space. Configure the user, internet connection and actual
Wi-Fi country in Raspberry Pi Imager/system settings first. OS Lite and 32-bit
images are not supported by this installer.

## Choose and check the OS image

In Raspberry Pi Imager, select **Raspberry Pi OS (64-bit)** with a graphical
desktop, based on Bookworm or Trixie. The Desktop/Full editions include a
desktop; Lite does not. Check the explicit **64-bit** label before writing.
Configure your user, SSH access and network in Imager if remote setup is needed.
See Raspberry Pi's [OS editions and architectures](https://www.raspberrypi.com/documentation/computers/os.html)
and [Imager instructions](https://www.raspberrypi.com/documentation/computers/getting-started.html).

After first boot, run:

```sh
dpkg --print-architecture
```

The result must be **`arm64`**. **`armhf` means 32-bit userspace** and is not
supported by this installer. A Pi can report `aarch64` from `uname -m` while
still running 32-bit packages, so the kernel architecture alone is insufficient.
Enabling a 64-bit kernel does not convert an existing 32-bit OS image. For the
supported setup, back up any files you need and reflash with the 64-bit desktop
image, then repeat this check. The installer refuses an unsupported architecture
before cloning/building the app or changing OS packages.

## Optional: screen orientation before installing

**Skip this section if the image is already upright and touch input is aligned.**
For the usual car mounting, use **landscape (horizontal)** orientation. A fresh
OS image may start in portrait, sideways or upside down depending on the panel
and how it is mounted. coscarOS adapts its layout to the screen size, but does
not automatically rotate the OS display or calibrate touch input. Configure
these on the Pi desktop before installation so the first fullscreen start is
usable. An already correct horizontal image does not need rotation.

1. Open **Preferences → Control Centre → Screens** on the Raspberry Pi desktop.
   On older images, open **Preferences → Screen Configuration** instead.
2. Right-click the rectangle for the car display and select **Orientation**.
   Check the selected output: it may be `DSI-1`, `HDMI-A-1` or another name.
   With multiple monitors, change the car display rather than the other screen.
3. Select **Left** or **Right** for a quarter-turn, **Inverted** for an upside-down
   image, or **Normal** to undo rotation. The native orientation depends on the
   panel, so choose by the visible result in its physical mounting. Do not assume
   that Normal always means landscape.
4. Select **Apply**, then confirm only if the result is usable. If it is wrong,
   cancel/revert it; if the tool offers a confirmation timeout, let it revert.
   A USB mouse or keyboard can help while touch is not aligned.
5. Tap near each corner and drag across the screen. Touch should follow the
   same direction and land where you tap. In Screen Configuration, the
   **Touchscreen** option, when available, assigns the touch device to its display.
   If the image is correct but touch remains rotated, follow the panel vendor's
   Wayland/labwc touch-mapping instructions; changing image rotation repeatedly
   is not touch calibration.
6. Reboot and check the desktop orientation and touch again, then continue with
   [one-line setup](#one-line-setup). After installation, verify them once more
   in coscarOS's dedicated car session; rotation/touch persistence across that
   session is still a hardware acceptance check. **Quit**, or **Ctrl+Alt+Shift+Q**,
   returns to the desktop if you need to correct settings. If display preferences
   are changed after installation, recheck them after the next car-session start.

Use the desktop/Wayland method for this installer. The kernel-command-line
`rotate=` example in Raspberry Pi's documentation affects the text console and
does not replace graphical-session rotation. No blanket `config.txt` display or
touch overlay edit is required by this guide.

Sources: Raspberry Pi's [Touch Display 2 orientation guide](https://www.raspberrypi.com/documentation/accessories/touch-display-2.html#change-display-orientation)
and [Touch Display screen/touch assignment instructions](https://www.raspberrypi.com/news/how-to-use-the-raspberry-pi-touch-display/#change-screen-orientation).

## One-line setup

After checking screen orientation (or skipping it if already correct), open a
terminal as your ordinary desktop user and paste:

```sh
bash -o pipefail -c 'curl -fsSL https://raw.githubusercontent.com/desquerteur/coscarOS/main/install.sh | bash'
```

The command downloads and executes this repository's installer as your user.
It shows the plan and asks for confirmation and your sudo password for OS
steps. SSH hotspot setup may also show a normal Polkit password prompt for
NetworkManager. It builds from source, so allow time for downloads and native compilation.
No proprietary Hudiy installation, activation or API service is required.

To inspect the script before running it, clone this repository and run
`bash install.sh --check`, then `bash install.sh`. The read-only check requires
Git/Python and an existing checkout; it does not install packages or clone one.

## What the installer does

1. Checks the Pi, 64-bit OS, supported release, desktop/labwc and free disk space.
   It refuses root execution and installation while our car app is running.
2. Clones to `~/coscarOS` (reuses an existing `~/hudiy-recreation` checkout), or updates an existing clean `main` checkout
   from the exact project remote with a fast-forward only. Another remote,
   branch, dirty checkout or symlinked target is retained and refused. Set
   `COSCAROS_INSTALL_DIR` (legacy `HUDIY_INSTALL_DIR` is also accepted) if you need a different directory.
3. Installs native build dependencies, BlueZ/OBEX/oFono, NetworkManager/DHCP,
   PipeWire/WirePlumber, the Qt Wayland runtime, Python OS packages and the standard Android USB rules.
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
The earlier native audio queue-overflow issue was corrected; audible car-radio routing still needs hardware acceptance.

## Options and retry

```sh
bash install.sh --check           # Inspect prerequisites without changes
bash install.sh --no-autologin    # Keep OS login authentication
bash install.sh --skip-black-boot  # Keep existing OS boot theme/session selection
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

On 25 October 2026 we removed the existing application's active source/build,
private Node runtime, OTA selection and managed startup configuration, keeping
recoverable backups and user data. The public piped one-liner reproduced a real
confirmation failure (`File or stream is not seekable`). The corrected installer
completed the actual dependency installation, fresh Node download, frontend/backend
checks, ARM64 compilation, six native tests and startup setup. A subsequent reboot
exposed a separate LightDM/Xsession quoting failure; the fixed-path session wrapper
addresses it without shell evaluation of checkout paths.

See [the installation acceptance report](INSTALL_VERIFICATION.md) for the exact
results and remaining checks. A subsequent genuinely fresh **64-bit Trixie desktop**
install also passed the public installer, native launch, landscape persistence and
automatic boot. A freshly flashed 64-bit Bookworm image remains untested.
The repaired session booted automatically with both web views ready. After the
fix was published, the exact public piped command passed on this reference Pi
with exit 0, 35 frontend tests, 246 backend tests and all six native checks.

References: [Raspberry Pi system configuration](https://www.raspberrypi.com/documentation/computers/configuration.html),
[WirePlumber Bluetooth configuration](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html),
[official Node downloads](https://nodejs.org/en/download), and
[our hotspot setup](HOTSPOT_SETUP.md). The [backend rules](backend-rules.md)
record the exact local privilege boundaries.


## Updating the installed application

After installing the OTA-capable revision once, use Settings → System → Software updates for normal application changes. See [OTA setup, trust and recovery](OTA_UPDATES.md). The normal installer remains necessary for system-package or bootstrap/protocol changes and selects its rebuilt baseline after successful checks. Offline maintenance can start the original installation with `implementation/launcher/launcher.py --baseline` after quitting the app.


## Black startup

The installer now includes a reversible black Plymouth/quiet boot setup and a separate panel-free LightDM/labwc car session. `--skip-black-boot` skips these OS changes; `--no-autologin` keeps authentication unchanged. A saved Appearance switch controls the next app/session start. Runtime readiness waits for both web views, with a recovery screen after 60 seconds and saved desktop startup after Quit. This requires one-time privileged setup outside OTA, plus a native rebuild. See [Black startup](BLACK_STARTUP.md) for exact apply/restore commands, backups and pending Pi tests.


## Later device-test repairs

The guided package list now includes `pulseaudio-utils` for `pactl` on PipeWire
systems. Run the normal installer for OS-package additions; OTA stays unprivileged
and does not run apt. Headless installer/provisioning terminal checks use
`O_NOCTTY`. Saved enabled car mode is restored by the runtime after login, with
bounded retries and existing NetworkManager permissions. See
[the current Pi acceptance report](README_TEST_RESULTS.md).
