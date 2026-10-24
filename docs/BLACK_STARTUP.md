# Black startup until Hudiy is ready

Normal startup is intended to be **black boot → black car session → ready Hudiy dashboard and taskbar**. The Raspberry Pi is powered off, so this revision has not yet been built/deployed or cold-boot verified on the actual device.

## What changes

- The guided installer installs a small black Plymouth theme, suppresses normal on-screen kernel/status/logo output and disables the firmware rainbow splash. Root-device, serial-console and display parameters are preserved. Authentication prompts remain visible if requested by Plymouth.
- A separate LightDM entry starts labwc with our private configuration, without the OS wallpaper, desktop icons or panel. The vendor's desktop/session files remain available. The main LightDM configuration and a dedicated drop-in select the car session for existing automatic login; the helper does not change the login user, password or authentication mode.
- Our launcher owns a black background during the car session. The native application has a black window/page background and an opaque startup cover over both views. It waits for successful web loads, fonts, the saved layout and two browser paint frames from **both** dashboard and taskbar, using the current native startup token. A fixed sleep is not used to reveal the app.
- Android Auto can connect in the background during startup, but foreground opening waits until both web views are ready. Notifications also wait. OTA health checks cannot validate a runtime whose interface is still covered/unready.
- After 60 seconds without readiness, Retry loading and Return to desktop become available. The recovery buttons support touch and keyboard. Ctrl+Alt+Shift+Q remains available. Normal Quit, final launcher failure or recovery exit stops only our owned black background and starts the saved ordinary-user desktop startup; Quit does not relaunch Hudiy.

## Settings

**Settings → System → Appearance → Black screen during startup** is On by default and saved in private `projection.json`. It applies on the next application/session start. Off selects the ordinary merged desktop session and disables the native startup cover. Boot verbosity/theme are installed separately and stay quiet until restored with the helper below.

The normal installer includes the setup. `--skip-black-boot` leaves boot theme/session selection unchanged; `--no-autologin` keeps authentication unchanged and registers the car session without selecting it for automatic login. Manual login can still show its normal login screen.

For an existing installation, rebuild/test the native runtime and frontend, quit the running app, then run as the ordinary desktop user:

```sh
python3 implementation/launcher/install_autostart.py --apply
sudo python3 implementation/launcher/install_black_boot.py --apply
```

The required packages are `swaybg`, `plymouth` and `plymouth-themes`, included in the updated guided installer. The system helper is a one-time OS configuration step; OTA never runs sudo, rewrites boot configuration or changes the graphical session.

## Recovery and backups

```sh
# Inspect the plan without changing the system:
python3 implementation/launcher/install_black_boot.py
# Restore the exact saved firmware, command-line and LightDM/session files/theme:
sudo python3 implementation/launcher/install_black_boot.py --restore
```

Backups are stored privately in `/var/lib/hudiy-recreation/black-boot.json`; a restored manifest is retained as `black-boot.restored.json`. Apply is idempotent and refuses a changed target. Restore refuses administrator changes to managed files/theme instead of overwriting them. Failed installation attempts restore the saved files/theme when the theme tool succeeds. Existing user startup and labwc configuration retain timestamped backups. The installer never reboots or restarts the current display manager.

The car session is configured under `~/.config/hudiy-recreation/labwc/`; `desktop-recovery` is the saved ordinary-user startup with car launch entries removed/disabled. Terminal/SSH recovery remains available, and normal console messages can be inspected on tty3. Monitor firmware/OSD and hardware/firmware recovery diagnostics are outside the application cover; a real boot capture is required before claiming the complete power-on sequence is visually black.

## Verification still needed on the Pi

- [ ] Build the updated native executable and run CTest, including `black-startup-gate` and `android-auto-connection-policy`.
- [ ] Record a complete cold boot on the actual display: no desktop/panel, OS logo, login flash, cursor or white web page before Hudiy is painted.
- [ ] Verify the black Plymouth theme/initramfs and the effective LightDM car-session selection on both supported OS images.
- [ ] Test delayed backend/fonts, one failed web view, Retry and Return to desktop, and the emergency Quit shortcut.
- [ ] Test Android Auto automatic opening during a slow boot, startup notifications, and OTA failure/rollback without revealing the desktop between candidates.
- [ ] Verify normal Quit restores the usable desktop once, the Off setting survives restart, and helper restore recovers the previous boot/session configuration.
- [ ] Check display scaling/rotation, touch mapping, policy-agent prompts and multiple attached monitors in the dedicated session.

## References

- [Raspberry Pi boot and splash configuration](https://www.raspberrypi.com/documentation/computers/configuration.html#boot-behaviour)
- [Firmware disable_splash option](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/config_txt/boot.adoc)
- [labwc configuration-directory option](https://labwc.github.io/labwc.1.html)
- [labwc background and autostart guidance](https://labwc.github.io/getting-started.html)
- [LightDM session and login configuration](https://github.com/ubuntu/lightdm/blob/main/data/lightdm.conf)
