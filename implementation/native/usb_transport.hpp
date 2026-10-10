// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <oaa/Transport/ITransport.hpp>
#include <QTimer>
#include <libusb.h>
#include <atomic>
#include <mutex>
#include <thread>

class UsbTransport final : public oaa::ITransport {
    Q_OBJECT
public:
    explicit UsbTransport(QObject* parent = nullptr);
    ~UsbTransport() override;
    bool discover();
    bool restartAccessory();
    void start() override;
    void stop() override;
    void write(const QByteArray& data) override;
    bool isConnected() const override { return running_; }
private:
    libusb_context* context_ = nullptr;
    libusb_device_handle* handle_ = nullptr;
    int interface_ = -1;
    uint8_t input_ = 0, output_ = 0;
    std::atomic<bool> running_{false};
    std::thread reader_;
    std::mutex outputMutex_;
};
