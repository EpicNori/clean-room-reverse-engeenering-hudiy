// SPDX-License-Identifier: GPL-3.0-or-later
#include "startup_gate.hpp"
#include <cstdlib>
void require(bool value) { if (!value) std::abort(); }
int main() {
    StartupGate gate;
    require(!gate.ready());
    gate.loaded(0, true); gate.painted(0);
    require(!gate.ready());
    gate.loaded(1, false); gate.painted(1);
    require(!gate.ready());
    gate.loaded(1, true);
    require(gate.ready());
    gate.loading(0);
    require(!gate.ready());
    gate.loaded(0, true);
    require(!gate.ready());
    gate.painted(0);
    require(gate.ready());
    gate.loading(99); gate.loaded(-1, true); gate.painted(4);
    require(gate.ready());
}
