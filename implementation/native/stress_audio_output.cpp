// SPDX-License-Identifier: GPL-3.0-or-later
#include "audio_output.hpp"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <iostream>

// Explicit opt-in integration probe: synthetic silence to a named null sink.
// Not a default CTest: it must never select a user's real audio output.
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);
    if (argc!=3 || (QByteArray(argv[1])!="old" && QByteArray(argv[1])!="worker")) return 2;
    QAudioDevice device;
    for (const auto& candidate:QMediaDevices::audioOutputs())
        if (candidate.id()==QByteArray(argv[2])) device=candidate;
    if (device.isNull() || (device.id()!="auto_null" && !device.id().startsWith("hudiy_audio_probe_"))) {
        std::cerr<<"Select auto_null or an explicitly created hudiy_audio_probe_ null sink\n"; return 3;
    }
    const bool old=QByteArray(argv[1])=="old";
    ProjectionAudio worker(device);
    QAudioFormat format; format.setSampleRate(48000); format.setChannelCount(2); format.setSampleFormat(QAudioFormat::Int16);
    QAudioSink sink(device,format);
    sink.setBufferSize(format.bytesForDuration(100000));
    QIODevice* output=nullptr; QByteArray pending; quint64 written=0,dropped=0; qint64 highWater=0;
    if (old) output=sink.start(); else worker.start(0);
    QElapsedTimer wall; wall.start();
    qint64 producedFrames=0,lastDrain=0,maxDrainGap=0;
    QTimer source,drain,stall;
    auto feedOld=[&] {
        const auto now=wall.elapsed(); maxDrainGap=qMax(maxDrainGap,now-lastDrain); lastDrain=now;
        if (!output || pending.isEmpty()) return;
        const auto amount=qMin<qint64>(sink.bytesFree(),pending.size());
        if (amount>0) {const auto count=output->write(pending.constData(),amount); if (count>0) {written+=count;pending.remove(0,count);}}
    };
    QObject::connect(&drain,&QTimer::timeout,&app,feedOld);
    if (old) drain.start(10);
    QObject::connect(&source,&QTimer::timeout,&app,[&] {
        const qint64 frames=wall.elapsed()*48;
        const QByteArray packet((frames-producedFrames)*4,'\0'); producedFrames=frames;
        if (old) {
            feedOld();
            if (pending.size()+packet.size()>192000) {dropped+=pending.size()+packet.size();pending.clear();}
            else pending.append(packet);
            highWater=qMax<qint64>(highWater,pending.size()); feedOld();
        } else worker.enqueue(0,packet);
    });
    source.setTimerType(Qt::PreciseTimer); source.start(5);
    QObject::connect(&stall,&QTimer::timeout,&app,[] { QThread::msleep(120); });
    stall.start(700);
    QTimer::singleShot(30000,&app,[&] {
        source.stop(); stall.stop();
        QTimer::singleShot(1500,&app,[&] {
            auto snapshot=worker.snapshot(); const auto& c=snapshot.channel[0];
            const auto actualWritten=old ? written : c.written, actualDropped=old ? dropped : c.dropped;
            const auto queued=old ? pending.size() : c.pending;
            const qint64 received=producedFrames*4;
            std::cout<<QJsonDocument(QJsonObject{{"mode",old ? "old" : "worker"},{"receivedBytes",received},
                {"writtenBytes",qint64(actualWritten)},{"droppedBytes",qint64(actualDropped)},
                {"queuedBytes",queued},{"highWaterBytes",old ? highWater : c.highWater},
                {"maximumFeedGapMs",old ? maxDrainGap : snapshot.maximumFeedGapMs},
                {"sinkError",old ? int(sink.error()) : c.sinkError}}).toJson(QJsonDocument::Compact).constData()<<std::endl;
            // The old mode is diagnostic. Worker must deliver every synthetic
            // frame despite GUI stalls, without hiding it in a growing queue.
            app.exit(!old && (actualDropped || queued || qint64(actualWritten)!=received) ? 1 : 0);
        });
    });
    return app.exec();
}
