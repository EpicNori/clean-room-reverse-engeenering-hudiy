// SPDX-License-Identifier: GPL-3.0-or-later
#include "connection_policy.hpp"
#include <cstdlib>

void require(bool value) { if (!value) std::abort(); }
int main() {
    ConnectionPolicy automatic;
    require(automatic.allowsConnection() && automatic.allowsAutomatic());
    automatic.pause();
    require(!automatic.allowsConnection() && !automatic.allowsAutomatic());
    automatic.configure(true); // Unrelated options/IPC reconnect must preserve Quit.
    require(!automatic.allowsConnection());
    automatic.request();
    require(automatic.allowsConnection() && automatic.allowsAutomatic());
    automatic.configure(false);
    require(!automatic.allowsConnection() && !automatic.allowsAutomatic());
    automatic.request();
    require(automatic.allowsConnection() && !automatic.allowsAutomatic());
    automatic.configure(false); // Manual requests survive other settings saves.
    require(automatic.allowsConnection());
    automatic.pause();
    require(!automatic.allowsConnection());
    automatic.configure(true);
    require(automatic.allowsConnection() && automatic.allowsAutomatic());
    ConnectionPolicy manual(false); // Persisted Off at boot.
    require(!manual.allowsConnection());
    manual.request();
    require(manual.allowsConnection() && !manual.allowsAutomatic());
    manual.connected(); // Off permits one manual session, not future reconnects.
    require(!manual.allowsConnection());
    automatic.connected();
    require(automatic.allowsAutomatic());
}
