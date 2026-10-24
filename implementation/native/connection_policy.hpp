// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

class ConnectionPolicy {
public:
    explicit ConnectionPolicy(bool automatic = true) : automatic_(automatic) {}
    void configure(bool automatic) {
        if (automatic != automatic_) {
            automatic_ = automatic;
            manual_ = false;
            if (automatic) paused_ = false;
        }
    }
    void request() { manual_ = true; paused_ = false; }
    void connected() { manual_ = false; }
    void pause() { manual_ = false; paused_ = true; }
    bool allowsConnection() const { return !paused_ && (automatic_ || manual_); }
    bool allowsAutomatic() const { return !paused_ && automatic_; }
private:
    bool automatic_ = true, manual_ = false, paused_ = false;
};
