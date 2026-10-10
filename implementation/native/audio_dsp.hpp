// SPDX-License-Identifier: GPL-3.0-or-later
// Independently implemented peaking EQ; coefficient reference:
// https://www.w3.org/TR/audio-eq-cookbook/ (peaking EQ, Q = 1.4).
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>

class AudioDsp {
    struct Biquad {
        std::array<double,5> coefficients{1,0,0,0,0}, target{1,0,0,0,0};
        std::array<double,2> z1{}, z2{};
        int remaining = 0;
        double sample(double input, int channel) {
            const auto& c = coefficients;
            const double output = c[0]*input + z1[channel];
            z1[channel] = c[1]*input - c[3]*output + z2[channel];
            z2[channel] = c[2]*input - c[4]*output;
            if (!std::isfinite(output)) { z1[channel]=z2[channel]=0; return 0; }
            return output;
        }
        void advance() {
            if (!remaining) return;
            for (std::size_t i=0;i<5;++i) coefficients[i]+=(target[i]-coefficients[i])/remaining;
            --remaining;
        }
    };
    inline static constexpr std::array<double,15> frequencies{
        25,40,63,100,160,250,400,630,1000,1600,2500,4000,6300,10000,16000};
    std::array<Biquad,15> filters_{};
    std::array<double,15> gains_{};
    int rate_=48000, channels_=2, balance_=0, ramp_=0;
    double currentBalance_=0;
    std::vector<unsigned char> remainder_;
    void coefficients(bool smooth) {
        for (std::size_t i=0;i<filters_.size();++i) {
            auto& f=filters_[i];
            if (frequencies[i]>=rate_*0.49 || gains_[i]==0) f.target={1,0,0,0,0};
            else {
                const double angle=2*3.14159265358979323846*frequencies[i]/rate_;
                const double alpha=std::sin(angle)/(2*1.4), cosine=std::cos(angle);
                const double amplitude=std::pow(10,gains_[i]/40), divisor=1+alpha/amplitude;
                f.target={(1+alpha*amplitude)/divisor,-2*cosine/divisor,
                    (1-alpha*amplitude)/divisor,-2*cosine/divisor,(1-alpha/amplitude)/divisor};
            }
            f.remaining=smooth ? rate_*15/1000 : 0;
            if (!smooth) f.coefficients=f.target;
        }
    }
public:
    void reset(int rate, int channels) {
        if ((rate!=16000 && rate!=48000) || (channels!=1 && channels!=2))
            throw std::invalid_argument("Unsupported projection PCM format");
        rate_=rate; channels_=channels; remainder_.clear();
        filters_={}; currentBalance_=balance_/100.0; ramp_=0; coefficients(false);
    }
    void configure(const std::array<double,15>& gains, int balance) {
        if (balance<-100 || balance>100) throw std::invalid_argument("Invalid balance");
        for (double gain:gains) if (!std::isfinite(gain) || gain<-12 || gain>12)
            throw std::invalid_argument("Invalid equalizer gain");
        gains_=gains; balance_=balance; coefficients(true); ramp_=rate_*15/1000;
    }
    std::vector<unsigned char> process(const unsigned char* data, std::size_t size) {
        if (size>1024*1024 || (size && !data)) throw std::invalid_argument("Invalid PCM payload");
        if (size) remainder_.insert(remainder_.end(),data,data+size);
        const std::size_t frameBytes=channels_*2, length=remainder_.size()/frameBytes*frameBytes;
        std::vector<unsigned char> output(length);
        for (std::size_t offset=0;offset<length;offset+=frameBytes) {
            for (auto& filter:filters_) filter.advance();
            if (ramp_) {currentBalance_+=(balance_/100.0-currentBalance_)/ramp_; --ramp_;}
            for (int channel=0;channel<channels_;++channel) {
                const auto index=offset+channel*2;
                const int raw=int(remainder_[index])+(int(remainder_[index+1])<<8);
                double sample=raw>=32768 ? raw-65536 : raw;
                for (auto& filter:filters_) sample=filter.sample(sample,channel);
                if (channels_==2) sample*=channel==0 ? 1-std::max(0.0,currentBalance_) : 1+std::min(0.0,currentBalance_);
                const int bounded=static_cast<int>(std::lround(std::clamp(sample,-32768.0,32767.0)));
                const auto bits=static_cast<std::uint16_t>(bounded);
                output[index]=bits&255; output[index+1]=bits>>8;
            }
        }
        remainder_.erase(remainder_.begin(),remainder_.begin()+length);
        return output;
    }
};
