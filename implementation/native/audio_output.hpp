// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "audio_dsp.hpp"
#include <QAudioSink>
#include <QElapsedTimer>
#include <QMediaDevices>
#include <QMutex>
#include <QMutexLocker>
#include <QThread>
#include <QTimer>
#include <memory>

// The GUI may receive PCM in bursts after decoding video. Keep ingress bounded
// and let a separate event loop feed the output throughout GUI stalls.
namespace projection_audio {
inline int rate(int channel) { return channel == 2 ? 16000 : 48000; }
inline int channels(int channel) { return channel == 0 ? 2 : 1; }
inline int frameBytes(int channel) { return channels(channel)*2; }
inline int capacity(int channel) { return rate(channel)*frameBytes(channel); }
struct Channel {
    bool active = false, discontinuity = false, overflow = false;
    quint64 generation = 0, received = 0, written = 0, dropped = 0;
    quint64 overflows = 0, underruns = 0;
    QByteArray input;
    qint64 pending = 0, highWater = 0;
    int sinkState = QAudio::StoppedState, sinkError = QAudio::NoError;
    QString error;
};
struct Shared {
    QMutex mutex;
    std::array<Channel,3> channel;
    std::array<double,15> gains{};
    int balance = 0;
    quint64 settingsVersion = 0;
    qint64 maximumPacket = 0, maximumFeedGapMs = 0;
};

// Caller holds Shared::mutex. Frame-aligned eviction bounds latency without
// throwing away the entire second of already queued audio after a burst.
inline void append(Shared& shared,int index,const QByteArray& bytes) {
    if (index<0 || index>=3) throw std::invalid_argument("Invalid audio channel");
    auto& c=shared.channel[index];
    if (!c.active) return;
    shared.maximumPacket=qMax<qint64>(shared.maximumPacket,bytes.size());
    if (bytes.size()>1024*1024) {c.error="Audio packet exceeds size limit"; return;}
    c.received+=bytes.size(); c.input.append(bytes);
    if (c.input.size()>capacity(index)) {
        const int frame=frameBytes(index);
        const auto excess=(c.input.size()-capacity(index)+frame-1)/frame*frame;
        c.input.remove(0,excess); c.dropped+=excess; ++c.overflows;
        c.discontinuity=true; c.overflow=true;
    }
    c.highWater=qMax<qint64>(c.highWater,c.input.size());
}

class Worker final : public QObject {
public:
    Worker(std::shared_ptr<Shared> shared, const QAudioDevice& output)
        : shared_(std::move(shared)), output_(output) {}
    void initialize() {
        clock_.start();
        timer_ = new QTimer(this);
        timer_->setTimerType(Qt::PreciseTimer);
        connect(timer_, &QTimer::timeout, this, [this] { feed(); });
        timer_->start(5);
    }
    void shutdown() {
        if (timer_) timer_->stop();
        for (int i=0;i<3;++i) close(i);
    }
private:
    struct Output {
        QAudioSink* sink = nullptr;
        QIODevice* device = nullptr;
        AudioDsp dsp;
        QByteArray pending;
        quint64 generation = 0;
        bool active = false;
        bool underrun = false;
        qint64 retryAt = 0;
    };
    void close(int index) {
        auto& o=owned_[index];
        o.device=nullptr; o.pending.clear(); o.underrun=false;
        // Qt 6.4's PulseAudio destructor processes events; remove the pointer
        // before destruction and prevent a nested timer from re-entering feed.
        auto* sink=o.sink; o.sink=nullptr;
        if (sink) { sink->stop(); delete sink; }
    }
    void open(int index) {
        auto& o=owned_[index]; close(index);
        o.dsp.reset(rate(index),channels(index));
        const auto device=output_.isNull() ? QMediaDevices::defaultAudioOutput() : output_;
        QAudioFormat format; format.setSampleRate(rate(index));
        format.setChannelCount(channels(index)); format.setSampleFormat(QAudioFormat::Int16);
        o.retryAt=clock_.elapsed()+5000;
        if (device.isNull() || !device.isFormatSupported(format)) {
            QMutexLocker lock(&shared_->mutex);
            shared_->channel[index].error="Select a compatible audio output";
            shared_->channel[index].sinkState=QAudio::StoppedState;
            shared_->channel[index].sinkError=QAudio::OpenError;
            return;
        }
        o.sink=new QAudioSink(device,format,this);
        o.sink->setBufferSize(format.bytesForDuration(100000));
        o.device=o.sink->start();
    }
    bool drain(int index) {
        auto& o=owned_[index];
        if (!o.device || !o.sink || o.pending.isEmpty()) return false;
        const qint64 amount=qMin<qint64>(o.sink->bytesFree(),o.pending.size());
        if (amount<=0) return false;
        const auto written=o.device->write(o.pending.constData(),amount);
        if (written<=0) return false;
        o.pending.remove(0,written);
        QMutexLocker lock(&shared_->mutex);
        auto& c=shared_->channel[index]; c.written+=written;
        if (c.input.size()<capacity(index)/2) c.overflow=false;
        return true;
    }
    void feed() {
        if (feeding_) return;
        feeding_=true;
        struct Guard { bool& value; ~Guard() {value=false;} } guard{feeding_};
        const auto now=clock_.elapsed();
        {
            QMutexLocker lock(&shared_->mutex);
            if (lastFeed_>=0) shared_->maximumFeedGapMs=qMax(shared_->maximumFeedGapMs,now-lastFeed_);
            lastFeed_=now;
            if (settingsVersion_!=shared_->settingsVersion) {
                for (auto& o:owned_) o.dsp.configure(shared_->gains,shared_->balance);
                settingsVersion_=shared_->settingsVersion;
            }
        }
        for (int i=0;i<3;++i) {
            auto& o=owned_[i]; bool active; quint64 generation;
            {
                QMutexLocker lock(&shared_->mutex);
                active=shared_->channel[i].active; generation=shared_->channel[i].generation;
            }
            if (generation!=o.generation) {
                o.generation=generation; o.active=active;
                if (active) open(i); else close(i);
            }
            if (!active) continue;
            if ((!o.device || (o.sink && o.sink->state()==QAudio::StoppedState)) && now>=o.retryAt) open(i);
            if (o.device && o.sink && o.sink->state()!=QAudio::StoppedState) {
                drain(i);
                for (int attempt=0;attempt<4 && o.pending.isEmpty() && o.sink->bytesFree()>0;++attempt) {
                    QByteArray input; bool discontinuity;
                    {
                        QMutexLocker lock(&shared_->mutex);
                        auto& c=shared_->channel[i];
                        if (!c.active || c.generation!=o.generation) break;
                        // Consume whole frames; fragmented protocol packets stay
                        // joined, including across a partial sink write.
                        const auto length=qMin<qsizetype>(8192,c.input.size())/frameBytes(i)*frameBytes(i);
                        if (!length) break;
                        input=c.input.left(length); c.input.remove(0,length);
                        discontinuity=c.discontinuity; c.discontinuity=false;
                    }
                    if (discontinuity) o.dsp.reset(rate(i),channels(i));
                    auto pcm=o.dsp.process(reinterpret_cast<const unsigned char*>(input.constData()),input.size());
                    o.pending=QByteArray(reinterpret_cast<const char*>(pcm.data()),pcm.size());
                    drain(i);
                }
            }
            QMutexLocker lock(&shared_->mutex);
            auto& c=shared_->channel[i];
            if (c.generation!=o.generation) continue;
            c.pending=o.pending.size();
            if (o.sink) {
                c.sinkState=o.sink->state(); c.sinkError=o.sink->error();
                const bool underrun=c.sinkError==QAudio::UnderrunError;
                if (underrun && !o.underrun) ++c.underruns;
                o.underrun=underrun;
                c.error=c.sinkState==QAudio::StoppedState ? QString("Audio output unavailable") : QString();
            }
        }
    }
    std::shared_ptr<Shared> shared_;
    QAudioDevice output_;
    std::array<Output,3> owned_;
    QTimer* timer_=nullptr;
    QElapsedTimer clock_;
    qint64 lastFeed_=-1;
    quint64 settingsVersion_=0;
    bool feeding_=false;
};
}

class ProjectionAudio final {
public:
    struct Snapshot {
        std::array<projection_audio::Channel,3> channel;
        qint64 maximumPacket=0, maximumFeedGapMs=0;
    };
    explicit ProjectionAudio(const QAudioDevice& output={}) : shared_(std::make_shared<projection_audio::Shared>()) {
        worker_=new projection_audio::Worker(shared_,output);
        worker_->moveToThread(&thread_);
        QObject::connect(&thread_,&QThread::started,worker_,[this] {worker_->initialize();});
        QObject::connect(&thread_,&QThread::finished,worker_,&QObject::deleteLater);
        thread_.setObjectName("projection-audio"); thread_.start();
    }
    ~ProjectionAudio() {
        QMetaObject::invokeMethod(worker_,[this] {worker_->shutdown();},Qt::BlockingQueuedConnection);
        thread_.quit(); thread_.wait();
    }
    ProjectionAudio(const ProjectionAudio&)=delete;
    ProjectionAudio& operator=(const ProjectionAudio&)=delete;
    void start(int index) { change(index,true); }
    void stop(int index) { change(index,false); }
    void configure(const std::array<double,15>& gains,int balance) {
        AudioDsp validator; validator.configure(gains,balance);
        QMutexLocker lock(&shared_->mutex);
        shared_->gains=gains; shared_->balance=balance; ++shared_->settingsVersion;
    }
    void enqueue(int index,const QByteArray& bytes) {
        QMutexLocker lock(&shared_->mutex);
        projection_audio::append(*shared_,index,bytes);
    }
    Snapshot snapshot() const {
        QMutexLocker lock(&shared_->mutex);
        Snapshot result{shared_->channel,shared_->maximumPacket,shared_->maximumFeedGapMs};
        // Diagnostics contain counts and states, never the queued PCM payload.
        for (auto& c:result.channel) {const auto queued=c.input.size(); c.input.clear(); c.pending+=queued;}
        return result;
    }
private:
    void change(int index,bool active) {
        if (index<0 || index>=3) throw std::invalid_argument("Invalid audio channel");
        QMutexLocker lock(&shared_->mutex); auto& c=shared_->channel[index];
        c.active=active; ++c.generation; c.input.clear(); c.pending=0;
        c.discontinuity=false; c.overflow=false; c.error.clear();
        c.sinkState=QAudio::StoppedState; c.sinkError=QAudio::NoError;
    }
    std::shared_ptr<projection_audio::Shared> shared_;
    QThread thread_;
    projection_audio::Worker* worker_;
};
