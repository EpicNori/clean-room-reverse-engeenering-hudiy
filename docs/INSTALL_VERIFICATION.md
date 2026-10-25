# Installation acceptance — 25 October 2026

## Scope and source

The owner authorized stopping, removing and reinstalling coscarOS while the
vehicle was parked. The reference machine is a Pi 5 running 64-bit Raspberry Pi
OS Bookworm, kernel 6.12.96 and Qt 6.4.2. The public source tested was
`834903f862fe5be7461a923d230c6dc72f678eff` from `EpicNori/coscarOS` on `main`.
The repaired run adds the installer/session changes described below.

This was an actual application uninstall/reinstall on the existing OS. It was
not an OS reflash: system packages, BlueZ pairing data and the existing protected
hotspot were retained. Fresh-image Bookworm/Trixie acceptance remains open.

## Removal and recovery

The test stopped/saved recording and quit the owned app. The reversible helper
restored managed boot/session files; the app's user startup, audio configuration,
backlight rule, both former source/build directories and private runtime/state
were moved aside with recovery copies. The new installation did not reuse the
old native executable/build directory, managed Node installation or OTA selection.

User preferences, recording files and browser profile were preserved. All
**13 original top-level preference files and eight existing recordings** matched
their pre-removal SHA-256 hashes after reinstall and before first launch.
Private backups and detailed logs remain on the owner’s Pi; they are not public
repository artifacts. OBD automatic recording was temporarily disabled around
restarts and its original saved choice was restored after boot acceptance.

## Public one-liner failure and repair

The exact README command was executed after removing active application paths:

```sh
bash -o pipefail -c 'curl -fsSL https://raw.githubusercontent.com/EpicNori/coscarOS/main/install.sh | bash'
```

It cloned the correct source, then exited **1** with
`File or stream is not seekable`. Opening `/dev/tty` with Python `r+` selected a
buffer requiring seekability. Confirmation now reads the controlling terminal
in read-only text mode and prints the prompt to standard output. It still works
when the piped installer occupies standard input; `--yes` is the explicit
noninteractive option. A missing terminal reports that option clearly.

A real POSIX pseudo-terminal regression tests Yes/No/empty responses without
using standard input. All **13 installer tests passed on the Pi**. The package
list also now explicitly includes `qt6-wayland`: the platform plugin belongs to
that runtime package and must not depend on a previous installation providing it.
It was already present on this reference OS; absence on a fresh image has not
been tested.

## Corrected full install and first launch

The corrected helper was copied into the newly cloned source checkout. With
standard input occupied by a pipe, the real confirmation accepted the answer
from the controlling terminal. The full installer completed with **exit 0**:

- Actual APT dependency installation succeeded.
- A fresh official private **Node 22.23.4 ARM64** download, checksum validation
  and extraction succeeded.
- Production frontend build and **35 frontend tests** passed.
- **239 backend tests** passed on the Pi at this stage.
- Clean native Release compilation and **all six CTests** passed.
- User audio/device/startup and privileged black-boot setup succeeded.
- The existing protected hotspot was validated and reported unchanged.

The installed baseline selection had no active/pending OTA release. The actual
native executable ran from the new `~/coscarOS/implementation/native/build/`
directory with its owned backend. The readiness API reported **uiReady=true**;
the dashboard and application navigation were checked. Normal Quit displayed
the desktop-return message and stopped the native app and backend. Nonfatal
Fontconfig/QtWebEngine diagnostic warnings were observed; first launch was not
warning-free.

## Reboot-discovered session bug

The first controlled reboot changed the kernel boot ID, but automatic login's
session exited with status 2 and fell back to the greeter. The actual session log
showed Python trying to open a filename containing literal quote characters.
Debian Xsession ultimately uses `exec $STARTUP`; embedded quotes in that string
do not regain shell quoting semantics.

The session entry now uses fixed unquoted arguments pointing to the root-owned
`/usr/lib/coscaros/session.py` wrapper. That wrapper uses Python `runpy` with a
literal source path, supporting spaces/percent signs without evaluating a shell
command. An exact digest-verified migration retains the original restore data,
refuses administrator changes/unmanaged wrappers and rolls back on failure.

All **18 startup tests passed on the Pi**, including a real `/bin/sh` execution
matching Xsession word splitting, migration, idempotence, restore and failure
rollback. The fixed system session entry and wrapper were applied successfully.
The complete local backend suite passed **246 tests with six Windows/platform
skips** (including four additional OTA recovery tests).

The owner reported switching the Pi off during the second reboot check. After
power was restored, the fixed session booted automatically: labwc used our
private configuration, the launcher ran with `--boot-session`, exactly one
native process ran from the new checkout, and the backend reported
**uiReady=true**. The boot ID differed from the pre-test ID. Original recording
settings were restored through the API, and all 13 original preferences and eight
recordings again matched their backup hashes. A physical display screenshot was
saved privately on the Pi. No complete physical power-on video was captured,
so absence of every firmware/login flash remains unverified.

## Published-command retry

After publishing `8cdfbb7626e02dcd051e10b1bb9820fbe33b0a4b`, we reran the exact
README `curl | bash` command on the reference Pi. The previously deployed local
patch was saved privately, then only those owned source modifications were
restored so the bootstrap could fast-forward a clean `main` checkout itself.
It fetched the published commit, accepted interactive confirmation, executed the
explicit `qt6-wayland` package plan, rebuilt the frontend, passed **35 frontend
tests, 246 backend tests without skips and all six native CTests**, reapplied
startup idempotently and exited **0**. The protected hotspot stayed unchanged.
This repeat used the newly installed Node/build cache; the earlier corrected
full reinstall is the fresh app/runtime/build evidence.

## Freshly flashed image attempt — 25 October 2026

The owner reflashed the reference Pi 5 and requested another public-one-liner
test. No former app checkout, native build, private Node runtime or app state
directory existed on that image. It booted Raspbian Bookworm with an `aarch64`
kernel, but `dpkg --print-architecture` returned **`armhf`** and Python reported
**32-bit** pointers. The installed userspace was therefore the unsupported
32-bit edition, not a fresh 64-bit OS acceptance target.

The exact published `curl | bash` command was executed and exited **1** with
`Use 64-bit Raspberry Pi OS Desktop (Bookworm or Trixie).` This is correct
preflight rejection, not successful installation. No app packages, builds,
startup or rotation changes were applied by this test. Display enumeration
showed `DSI-2`, 720×1280 at normal transform: portrait orientation, requiring
an appropriate quarter-turn for the owner's horizontal mounting. Touch alignment
was not tested remotely. A repeat on a genuinely 64-bit desktop image is pending.

## Fresh 64-bit Trixie installation — 25 October 2026

The next reflash installed 64-bit Raspberry Pi OS Desktop based on Debian 13
Trixie on the Pi 5. `dpkg` reported **arm64** and Python used 64-bit pointers.
Preflight evidence confirmed there was no former app checkout/build, managed
Node installation or private application state. Qt/receiver dependencies were
not already installed. This is a genuine fresh-image test, distinct from the
earlier Bookworm application reinstall and the rejected armhf image.

The exact public one-liner fetched `a31810b7f8dec7c7e14290f783487019e28b833a`
and completed with **exit 0**. It installed the actual OS dependencies, downloaded
and verified the private Node runtime, built the production frontend, passed
**35 frontend tests and 246 backend tests without skips**, compiled the native
receiver against **Qt 6.8.2**, passed **all six CTests** and configured startup.
The runtime dependency audit reported **zero known vulnerabilities**.

The panel initially reported `DSI-2`, 720×1280 and normal transform. With the
owner's authorization, its previously empty user kanshi configuration was backed
up and a 90-degree transform saved for that output. First launch produced an
actual **1280×720** dashboard/taskbar screenshot and **uiReady=true** from the
new native executable running as the ordinary user. Normal Quit stopped both
the app and its owned backend. A controlled reboot then automatically started
the dedicated panel-free car session and the same installed app. Both web views
became ready, landscape rotation persisted, and a saved Contacts taskbar shortcut
and a nondefault automatic-connection preference survived. Original defaults
were restored afterward. Bluetooth and oFono were enabled.

This is logical display/session verification. Physical touch alignment and the
mounting direction still need the owner's confirmation; a remote screenshot
cannot establish where a finger lands. No complete power-on display video was
recorded. Phone projection, microphone, radio, calls and powered-vehicle OBD
were not exercised by this clean-install acceptance test.

### SSH hotspot authentication failure and repair

The first successful full install reported that car-hotspot preparation was
unavailable. The hardware/regulatory checks passed, but NetworkManager returned
**Settings.PermissionDenied: Insufficient privileges** when an SSH session tried
to create its user-only profile without a terminal authentication agent. After
reboot, verifying the saved profile's secret had the same authorization gap.

The provisioning adapter now registers a temporary `pkttyagent` for its own
process around profile creation, secret verification and rollback deletion.
It reads the controlling terminal even under `curl | bash`, preserves existing
agents with `--fallback`, waits for registration and terminates/reaps its owned
agent on success, failure or timeout. The normal system policy/password prompt
authorizes the operation; no Polkit policy is installed or relaxed, the provisioning process
stays unprivileged, and credentials are never arguments or stored application input.
Authenticated D-Bus calls allow at most 120 seconds; other calls keep 15 seconds.
Missing terminal/agent retains normal noninteractive authorization behavior.

On the real Pi, the corrected path verified the existing inactive car profile,
created a separate inactive test profile, matched its secret and deleted it by
its exact UUID. Active connections were identical before/after; the test profile
and terminal agent were gone at completion. The production hotspot remains
protected, user-restricted and **disabled** until explicitly enabled in the app.
All **15 hotspot tests passed on the Pi**, including real child-process cleanup
after failure and registration timeout. The complete patched suite passed
**250 backend tests**; Windows skips its eight POSIX/platform checks.

### Published repair retest

After publishing `51e0f57fddb6126666de8f7786322bd48fe04c60`, the Pi's two owned
local patch files were backed up and compared with that published source. The
exact public one-liner then fast-forwarded a clean checkout itself and repeated
installation. It passed **35 frontend tests, 250 backend tests without skips and
all six native CTests**, displayed the normal terminal authorization prompt,
verified the existing inactive hotspot with `changed: false`, emitted **no hotspot
preparation warning** and finished with **exit 0**. The final native app was
restarted successfully with UI readiness and original default preferences.
This repeat reused the build/runtime from the genuine fresh-image run above.

## Remaining acceptance

- [x] Reconnect after the second reboot; inspect actual session/app logs and
  verify the new native executable, backend and both web views become ready.
- [x] Restore the owner's original recording preference and recheck all
  preserved preferences/recordings after startup.
- [x] Publish the reviewed installer/session fixes after owner authorization,
  then rerun the exact public piped command against that GitHub revision.
- [x] Test the installer, native launch, landscape persistence and automatic
  boot on a freshly flashed 64-bit Trixie desktop image.
- [ ] Repeat on a freshly flashed 64-bit Bookworm image.
- [ ] Verify first-login phone/audio services and physical touch alignment.
- [ ] Capture the complete physical cold-boot display sequence and recovery.
- [ ] Verify live phone, microphone/radio and powered-vehicle OBD behavior;
  installation/build success alone does not verify those devices.

The repair adds no API route, cloud rule or application privilege. The additional
system wrapper belongs to the existing one-time privileged installer and is
covered by its backup/restore manifest; see [backend rules](backend-rules.md).
