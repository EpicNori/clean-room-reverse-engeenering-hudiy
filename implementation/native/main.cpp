// SPDX-License-Identifier: GPL-3.0-or-later
// Protocol channel construction is adapted from OpenAuto Prodigy's
// ServiceDiscoveryBuilder.cpp. See THIRD_PARTY.md for the pinned source.
#include "usb_transport.hpp"
#include "connection_policy.hpp"
#include "startup_gate.hpp"
#include "microphone_pcm.hpp"
#include <QRegularExpression>
#include <QUuid>
#include <QLabel>
#include <QPalette>
#include <QPushButton>
#include "audio_output.hpp"
#include "notice_overlay.hpp"
#include <QApplication>
#include <QAudioSink>
#include <QAudioSource>
#include <QDateTime>
#include <QElapsedTimer>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QImageReader>
#include <QBuffer>
#include <QBluetoothLocalDevice>
#include <QLocalServer>
#include <QLocalSocket>
#include <QLockFile>
#include <QLoggingCategory>
#include <QMediaDevices>
#include <QMouseEvent>
#include <QPainter>
#include <QProcess>
#include <QSaveFile>
#include <QScreen>
#include <QShortcut>
#include <QTimer>
#include <QTouchEvent>
#include <QStackedWidget>
#include <QTcpServer>
#include <QVBoxLayout>
#include <QWebEnginePage>
#include <QWebEngineProfile>
#include <QWebEngineView>
#include <cstring>
#include <csignal>
#include <oaa/Session/AASession.hpp>
#include <oaa/Transport/TCPTransport.hpp>
#include <oaa/HU/Handlers/VideoChannelHandler.hpp>
#include <oaa/HU/Handlers/AudioChannelHandler.hpp>
#include <oaa/HU/Handlers/AVInputChannelHandler.hpp>
#include <oaa/HU/Handlers/InputChannelHandler.hpp>
#include <oaa/HU/Handlers/SensorChannelHandler.hpp>
#include <oaa/HU/Handlers/MediaStatusChannelHandler.hpp>
#include <oaa/HU/Handlers/NavigationChannelHandler.hpp>
#include <oaa/HU/Handlers/PhoneStatusChannelHandler.hpp>
#include <oaa/HU/Handlers/BluetoothChannelHandler.hpp>
#include <oaa/HU/Handlers/WiFiChannelHandler.hpp>
#include <oaa/bluetooth/BluetoothPairingMethodEnum.pb.h>
#include <oaa/bluetooth/BluetoothPairingRequestMessage.pb.h>
#include <oaa/control/ChannelDescriptorData.pb.h>
#include <oaa/av/MediaCodecTypeEnum.pb.h>
#include <oaa/audio/AudioTypeEnum.pb.h>
#include <oaa/video/VideoResolutionEnum.pb.h>
#include <oaa/video/VideoFPSEnum.pb.h>
#include <oaa/sensor/SensorTypeEnum.pb.h>
#include <oaa/navigation/NavigationTypeEnum.pb.h>
#include <oaa/media/MediaPlaybackStatusMessage.pb.h>
extern "C" {
#include <libavcodec/avcodec.h>
#include <libswscale/swscale.h>
}

namespace {
const QString stateDir = QDir::homePath() + "/.local/share/hudiy-recreation";
const QString socketPath = stateDir + "/native.sock";
volatile std::sig_atomic_t exitSignal = 0;
void requestSignalExit(int) { exitSignal = 1; }
uint64_t timestamp() { return static_cast<uint64_t>(QDateTime::currentMSecsSinceEpoch()) * 1000; }
QJsonObject readObject(const QString& path) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly) || file.size() > 65536) return {};
    return QJsonDocument::fromJson(file.readAll()).object();
}
QAudioFormat audioFormat(int rate, int channels) {
    QAudioFormat format; format.setSampleRate(rate); format.setChannelCount(channels);
    format.setSampleFormat(QAudioFormat::Int16); return format;
}
class LocalPage final : public QWebEnginePage {
public:
    LocalPage(QWebEngineProfile* profile, QObject* parent) : QWebEnginePage(profile, parent) {}
    bool acceptNavigationRequest(const QUrl& url, NavigationType, bool) override {
        return url.scheme() == "http" && url.host() == "127.0.0.1" && url.port() == 8766;
    }
};
class LiveMediaChannel final : public oaa::hu::MediaStatusChannelHandler {
public:
    std::function<void(uint32_t)> position;
    void onMessage(uint16_t messageId, const QByteArray& payload, int offset = 0) override {
        if (offset < 0 || offset > payload.size() || payload.size() > 4*1024*1024) return;
        if (messageId == oaa::MediaStatusMessageId::PLAYBACK_STATUS) {
            oaa::proto::messages::MediaPlaybackStatus status;
            if (status.ParseFromArray(payload.constData()+offset, payload.size()-offset) && status.has_position_seconds() && position)
                position(qMin<uint32_t>(status.position_seconds(),86400));
        }
        oaa::hu::MediaStatusChannelHandler::onMessage(messageId,payload,offset);
    }
};
class PairedBluetoothChannel final : public oaa::hu::BluetoothChannelHandler {
public:
    void onMessage(uint16_t messageId, const QByteArray& payload, int offset = 0) override {
        if (offset < 0 || offset > payload.size() || payload.size() > 4096) return;
        if (messageId == oaa::BluetoothMessageId::PAIRING_REQUEST) {
            oaa::proto::messages::BluetoothPairingRequest request;
            if (!request.ParseFromArray(payload.constData()+offset, payload.size()-offset)) return;
            const QBluetoothAddress address(QString::fromStdString(request.phone_address()));
            QBluetoothLocalDevice adapter;
            if (address.isNull() || !adapter.isValid() || adapter.pairingStatus(address) == QBluetoothLocalDevice::Unpaired) {
                qWarning("Pair the phone in the dashboard before Android Auto Bluetooth setup");
                return;
            }
        }
        oaa::hu::BluetoothChannelHandler::onMessage(messageId,payload,offset);
    }
};
class VideoView final : public QWidget {
public:
    QImage image;
    int margin = 80;
    std::function<void(int, int, int)> touch;
    std::function<void(const QList<oaa::hu::InputChannelHandler::Pointer>&, int, int)> multiTouch;
    explicit VideoView(QWidget* parent) : QWidget(parent) { setAttribute(Qt::WA_OpaquePaintEvent); setAttribute(Qt::WA_AcceptTouchEvents); }
    QRect source() const { return image.rect().adjusted(0, margin/2, 0, -margin/2); }
    void paintEvent(QPaintEvent*) override {
        QPainter painter(this); painter.fillRect(rect(), Qt::black);
        if (!image.isNull()) painter.drawImage(rect(), image, source());
    }
    void pointer(QMouseEvent* event, int action) {
        if (touch && !image.isNull()) touch(
            qBound(0, int(event->position().x() * 1280 / qMax(1, width())), 1279),
            qBound(0, int(event->position().y() * (720-margin) / qMax(1, height())), 719-margin), action);
        event->accept();
    }
    void mousePressEvent(QMouseEvent* event) override { pointer(event, 0); }
    void mouseMoveEvent(QMouseEvent* event) override { if (event->buttons() & Qt::LeftButton) pointer(event, 2); }
    void mouseReleaseEvent(QMouseEvent* event) override { pointer(event, 1); }
    bool event(QEvent* event) override {
        if (event->type() == QEvent::TouchBegin || event->type() == QEvent::TouchUpdate || event->type() == QEvent::TouchEnd) {
            auto* touches = static_cast<QTouchEvent*>(event);
            QList<oaa::hu::InputChannelHandler::Pointer> pointers;
            int action = 2, actionIndex = 0;
            for (const auto& point : touches->points()) {
                if (pointers.size() >= 10) break;
                if (point.state() == QEventPoint::State::Pressed) { action = event->type() == QEvent::TouchBegin ? 0 : 5; actionIndex = pointers.size(); }
                if (point.state() == QEventPoint::State::Released) { action = event->type() == QEvent::TouchEnd ? 1 : 6; actionIndex = pointers.size(); }
                pointers.append({qBound(0,int(point.position().x()*1280/qMax(1,width())),1279),
                    qBound(0,int(point.position().y()*(720-margin)/qMax(1,height())),719-margin),point.id()});
            }
            if (multiTouch && !pointers.isEmpty() && !image.isNull()) multiTouch(pointers,actionIndex,action);
            event->accept(); return true;
        }
        return QWidget::event(event);
    }
};

oaa::SessionConfig capabilities(int margin, const QString& adapterAddress, const QString& wifiBssid) {
    oaa::SessionConfig config;
    config.headUnitName = "coscarOS"; config.manufacturer = "EpicNori";
    config.model = "Independent car software"; config.carModel = "Universal";
    config.carYear = "2026"; config.carSerial = "hudiy-recreation";
    config.swBuild = "standalone-1"; config.swVersion = "1.0";
    auto add = [&](oaa::proto::data::ChannelDescriptor& descriptor) {
        config.channels.append({static_cast<uint8_t>(descriptor.channel_id()),
            QByteArray::fromStdString(descriptor.SerializeAsString())});
    };
    oaa::proto::data::ChannelDescriptor video; video.set_channel_id(3);
    auto* av = video.mutable_av_channel();
    av->set_stream_type(oaa::proto::enums::MediaCodecType::MEDIA_CODEC_VIDEO_H264_BP);
    auto* v = av->add_video_configs();
    v->set_video_resolution(oaa::proto::enums::VideoResolution::VIDEO_1280x720);
    v->set_video_fps(oaa::proto::enums::VideoFPS::_30); v->set_dpi(140);
    v->set_margin_width(0); v->set_margin_height(margin);
    v->set_codec(oaa::proto::enums::MediaCodecType::MEDIA_CODEC_VIDEO_H264_BP); add(video);
    for (int id : {4, 5, 6}) {
        oaa::proto::data::ChannelDescriptor audio; audio.set_channel_id(id);
        auto* channel = audio.mutable_av_channel();
        channel->set_stream_type(oaa::proto::enums::MediaCodecType::MEDIA_CODEC_AUDIO_PCM);
        channel->set_audio_type(id == 4 ? oaa::proto::enums::AudioType::MEDIA :
            id == 5 ? oaa::proto::enums::AudioType::SPEECH : oaa::proto::enums::AudioType::SYSTEM);
        auto* format = channel->add_audio_configs(); format->set_bit_depth(16);
        format->set_sample_rate(id == 6 ? 16000 : 48000); format->set_channel_count(id == 4 ? 2 : 1); add(audio);
    }
    oaa::proto::data::ChannelDescriptor input; input.set_channel_id(1);
    auto* touch = input.mutable_input_channel()->add_touch_screen_configs();
    touch->set_width(1280); touch->set_height(720-margin);
    for (int key : {3, 4, 85, 86, 87, 88, 126, 127, 219, 231}) input.mutable_input_channel()->add_supported_keycodes(key);
    add(input);
    oaa::proto::data::ChannelDescriptor sensor; sensor.set_channel_id(2);
    sensor.mutable_sensor_channel()->add_sensors()->set_sensor_type(oaa::proto::enums::SensorType::NIGHT_DATA); add(sensor);
    // Keep the protocol's audio-input service stable across device changes.
    // Capture requests still return failure when no real microphone is available.
    {
        oaa::proto::data::ChannelDescriptor mic; mic.set_channel_id(7);
        auto* channel = mic.mutable_av_input_channel();
        channel->set_stream_type(oaa::proto::enums::MediaCodecType::MEDIA_CODEC_AUDIO_PCM);
        auto* format = channel->mutable_audio_config(); format->set_sample_rate(16000);
        format->set_bit_depth(16); format->set_channel_count(1); add(mic);
    }
    oaa::proto::data::ChannelDescriptor navigation; navigation.set_channel_id(9);
    auto* nav = navigation.mutable_navigation_channel(); nav->set_minimum_interval_ms(500);
    nav->set_type(oaa::proto::enums::NavigationType::TURN_BY_TURN);
    auto* icon = nav->mutable_image_options(); icon->set_width(64); icon->set_height(64); icon->set_colour_depth_bits(32); add(navigation);
    oaa::proto::data::ChannelDescriptor media; media.set_channel_id(10); media.mutable_media_info_channel(); add(media);
    oaa::proto::data::ChannelDescriptor phone; phone.set_channel_id(11); phone.mutable_phone_status_channel(); add(phone);
    if (!adapterAddress.isEmpty()) {
        oaa::proto::data::ChannelDescriptor bluetooth; bluetooth.set_channel_id(8);
        auto* channel = bluetooth.mutable_bluetooth_channel();
        channel->set_adapter_address(adapterAddress.toStdString());
        channel->add_supported_pairing_methods(oaa::proto::enums::BluetoothPairingMethod::PIN); add(bluetooth);
    }
    if (!wifiBssid.isEmpty()) {
        oaa::proto::data::ChannelDescriptor wifi; wifi.set_channel_id(14);
        wifi.mutable_wifi_channel()->set_bssid(wifiBssid.toStdString()); add(wifi);
    }
    return config;
}
}

class CarRuntime final : public QWidget {
    Q_OBJECT
public:
    explicit CarRuntime(const QString& implementation) {
        setWindowTitle("coscarOS");
        QPalette startupPalette = palette(); startupPalette.setColor(QPalette::Window, Qt::black);
        setPalette(startupPalette); setAutoFillBackground(true);
        setWindowFlags(Qt::Window | Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint);
        if (auto* screen = QGuiApplication::primaryScreen()) resize(screen->size());
        QDir().mkpath(stateDir);
        QFile::setPermissions(stateDir, QFileDevice::ReadOwner | QFileDevice::WriteOwner | QFileDevice::ExeOwner);
        ipc_.setSocketOptions(QLocalServer::UserAccessOption);
        // A launcher lock prevents a second owner; never remove an active socket.
        QLocalServer::removeServer(socketPath);
        if (!ipc_.listen(socketPath)) qFatal("Cannot create private native socket");
        connect(&ipc_, &QLocalServer::newConnection, this, [this] {
            auto* candidate = ipc_.nextPendingConnection();
            if (client_) { candidate->disconnectFromServer(); candidate->deleteLater(); return; }
            client_ = candidate; buffer_.clear();
            connect(client_, &QLocalSocket::readyRead, this, &CarRuntime::commands);
            connect(client_, &QLocalSocket::disconnected, this, [this] { client_->deleteLater(); client_ = nullptr; buffer_.clear(); });
            publish();
        });
        options_ = readObject(stateDir + "/projection.json");
        connectionPolicy_.configure(options_.value("autoConnect").toBool(true));
        profile_ = new QWebEngineProfile("hudiy-recreation", this);
        profile_->setPersistentStoragePath(stateDir + "/web");
        auto web = [&](const QString& mode) {
            auto* view = new QWebEngineView(this);
            view->setPage(new LocalPage(profile_, view));
            view->page()->setBackgroundColor(Qt::black);
            const int surface = mode == "content" ? 0 : 1;
            connect(view, &QWebEngineView::loadStarted, this, [this,surface] { startupGate_.loading(surface); });
            connect(view, &QWebEngineView::loadFinished, this, [this,surface](bool success) { startupGate_.loaded(surface,success); revealStartup(); });
            view->setContextMenuPolicy(Qt::NoContextMenu);
            view->setUrl(QUrl("http://127.0.0.1:8766/?host=" + mode + "&startup=" + startupToken_)); return view;
        };
        stack_ = new QStackedWidget(this); content_ = web("content"); video_ = new VideoView(this);
        stack_->addWidget(content_); stack_->addWidget(video_);
        taskbar_ = web("taskbar");
        auto* layout = new QVBoxLayout(this); layout->setContentsMargins(0,0,0,0); layout->setSpacing(0);
        layout->addWidget(stack_, 1); layout->addWidget(taskbar_);
        notice_ = new NoticeOverlay(this);
        startupCover_ = new QWidget(this);
        startupCover_->setObjectName("startup-cover");
        startupCover_->setStyleSheet("#startup-cover { background: #000; color: #fff; } #startup-cover QLabel { color: #fff; font-size: 24px; } #startup-cover QPushButton { color: #fff; background: #222; padding: 16px; min-height: 48px; font-size: 20px; }");
        auto* recovery = new QVBoxLayout(startupCover_);
        recovery->addStretch();
        startupError_ = new QLabel("coscarOS could not finish loading.", startupCover_);
        startupError_->setWordWrap(true); startupError_->setAlignment(Qt::AlignCenter);
        startupRetry_ = new QPushButton("Retry loading", startupCover_);
        startupDesktop_ = new QPushButton("Return to desktop", startupCover_);
        recovery->addWidget(startupError_); recovery->addWidget(startupRetry_); recovery->addWidget(startupDesktop_); recovery->addStretch();
        startupError_->hide(); startupRetry_->hide(); startupDesktop_->hide();
        connect(startupRetry_, &QPushButton::clicked, this, [this] {
            startupToken_ = QUuid::createUuid().toString(QUuid::Id128); startupGate_ = StartupGate();
            startupError_->hide(); startupRetry_->hide(); startupDesktop_->hide(); startupCover_->setCursor(Qt::BlankCursor);
            content_->setUrl(QUrl("http://127.0.0.1:8766/?host=content&startup=" + startupToken_));
            taskbar_->setUrl(QUrl("http://127.0.0.1:8766/?host=taskbar&startup=" + startupToken_));
            startupTimeout_.start(60000);
        });
        connect(startupDesktop_, &QPushButton::clicked, qApp, &QApplication::quit);
        startupTimeout_.setSingleShot(true);
        connect(&startupTimeout_, &QTimer::timeout, this, [this] {
            if (startupGate_.ready() || !startupCover_->isVisible()) return;
            startupCover_->setCursor(Qt::ArrowCursor); startupError_->show(); startupRetry_->show(); startupDesktop_->show(); startupDesktop_->setFocus();
        });
        startupCover_->setCursor(Qt::BlankCursor);
        startupCover_->setVisible(options_.value("blackStartup").toBool(true));
        startupTimeout_.start(60000);
        video_->touch = [this](int x, int y, int action) {
            oaa::hu::InputChannelHandler::Pointer pointer{x,y,0};
            if (active_) input_.sendTouchIndication(1, &pointer, 0, action, timestamp());
        };
        video_->multiTouch = [this](const QList<oaa::hu::InputChannelHandler::Pointer>& pointers,int index,int action) {
            if (active_) input_.sendTouchIndication(pointers.size(),pointers.constData(),index,action,timestamp());
        };
        codec_ = avcodec_alloc_context3(avcodec_find_decoder(AV_CODEC_ID_H264));
        if (!codec_ || avcodec_open2(codec_, codec_->codec, nullptr) < 0) qFatal("H.264 decoder unavailable");
        codec_->thread_count = 2; frame_ = av_frame_alloc();
        connect(&videoChannel_, &oaa::hu::VideoChannelHandler::videoFrameData, this,
            [this](std::shared_ptr<const QByteArray> data, qint64) { decode(*data); });
        connect(&videoChannel_, &oaa::hu::VideoChannelHandler::handlerError, this, [this](const QString& error) { error_ = error.left(256); publish(); });
        connect(&videoChannel_, &oaa::hu::VideoChannelHandler::setupRequested, this, [](int codec) { qWarning() << "Video setup codec" << codec; });
        connect(&videoChannel_, &oaa::hu::VideoChannelHandler::streamStarted, this, [](int, uint32_t config) { qWarning() << "Video stream config" << config; });
        connect(&videoChannel_, &oaa::hu::VideoChannelHandler::videoFocusChanged, this,
            [this](int focus, bool) { if (focus == 2) showProjection(false); });
        connect(&media_, &oaa::hu::MediaStatusChannelHandler::metadataChanged, this,
            [this](const QString& title, const QString& artist, const QString& album, const QByteArray& art) {
                mediaState_["source"] = "android"; mediaState_["title"] = title.left(512);
                mediaState_["artist"] = artist.left(512); mediaState_["album"] = album.left(512);
                QFile::remove(stateDir + "/native-cover.png");
                mediaState_["coverart"] = false;
                mediaState_["duration"] = "—";
                QBuffer encoded; encoded.setData(art); encoded.open(QIODevice::ReadOnly);
                QImageReader reader(&encoded);
                const auto artSize = reader.size();
                if (art.size() <= 2*1024*1024 && artSize.isValid() && artSize.width() <= 2048 && artSize.height() <= 2048 && !reader.read().isNull()) {
                    QSaveFile file(stateDir + "/native-cover.png");
                    if (file.open(QIODevice::WriteOnly)) {
                        file.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);
                        if (file.write(art) == art.size() && file.commit()) mediaState_["coverart"] = true;
                    }
                }
                mediaState_["coverartVersion"] = ++coverVersion_; publish();
            });
        media_.position = [this](uint32_t seconds) {
            mediaState_["position"] = QString("%1:%2").arg(seconds/60,2,10,QChar('0')).arg(seconds%60,2,10,QChar('0'));
            publish();
        };
        connect(&media_, &oaa::hu::MediaStatusChannelHandler::playbackStateChanged, this,
            [this](int state, const QString& app) { mediaState_["playing"] = state == 2; mediaState_["application"] = app.left(128); publish(); });
        connect(&navigation_, &oaa::hu::NavigationChannelHandler::navigationTurnEvent, this,
            [this](const QString& road, int maneuver, int direction, const QByteArray&, int distance, int unit) {
                navigationState_ = {{"active", true}, {"road", road.left(512)}, {"distance", distance}, {"unit", unit}, {"maneuver", maneuver}, {"direction", direction}}; publish();
            });
        connect(&navigation_, &oaa::hu::NavigationChannelHandler::navigationStateSnapshotChanged, this,
            [this](oaa::hu::NavigationState state) { navigationState_["active"] = state == oaa::hu::NavigationState::Active; publish(); });
        connect(&navigation_, &oaa::hu::NavigationChannelHandler::navigationNotificationChanged, this,
            [this](const oaa::hu::NavigationNotificationSnapshot& value) {
                navigationState_["description"] = (value.hasUpcomingRoad ? value.upcomingRoad : value.actionCues.join(" ")).left(512);
                if (value.hasManeuver) navigationState_["maneuver"] = value.maneuverType;
                publish();
            });
        connect(&navigation_, &oaa::hu::NavigationChannelHandler::navigationPositionChanged, this,
            [this](const oaa::hu::NavigationPositionSnapshot& value) {
                if (value.hasStepDistance) {
                    const auto& distance = value.stepDistance;
                    navigationState_["distance"] = distance.hasDisplayText ? distance.displayText.left(64) : QString();
                    if (distance.hasValue) navigationState_["distanceValue"] = distance.value;
                    if (distance.hasUnit) navigationState_["unit"] = distance.unit;
                }
                if (value.hasCurrentRoad && !navigationState_.contains("description")) navigationState_["description"] = value.currentRoad.left(512);
                publish();
            });
        connect(&phone_, &oaa::hu::PhoneStatusChannelHandler::signalStrengthChanged, this,
            [this](int strength) { signal_ = strength; publish(); });
        for (int i = 0; i < 3; ++i) {
            audio_[i] = new oaa::hu::AudioChannelHandler(4+i, this);
            connect(audio_[i], &oaa::hu::AudioChannelHandler::streamStarted, this, [this,i](int) { startAudio(i); });
            connect(audio_[i], &oaa::hu::AudioChannelHandler::streamStopped, this, [this,i] { stopAudio(i); });
            connect(audio_[i], &oaa::hu::AudioChannelHandler::audioDataReceived, this, [this,i](const QByteArray& bytes, uint64_t) {
                audioOutput_.enqueue(i,bytes);
            });
        }
        connect(&inputDevices_, &QMediaDevices::audioInputsChanged, this, [this] {
            // A selected device disappearing never silently selects another microphone.
            stopMicrophone();
            if (micRequested_) startMicrophone();
            publish();
        });
        mic_.setCaptureController([this](bool open) { return microphone(open); });
        connect(&tcp_, &QTcpServer::newConnection, this, [this] {
            auto* socket = tcp_.nextPendingConnection();
            if (session_ || usbRecoveryRunning_ || !connectionPolicy_.allowsConnection() || preferredTransport_ == "usb") { socket->disconnectFromHost(); socket->deleteLater(); return; }
            auto* transport = new oaa::TCPTransport(this); transport->setSocket(socket);
            socket->setParent(transport); begin(transport, "wifi");
        });
        connect(&check_, &QTimer::timeout, this, &CarRuntime::checkConnection);
        check_.start(5000);
        auto* quit = new QShortcut(QKeySequence("Ctrl+Alt+Shift+Q"), this);
        connect(quit, &QShortcut::activated, qApp, &QApplication::quit);
        environment_ = QProcessEnvironment::systemEnvironment(); environment_.insert("HUDIY_STANDALONE", "1");
        backend_.setProcessEnvironment(environment_); backend_.setWorkingDirectory(implementation);
        backend_.setProcessChannelMode(QProcess::ForwardedChannels);
        backend_.start("/usr/bin/python3", {implementation + "/service/server.py"});
        QTimer::singleShot(1500, this, [this] { content_->reload(); taskbar_->reload(); bindWireless(); });
        showFullScreen(); adjustLayout();
        QTimer::singleShot(1000, this, [this] { showFullScreen(); raise(); });
        QTimer::singleShot(2500, this, [this] {
            qInfo() << "Native window geometry" << geometry() << "fullscreen" << isFullScreen();
        });
    }
    ~CarRuntime() override {
        if (usbRecovery_.joinable()) usbRecovery_.join();
        teardown(); microphone(false);
        for (int i=0; i<3; ++i) stopAudio(i);
        backend_.terminate(); if (!backend_.waitForFinished(4000)) { backend_.kill(); backend_.waitForFinished(2000); }
        // Pages must release their profile before QObject's child destruction.
        delete content_; content_ = nullptr;
        delete taskbar_; taskbar_ = nullptr;
        delete profile_; profile_ = nullptr;
        av_frame_free(&frame_); avcodec_free_context(&codec_); sws_freeContext(scaler_);
    }
protected:
    void resizeEvent(QResizeEvent* event) override { QWidget::resizeEvent(event); adjustLayout(); }
private:
    void revealStartup() {
        if (!startupCover_ || !startupGate_.ready()) return;
        startupTimeout_.stop(); startupCover_->hide();
        if (startupProjectionPending_) showProjection(true);
        if (!pendingNotice_.isEmpty()) { notice_->apply(pendingNotice_); pendingNotice_ = {}; }
        publish();
    }
    void checkConnection() {
        if (!tcp_.isListening()) bindWireless();
        if (!session_ && !usbRecoveryRunning_ && connectionPolicy_.allowsConnection() && preferredTransport_ != "wifi") {
            auto* usb = new UsbTransport(this);
            if (usb->discover()) begin(usb, "usb"); else usb->deleteLater();
        }
        publish();
    }
    void bindWireless() {
        const auto wireless = readObject(stateDir + "/wireless.json");
        const QString ip = wireless.value("ipAddress").toString();
        tcp_.close();
        if (wireless.value("enabled").toBool() && ip == "192.168.12.1") {
            if (!tcp_.listen(QHostAddress(ip), 5277)) error_ = "Car Wi-Fi listener unavailable";
            else if (error_ == "Car Wi-Fi listener unavailable") error_.clear();
        }
        publish();
    }
    void adjustLayout() {
        if (startupCover_) { startupCover_->setGeometry(rect()); if (startupCover_->isVisible()) startupCover_->raise(); }
        if (!taskbar_) return;
        taskbar_->setFixedHeight(qMax(56, qRound(height()*0.1125)));
        taskbar_->setVisible(!visible_ || options_.value("taskbarVisible").toBool(true));
        if (notice_) notice_->place(taskbar_->isHidden() ? 0 : taskbar_->height());
    }
    void showProjection(bool visible) {
        if (visible && guideLease_.isValid() && guideLease_.elapsed() < 30000) return;
        if (visible && options_.value("blackStartup").toBool(true) && !startupGate_.ready()) {
            startupProjectionPending_ = true; return;
        }
        startupProjectionPending_ = false;
        visible_ = visible && active_; stack_->setCurrentWidget(visible_ ? static_cast<QWidget*>(video_) : content_);
        if (session_) videoChannel_.requestVideoFocus(visible_);
        adjustLayout(); publish();
    }
    void begin(oaa::ITransport* transport, const QString& kind) {
        transport_ = transport; transportName_ = kind; error_.clear();
        const int margin = options_.value("taskbarVisible").toBool(true) ? 80 : 0;
        video_->margin = margin; video_->image = {}; frames_ = 0;
        avcodec_flush_buffers(codec_);
        QBluetoothLocalDevice adapter;
        const QString adapterAddress = adapter.isValid() ? adapter.address().toString() : QString();
        const auto wireless = readObject(stateDir + "/wireless.json");
        QFile addressFile("/sys/class/net/wlan0/address");
        QString bssid;
        if (kind == "wifi" && wireless.value("enabled").toBool() && addressFile.open(QIODevice::ReadOnly))
            bssid = QString::fromLatin1(addressFile.read(64)).trimmed().toUpper();
        wifi_ = bssid.isEmpty() ? nullptr : new oaa::hu::WiFiChannelHandler(wireless.value("ssid").toString(),wireless.value("passphrase").toString(),this);

        session_ = new oaa::AASession(transport, capabilities(margin, adapterAddress, bssid), this);
        auto* current = session_;
        connect(session_->controlChannel(), &oaa::ControlChannel::shutdownRequested, this,
            [](int reason) { qWarning() << "Phone requested session shutdown" << reason; });
        connect(session_, &oaa::AASession::channelOpened, this, [](uint8_t channel) { qWarning() << "Car channel opened" << channel; });
        for (auto* handler : QList<oaa::IChannelHandler*>{&input_, &sensor_, &videoChannel_, audio_[0], audio_[1], audio_[2], &mic_, &navigation_, &media_, &phone_}) session_->registerChannel(handler->channelId(), handler);
        if (!adapterAddress.isEmpty()) session_->registerChannel(bluetooth_.channelId(),&bluetooth_);
        if (wifi_) session_->registerChannel(wifi_->channelId(),wifi_);
        connect(session_, &oaa::AASession::stateChanged, this, [this](oaa::SessionState state) {
            if (state == oaa::SessionState::Disconnected) lastDisconnectPhase_ = phase_;
            phase_ = static_cast<int>(state); active_ = state == oaa::SessionState::Active;
            // Numeric lifecycle diagnostics contain no phone identifiers or payloads.
            qWarning() << "Car session phase" << phase_;
            if (active_) {
                const QString mode = options_.value("dayNight").toString("Common");
                sensor_.pushNightMode(mode == "Night" || (mode == "Common" && options_.value("darkMode").toBool()));
                if (options_.value("autostart").toBool() || requested_) showProjection(true);
                requested_ = false;
                connectionPolicy_.connected();
            }
            publish();
        });
        connect(session_, &oaa::AASession::disconnected, this, [this,current](oaa::DisconnectReason reason) {
            if (session_ != current) return;
            if (reason != oaa::DisconnectReason::Normal && reason != oaa::DisconnectReason::UserRequested)
                error_ = "Android Auto disconnected (reason " + QString::number(static_cast<int>(reason)) + ")";
            QTimer::singleShot(0, this, [this,current] { if (session_ == current) { teardown(); publish(); } });
        });
        connect(transport_, &oaa::ITransport::error, this, [this](const QString& error) { error_ = error.left(256); publish(); });
        session_->start();
        // AASession starts its messenger; transport I/O is owned by this host.
        transport_->start();
        publish();
    }
    void teardown() {
        active_ = visible_ = false; phase_ = 0;
        if (session_) { auto* previous = session_; session_ = nullptr; previous->disconnect(this); previous->finalize(); delete previous; }
        if (transport_) { transport_->stop(); transport_->deleteLater(); transport_ = nullptr; }
        if (wifi_) { delete wifi_; wifi_ = nullptr; }
        for (int i=0; i<3; ++i) stopAudio(i);
        microphone(false); stack_->setCurrentWidget(content_); adjustLayout();
        mediaState_ = {}; navigationState_ = {}; signal_ = -1;
        QFile::remove(stateDir + "/native-cover.png");
    }
    void decode(const QByteArray& bytes) {
        if (bytes.isEmpty() || bytes.size() > 4*1024*1024) return;
        AVPacket* packet = av_packet_alloc();
        if (!packet || av_new_packet(packet, bytes.size()) < 0) { av_packet_free(&packet); return; }
        std::memcpy(packet->data, bytes.constData(), bytes.size());
        const int result = avcodec_send_packet(codec_, packet); av_packet_free(&packet);
        if (result < 0 && result != AVERROR(EAGAIN)) return;
        while (avcodec_receive_frame(codec_, frame_) == 0) {
            if (frame_->width <= 0 || frame_->height <= 0 || frame_->width > 1920 || frame_->height > 1080) continue;
            QImage image(frame_->width, frame_->height, QImage::Format_RGB888);
            scaler_ = sws_getCachedContext(scaler_, frame_->width, frame_->height, static_cast<AVPixelFormat>(frame_->format),
                frame_->width, frame_->height, AV_PIX_FMT_RGB24, SWS_FAST_BILINEAR, nullptr, nullptr, nullptr);
            if (!scaler_) continue;
            uint8_t* dest[] = {image.bits(), nullptr, nullptr, nullptr}; int strides[] = {static_cast<int>(image.bytesPerLine()), 0, 0, 0};
            sws_scale(scaler_, frame_->data, frame_->linesize, 0, frame_->height, dest, strides);
            video_->image = image; video_->update(); ++frames_;
        }
    }
    void startAudio(int index) { audioOutput_.start(index); }
    void stopAudio(int index) { audioOutput_.stop(index); }
    static QString inputId(const QAudioDevice& device) {
        return QString::fromLatin1(device.id().toBase64(QByteArray::Base64UrlEncoding | QByteArray::OmitTrailingEquals));
    }
    QAudioDevice selectedInput() const {
        const auto selected=inputSettings_.value("device").toString();
        if (selected=="default") return QMediaDevices::defaultAudioInput();
        for (const auto& device:QMediaDevices::audioInputs()) if (inputId(device)==selected) return device;
        return {};
    }
    void stopMicrophone() {
        if (!micSource_) return;
        micSource_->disconnect(this);
        micSource_->stop(); delete micSource_; micSource_=nullptr;
    }
    bool startMicrophone() {
        inputError_.clear();
        if (!inputConfigured_) {inputError_="Waiting for saved microphone settings"; return false;}
        const auto device=selectedInput(); const auto format=audioFormat(16000,1);
        if (device.isNull()) {inputError_="Selected microphone unavailable"; return false;}
        if (!device.isFormatSupported(format)) {inputError_="Microphone needs 16 kHz mono signed 16-bit capture"; return false;}
        micSource_=new QAudioSource(device,format,this);
        auto* source=micSource_;
        connect(source,&QAudioSource::stateChanged,this,[this,source](QAudio::State state) {
            if (source==micSource_ && state==QAudio::StoppedState && source->error()!=QAudio::NoError)
                inputError_="Microphone capture stopped; check the device";
            publish();
        });
        auto* data=source->start();
        if (!data || source->error()!=QAudio::NoError) {
            inputError_="Could not open microphone"; stopMicrophone(); return false;
        }
        connect(data,&QIODevice::readyRead,this,[this,data,source] {
            if (source!=micSource_ || !micRequested_) return;
            while (data->bytesAvailable()>=640) {
                auto pcm=data->read(640);
                if (pcm.size()!=640) break;
                scaleMicrophonePCM(pcm.data(),pcm.size(),inputSettings_.value("volume").toInt(100),inputSettings_.value("muted").toBool());
                mic_.sendMicData(pcm,timestamp());
            }
        });
        return true;
    }
    bool microphone(bool open) {
        micRequested_=open; stopMicrophone();
        if (!open) {inputError_.clear(); publish(); return true;}
        const bool started=startMicrophone();
        if (!started) micRequested_=false;
        publish(); return started;
    }
    QJsonObject inputState() const {
        QJsonArray devices;
        for (const auto& device:QMediaDevices::audioInputs()) {
            const auto id=inputId(device);
            if (devices.size()>=32) break;
            if (id.isEmpty() || id.size()>256) continue;
            devices.append(QJsonObject{{"id",id},{"name",device.description().left(120)},
                {"isDefault",device.isDefault()},{"supported",device.isFormatSupported(audioFormat(16000,1))}});
        }
        const auto selected=selectedInput();
        QString error=inputError_;
        if (selected.isNull()) error="Selected microphone unavailable";
        else if (!selected.isFormatSupported(audioFormat(16000,1))) error="Microphone needs 16 kHz mono signed 16-bit capture";
        const bool capturing=micSource_ && (micSource_->state()==QAudio::ActiveState || micSource_->state()==QAudio::IdleState) && micSource_->error()==QAudio::NoError;
        return {{"configured",inputConfigured_},{"settings",inputSettings_},{"devices",devices},{"resolvedDevice",selected.isNull()?QString():inputId(selected)},
            {"microphoneAvailable",!selected.isNull() && selected.isFormatSupported(audioFormat(16000,1))},
            {"captureActive",capturing},{"error",error}};
    }
    void commands() {
        buffer_ += client_->readAll();
        if (buffer_.size() > 65536) { client_->disconnectFromServer(); return; }
        int end;
        while ((end = buffer_.indexOf('\n')) >= 0) {
            const auto command = QJsonDocument::fromJson(buffer_.left(end)).object(); buffer_.remove(0,end+1);
            const QString op = command.value("operation").toString();
            if (op == "guide-hold") {
                if (command.value("active").toBool()) { guideLease_.start(); if (visible_) showProjection(false); }
                else guideLease_.invalidate();
            }
            else if (guideLease_.isValid() && guideLease_.elapsed() < 30000 && (op == "route" || op == "resume" || op == "usb" || op == "wifi")) {
                // The guide owns navigation temporarily; a crashed view releases it within 30 seconds.
            }
            else if (op == "startup-ready") {
                if (command.value("token").toString() == startupToken_) {
                    const auto surface = command.value("surface").toString();
                    if (surface == "content" || surface == "taskbar") startupGate_.painted(surface == "content" ? 0 : 1);
                    revealStartup();
                }
            }
            else if (op == "notification") {
                if (startupGate_.ready() || command.value("kind").toString() == "theme") notice_->apply(command);
                else pendingNotice_ = command;
            }
            else if (op == "options") {
                const bool previous = options_.value("taskbarVisible").toBool(true);
                const bool previousAuto = options_.value("autoConnect").toBool(true);
                const bool previousOpen = options_.value("autostart").toBool();
                options_ = command.value("options").toObject();
                connectionPolicy_.configure(options_.value("autoConnect").toBool(true));
                if (previousAuto != options_.value("autoConnect").toBool(true)) {
                    requested_ = false;
                    if (options_.value("autoConnect").toBool(true)) preferredTransport_ = "auto";
                }
                if (!previousOpen && options_.value("autostart").toBool() && active_) showProjection(true);
                const QString mode = options_.value("dayNight").toString("Common");
                sensor_.pushNightMode(mode == "Night" || (mode == "Common" && options_.value("darkMode").toBool()));
                if (previous != options_.value("taskbarVisible").toBool(true) && session_) { session_->stop(); }
                adjustLayout();
            } else if (op=="audio-input") {
                const auto settings=command.value("settings").toObject();
                const auto volume=settings.value("volume"); const auto device=settings.value("device").toString();
                const bool valid=settings.size()==3 && settings.value("device").isString()
                    && QRegularExpression("^[A-Za-z0-9_-]{1,256}$").match(device).hasMatch()
                    && settings.value("muted").isBool() && volume.isDouble() && volume.toDouble()==volume.toInt()
                    && volume.toInt()>=0 && volume.toInt()<=100;
                if (valid) {
                    const bool changed=device!=inputSettings_.value("device").toString();
                    inputSettings_=settings; inputConfigured_=true;
                    if (changed) {stopMicrophone(); inputError_.clear(); if (micRequested_) startMicrophone();}
                }
            } else if (op=="audio-dsp") {
                const auto settings=command.value("settings").toObject();
                const auto bands=settings.value("equalizer").toArray();
                const auto balance=settings.value("balance");
                std::array<double,15> gains{};
                bool valid=bands.size()==15 && balance.isDouble() && balance.toDouble()==balance.toInt() && balance.toInt()>=-100 && balance.toInt()<=100;
                for (int i=0;i<bands.size() && i<15;++i) {
                    gains[i]=bands[i].toDouble();
                    valid=valid && bands[i].isDouble() && std::isfinite(gains[i]) && gains[i]>=-12 && gains[i]<=12;
                }
                if (valid) {audioOutput_.configure(gains,balance.toInt()); audioSettings_=settings;}
                else error_="Invalid projection audio settings";
            } else if (op == "exit") { QTimer::singleShot(150, qApp, &QApplication::quit); }
            else if (op == "quit") { requested_ = false; connectionPolicy_.pause(); showProjection(false); if (session_) session_->stop(); }
            else if (op == "usb" || op == "wifi" || op == "resume") {
                requested_ = true; connectionPolicy_.request();
                if (op != "resume") preferredTransport_ = op;
                else if (!active_) preferredTransport_ = "auto";
                if (active_ && (preferredTransport_ == "auto" || preferredTransport_ == transportName_)) {
                    showProjection(true); requested_ = false; connectionPolicy_.connected();
                }
                else {
                    teardown(); check_.stop(); check_.start(5000);
                    if (preferredTransport_ == "usb" || (op == "resume" && transportName_ == "usb")) {
                        if (!usbRecoveryRunning_ && (!usbRestartCooldown_.isValid() || usbRestartCooldown_.elapsed() >= 15000)) {
                            usbRestartCooldown_.start();
                            if (usbRecovery_.joinable()) usbRecovery_.join();
                            usbRecoveryRunning_ = true;
                            usbRecovery_ = std::thread([this] {
                                UsbTransport reconnect;
                                const bool reset = reconnect.restartAccessory();
                                qWarning() << "USB accessory reconnect" << reset;
                                QMetaObject::invokeMethod(this, [this] {
                                    // Give the phone time to open its accessory endpoint.
                                    QTimer::singleShot(2000, this, [this] {
                                        usbRecoveryRunning_ = false;
                                        checkConnection();
                                    });
                                }, Qt::QueuedConnection);
                            });
                        }
                        QTimer::singleShot(1000, this, &CarRuntime::checkConnection);
                    } else QTimer::singleShot(0, this, &CarRuntime::checkConnection);
                }
            } else if (op == "media-toggle" || op == "media-next" || op == "media-previous") {
                if (active_) { const int code = op == "media-toggle" ? 85 : op == "media-next" ? 87 : 88;
                    input_.sendButtonEvent(code,true,timestamp()); input_.sendButtonEvent(code,false,timestamp()); }
            } else if (op == "wireless-reload") bindWireless();
            else if (op == "route") { route_ = command.value("route").toString(); ++revision_; showProjection(false); }
            publish();
        }
    }
    void publish() {
        if (!client_) return;
        const auto audio=audioOutput_.snapshot();
        qint64 written=0, queued=0, dropped=0; QString audioError; QJsonArray audioChannels;
        for (const auto& c:audio.channel) {
            written+=c.written; queued+=c.pending; dropped+=c.dropped;
            if (!c.error.isEmpty()) audioError=c.error;
            else if (c.overflow && audioError.isEmpty()) audioError="Audio output could not keep up";
            audioChannels.append(QJsonObject{{"active",c.active},{"receivedBytes",qint64(c.received)},
                {"writtenBytes",qint64(c.written)},{"queuedBytes",c.pending},{"droppedBytes",qint64(c.dropped)},
                {"highWaterBytes",c.highWater},{"overflows",qint64(c.overflows)},{"underruns",qint64(c.underruns)},
                {"sinkState",c.sinkState},{"sinkError",c.sinkError}});
        }
        QJsonObject state{{"event","state"}, {"connected",active_}, {"visible",visible_}, {"phase",phase_},
            {"route",route_}, {"revision",revision_}, {"error",error_.isEmpty() ? audioError : error_}, {"transport",transportName_},
            {"frames",static_cast<qint64>(frames_)}, {"audioBytes",written}, {"runtimePid",QCoreApplication::applicationPid()},
            {"lastDisconnectPhase",lastDisconnectPhase_},
            {"connectionAllowed",connectionPolicy_.allowsConnection()},
            {"automaticConnectionAllowed",connectionPolicy_.allowsAutomatic()},
            {"sessionStarting",session_ != nullptr && !active_},
            {"uiReady",startupGate_.ready()},
            {"microphoneAvailable",inputState().value("microphoneAvailable")},
            {"audioInput",inputState()},
            {"audioDSP",audioSettings_},
            {"audioQueuedBytes",queued},
            {"audioDroppedBytes",dropped},
            {"maximumAudioPacket",audio.maximumPacket},
            {"audioChannels",audioChannels},{"maximumAudioFeedGapMs",audio.maximumFeedGapMs},
            {"media",mediaState_}, {"navigation",navigationState_}, {"signal",signal_}, {"wirelessListening",tcp_.isListening()}, {"usbRecoveryRunning",usbRecoveryRunning_},
            {"taskbarVisible",options_.value("taskbarVisible").toBool(true)}};
        if (client_->bytesToWrite() > 65536) { client_->disconnectFromServer(); return; }
        client_->write(QJsonDocument(state).toJson(QJsonDocument::Compact) + '\n');
    }
    QLocalServer ipc_; QLocalSocket* client_ = nullptr; QByteArray buffer_;
    QProcess backend_; QProcessEnvironment environment_;
    QWebEngineProfile* profile_ = nullptr; QWebEngineView *content_ = nullptr, *taskbar_ = nullptr;
    NoticeOverlay* notice_ = nullptr;
    QStackedWidget* stack_ = nullptr; VideoView* video_ = nullptr;
    QTcpServer tcp_; QTimer check_; oaa::AASession* session_ = nullptr; oaa::ITransport* transport_ = nullptr;
    QElapsedTimer usbRestartCooldown_;
    std::thread usbRecovery_;
    bool usbRecoveryRunning_ = false;
    QString preferredTransport_ = "auto";
    oaa::hu::VideoChannelHandler videoChannel_; oaa::hu::InputChannelHandler input_;
    oaa::hu::SensorChannelHandler sensor_; LiveMediaChannel media_;
    oaa::hu::NavigationChannelHandler navigation_; oaa::hu::PhoneStatusChannelHandler phone_;
    PairedBluetoothChannel bluetooth_; oaa::hu::WiFiChannelHandler* wifi_ = nullptr;
    oaa::hu::AVInputChannelHandler mic_; oaa::hu::AudioChannelHandler* audio_[3]{};
    ProjectionAudio audioOutput_; QAudioSource* micSource_ = nullptr; QJsonObject audioSettings_;
    QMediaDevices inputDevices_;
    QJsonObject inputSettings_{{"device","default"},{"volume",100},{"muted",false}};
    QString inputError_; bool micRequested_=false, inputConfigured_=false;
    AVCodecContext* codec_ = nullptr; AVFrame* frame_ = nullptr; SwsContext* scaler_ = nullptr;
    QJsonObject options_, mediaState_, navigationState_;
    QElapsedTimer guideLease_;
    QString route_ = "dashboard", error_, transportName_; int revision_ = 0, phase_ = 0, lastDisconnectPhase_ = 0, signal_ = -1, coverVersion_ = 0;
    QWidget* startupCover_ = nullptr; QLabel* startupError_ = nullptr;
    QPushButton *startupRetry_ = nullptr, *startupDesktop_ = nullptr;
    bool startupProjectionPending_ = false;
    QTimer startupTimeout_; StartupGate startupGate_;
    QString startupToken_ = QUuid::createUuid().toString(QUuid::Id128); QJsonObject pendingNotice_;
    ConnectionPolicy connectionPolicy_;
    bool active_ = false, visible_ = false, requested_ = false;
    uint64_t frames_ = 0;
};

int main(int argc, char** argv) {
    // Protocol info/debug messages may contain phone metadata or raw payloads.
    QLoggingCategory::setFilterRules("*.debug=false\n*.info=false");
    QApplication application(argc, argv);
    application.setApplicationName("hudiy-recreation");
    application.setApplicationDisplayName("coscarOS"); application.setDesktopFileName("hudiy-recreation");
    if (argc != 2 || !QFile::exists(QString::fromLocal8Bit(argv[1]) + "/service/server.py")) {
        qCritical("Pass the implementation directory"); return 2;
    }
    QDir().mkpath(stateDir);
    QLockFile ownerLock(stateDir + "/native.lock");
    if (!ownerLock.tryLock()) { qCritical("The native car runtime is already running"); return 3; }
    CarRuntime runtime(QFileInfo(QString::fromLocal8Bit(argv[1])).absoluteFilePath());
    std::signal(SIGTERM, requestSignalExit);
    std::signal(SIGINT, requestSignalExit);
    QTimer signalCheck;
    QObject::connect(&signalCheck, &QTimer::timeout, &application, [&application] { if (exitSignal) application.quit(); });
    signalCheck.start(100);
    return application.exec();
}
#include "main.moc"
