// SPDX-License-Identifier: GPL-3.0-or-later
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "audio_dsp.hpp"
#include <cassert>
#include <iostream>
#include <limits>

std::vector<unsigned char> tone(double frequency, int rate=48000,int channels=2) {
    std::vector<unsigned char> bytes;
    for(int frame=0;frame<rate;++frame) {
        int sample=std::lround(2000*std::sin(2*3.14159265358979323846*frequency*frame/rate));
        for(int channel=0;channel<channels;++channel) {const auto value=static_cast<std::uint16_t>(sample); bytes.push_back(value&255);bytes.push_back(value>>8);}
    }
    return bytes;
}
double rms(const std::vector<unsigned char>& bytes,int channels=2,int channel=0) {
    double sum=0; std::size_t count=0;
    for(std::size_t i=bytes.size()/2/(channels*2)*(channels*2)+channel*2;i+1<bytes.size();i+=channels*2) {
        int raw=bytes[i]+(int(bytes[i+1])<<8), value=raw>=32768?raw-65536:raw;
        sum+=double(value)*value; ++count;
    }
    return std::sqrt(sum/count);
}
int main() {
    auto input=tone(1000); AudioDsp flat; flat.reset(48000,2);
    assert(flat.process(input.data(),input.size())==input);
    AudioDsp chunked; chunked.reset(48000,2); std::vector<unsigned char> joined;
    for(std::size_t i=0;i<input.size();i+=131) {auto output=chunked.process(input.data()+i,std::min<std::size_t>(131,input.size()-i));joined.insert(joined.end(),output.begin(),output.end());}
    assert(joined==input);
    std::array<double,15> gains{}; gains[8]=6;
    AudioDsp boost; boost.configure(gains,0); boost.reset(48000,2);
    auto raised=boost.process(input.data(),input.size()); assert(rms(raised)/rms(input)>1.98 && rms(raised)/rms(input)<2.01);
    AudioDsp fragmented; fragmented.configure(gains,0); fragmented.reset(48000,2); joined.clear();
    for(std::size_t i=0;i<input.size();i+=4097) {auto output=fragmented.process(input.data()+i,std::min<std::size_t>(4097,input.size()-i));joined.insert(joined.end(),output.begin(),output.end());}
    assert(joined==raised);
    gains[8]=-6; AudioDsp cut; cut.configure(gains,0); cut.reset(48000,2);
    auto lowered=cut.process(input.data(),input.size()); assert(rms(lowered)/rms(input)>0.49 && rms(lowered)/rms(input)<0.51);
    AudioDsp left; left.configure({},-100); left.reset(48000,2);
    auto balanced=left.process(input.data(),input.size()); assert(rms(balanced,2,1)==0); assert(rms(balanced,2,0)==rms(input,2,0));
    AudioDsp right; right.configure({},100); right.reset(48000,2);
    balanced=right.process(input.data(),input.size()); assert(rms(balanced,2,0)==0); assert(rms(balanced,2,1)==rms(input,2,1));
    auto speech=tone(2000,16000,1); AudioDsp mono; mono.configure({},100); mono.reset(16000,1);
    assert(mono.process(speech.data(),speech.size())==speech);
    gains.fill(12); AudioDsp extreme; extreme.configure(gains,0); extreme.reset(48000,2);
    auto saturated=extreme.process(input.data(),input.size()); assert(saturated.size()==input.size()); assert(rms(saturated)>0 && rms(saturated)<=32768);
    gains[0]=std::numeric_limits<double>::quiet_NaN(); bool rejected=false;
    try {extreme.configure(gains,0);} catch(const std::invalid_argument&) {rejected=true;} assert(rejected);
    std::cout<<"PASS: flat identity, split packets, +/-6 dB frequency response, both stereo balance extremes, mono speech, peak bounds, invalid gain rejection\n";
}
