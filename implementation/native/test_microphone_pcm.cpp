// SPDX-License-Identifier: GPL-3.0-or-later
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "microphone_pcm.hpp"
#include <array>
#include <cassert>

int main() {
    std::array<std::int16_t,5> samples{{-32768,-1000,0,1000,32767}};
    const auto original=samples;
    scaleMicrophonePCM(reinterpret_cast<char*>(samples.data()),sizeof(samples),100,false);
    assert(samples==original);
    scaleMicrophonePCM(reinterpret_cast<char*>(samples.data()),sizeof(samples),50,false);
    assert((samples==std::array<std::int16_t,5>{{-16384,-500,0,500,16383}}));
    scaleMicrophonePCM(reinterpret_cast<char*>(samples.data()),sizeof(samples),100,true);
    for (auto sample:samples) assert(sample==0);
    samples=original;
    scaleMicrophonePCM(reinterpret_cast<char*>(samples.data()),sizeof(samples),0,false);
    for (auto sample:samples) assert(sample==0);
    std::array<char,5> odd{{1,2,3,4,5}};
    scaleMicrophonePCM(odd.data(),odd.size(),50,false);
    assert(odd.back()==5); // No read/write beyond a complete sample.
    scaleMicrophonePCM(odd.data(),odd.size(),100,true);
    for (auto sample:odd) assert(sample==0);
}
