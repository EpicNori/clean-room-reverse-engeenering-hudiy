// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

inline void scaleMicrophonePCM(char* pcm, std::size_t size, int volume, bool muted) {
    if (muted || volume <= 0) { std::memset(pcm, 0, size); return; }
    if (volume >= 100) return;
    for (std::size_t i=0; i+1<size; i+=2) {
        std::int16_t sample;
        std::memcpy(&sample, pcm+i, sizeof(sample));
        sample=static_cast<std::int16_t>(static_cast<int>(sample)*volume/100);
        std::memcpy(pcm+i, &sample, sizeof(sample));
    }
}
