// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <array>

class StartupGate {
public:
    void loading(int surface) { if (valid(surface)) { loaded_[surface] = false; painted_[surface] = false; } }
    void loaded(int surface, bool success) { if (valid(surface)) loaded_[surface] = success; }
    void painted(int surface) { if (valid(surface)) painted_[surface] = true; }
    bool ready() const { return loaded_[0] && loaded_[1] && painted_[0] && painted_[1]; }
private:
    static bool valid(int surface) { return surface >= 0 && surface < 2; }
    std::array<bool, 2> loaded_{{false, false}}, painted_{{false, false}};
};
