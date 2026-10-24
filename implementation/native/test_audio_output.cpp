// SPDX-License-Identifier: GPL-3.0-or-later
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "audio_output.hpp"
#include <cassert>
#include <iostream>
int main() {
    projection_audio::Shared shared;
    for (int i=0;i<3;++i) {
        auto& c=shared.channel[i];
        projection_audio::append(shared,i,QByteArray(32,'x'));
        assert(c.input.isEmpty()); // stopped channels cannot accumulate data
        c.active=true;
        const int maximum=projection_audio::capacity(i), frame=projection_audio::frameBytes(i);
        QByteArray expected(maximum,'a'); expected.append(QByteArray(8192,'b'));
        projection_audio::append(shared,i,expected.left(maximum));
        projection_audio::append(shared,i,expected.mid(maximum));
        assert(c.input==expected.right(maximum));
        assert(c.input.size()<=maximum && c.dropped==8192 && c.overflows==1);
        assert(c.discontinuity && c.overflow && c.highWater==maximum);
        c.input.clear(); c.dropped=0;
        // An odd-sized protocol fragment may end inside a stereo sample. Only
        // whole old frames may be removed, preserving channel/sample alignment.
        QByteArray fragmented(maximum+1,'c'); fragmented[frame]='d';
        projection_audio::append(shared,i,fragmented);
        assert(c.dropped==quint64(frame) && c.input==fragmented.mid(frame));
        const auto before=c.input;
        const auto received=c.received;
        projection_audio::append(shared,i,QByteArray(1024*1024+1,'z'));
        assert(c.input==before && c.received==received);
        assert(c.error=="Audio packet exceeds size limit");
        c.input.clear(); c.active=false;
        projection_audio::append(shared,i,QByteArray(64,'x')); assert(c.input.isEmpty());
    }
    bool rejected=false;
    try {projection_audio::append(shared,3,QByteArray());}
    catch (const std::invalid_argument&) {rejected=true;}
    assert(rejected);
    std::cout<<"PASS: bounded media/speech/system queues, minimum frame-aligned eviction, fragmented PCM, stopped channels, packet/channel limits\n";
}
