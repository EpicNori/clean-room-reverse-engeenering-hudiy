# coscarOS branding and upgrade compatibility

coscarOS is the independent project's displayed name and GitHub repository:
[EpicNori/coscarOS](https://github.com/EpicNori/coscarOS). Original Hudiy references describe historical observation/documentation; they are not our brand or an endorsement. Choosing a distinct name does not constitute trademark clearance.

## Existing installations

Settings, taskbar order, contacts, vehicle mappings/logs, Bluetooth pairings and hotspot credentials are preserved. Existing user-selected Bluetooth aliases and SSIDs are not overwritten. Fresh hotspot and adapter fallback labels use coscarOS. New OBD exports use `~/Downloads/coscarOS-OBD-Logs`; old exports remain where they were.

The private `~/.local/share/hudiy-recreation` and `.config/hudiy-recreation` paths, internal `Hudiy` menu key, localStorage keys, native executable/app ID, USB serial, NetworkManager profile and managed startup markers remain stable for compatibility. Do not globally replace these identifiers or delete their data. The installer uses `~/coscarOS` for a new checkout, reuses an existing `~/hudiy-recreation`, and accepts `COSCAROS_INSTALL_DIR` or the legacy `HUDIY_INSTALL_DIR`. It accepts only this project's exact new or legacy HTTPS remote.

## One-time update across the repository rename

The old updater deliberately restricts repository redirects/archive roots. Its existing strict check can reject the renamed repository. Update the baseline source once while the app is quit, then rebuild using the installer; do not bypass the updater's trust checks:

```sh
cd ~/hudiy-recreation # use ~/coscarOS for a fresh installation
git status --short # preserve local changes first
git remote set-url origin https://github.com/EpicNori/coscarOS.git
git pull --ff-only
bash install.sh
```

The renamed updater uses only EpicNori/coscarOS on GitHub/codeload with the same archive, traversal, size and parked activation checks. Already prepared old releases remain rollback candidates. No hostname or radio network is silently changed. The startup helper permits an exact branding-only upgrade of verified managed session/theme files, retains their original restore backups, and refuses administrator changes or a changed launcher path.

## Hardware acceptance still required

- [ ] Cold boot shows coscarOS after a black startup with no desktop flash.
- [ ] Existing paired phone starts USB and wireless projection after the rename without re-pairing.
- [ ] Settings, taskbar order, OBD mappings and recordings survive upgrade/reboot.
- [ ] New GitHub OTA download, activation and rollback work on the Pi.
- [ ] Complete formal clearance of the coscarOS name and distinct visual identity before a public release.
