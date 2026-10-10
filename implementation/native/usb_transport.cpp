// SPDX-License-Identifier: GPL-3.0-or-later
#include "usb_transport.hpp"
#include <QMetaObject>
#include <cstring>

namespace {
const char* const identity[] = {"Android", "Android Open Automotive Protocol", "Android Auto", "1.0", "https://www.android.com/", "hudiy-recreation"};
bool identify(libusb_device_handle* handle) {
    for (int n = 0; n < 6; ++n) {
        const auto size = static_cast<uint16_t>(std::strlen(identity[n]) + 1);
        if (libusb_control_transfer(handle, 0x40, 52, 0, n,
            reinterpret_cast<unsigned char*>(const_cast<char*>(identity[n])), size, 500) != size) return false;
    }
    return libusb_control_transfer(handle, 0x40, 53, 0, 0, nullptr, 0, 500) == 0;
}
}

UsbTransport::UsbTransport(QObject* parent) : ITransport(parent) {
    if (libusb_init(&context_) != 0) context_ = nullptr;
}
UsbTransport::~UsbTransport() { stop(); if (context_) libusb_exit(context_); }

bool UsbTransport::discover() {
    if (!context_ || handle_) return handle_ != nullptr;
    libusb_device** devices = nullptr;
    const auto count = libusb_get_device_list(context_, &devices);
    for (ssize_t i = 0; i < count && !handle_; ++i) {
        libusb_device_descriptor descriptor{};
        if (libusb_get_device_descriptor(devices[i], &descriptor) != 0) continue;
        const bool accessory = descriptor.idVendor == 0x18d1 &&
            descriptor.idProduct >= 0x2d00 && descriptor.idProduct <= 0x2d05;
        libusb_device_handle* candidate = nullptr;
        // Limit AOAP negotiation to known Android manufacturers, excluding hubs.
        const bool phone = descriptor.idVendor == 0x04e8 || descriptor.idVendor == 0x18d1 ||
            descriptor.idVendor == 0x22b8 || descriptor.idVendor == 0x2a70 || descriptor.idVendor == 0x2717;
        if ((!accessory && !phone) || libusb_open(devices[i], &candidate) != 0) continue;
        if (!accessory) {
            unsigned char version[2]{};
            const int result = libusb_control_transfer(candidate, 0xc0, 51, 0, 0, version, 2, 500);
            if (result == 2 && version[0] >= 1) {
                // Android Auto's accessory filter matches these protocol labels.
                // Our product identity is sent separately during service discovery.
                identify(candidate);
            }
            libusb_close(candidate);
            continue; // Device re-enumerates; the next five-second check opens it.
        }
        libusb_config_descriptor* config = nullptr;
        if (libusb_get_active_config_descriptor(devices[i], &config) != 0) {
            libusb_close(candidate); continue;
        }
        for (int n = 0; n < config->bNumInterfaces && !handle_; ++n) {
            for (int a = 0; a < config->interface[n].num_altsetting && !handle_; ++a) {
                const auto& setting = config->interface[n].altsetting[a];
                if (setting.bInterfaceClass != 0xff) continue;
                uint8_t in = 0, out = 0;
                for (int e = 0; e < setting.bNumEndpoints; ++e) {
                    const auto& endpoint = setting.endpoint[e];
                    if ((endpoint.bmAttributes & 3) != LIBUSB_TRANSFER_TYPE_BULK) continue;
                    if (endpoint.bEndpointAddress & 0x80) in = endpoint.bEndpointAddress;
                    else out = endpoint.bEndpointAddress;
                }
                // Never detach another process's kernel driver.
                if (in && out && libusb_claim_interface(candidate, setting.bInterfaceNumber) == 0) {
                    handle_ = candidate; interface_ = setting.bInterfaceNumber; input_ = in; output_ = out;
                }
            }
        }
        libusb_free_config_descriptor(config);
        if (!handle_) libusb_close(candidate);
    }
    if (count >= 0) libusb_free_device_list(devices, 1);
    return handle_ != nullptr;
}
bool UsbTransport::restartAccessory() {
    // Explicit reconnect only: do not reset unrelated devices or choose between phones.
    if (!context_ || handle_ || running_) return false;
    libusb_device** devices = nullptr;
    const auto count = libusb_get_device_list(context_, &devices);
    libusb_device* selected = nullptr;
    int matches = 0;
    for (ssize_t i = 0; i < count; ++i) {
        libusb_device_descriptor descriptor{};
        if (libusb_get_device_descriptor(devices[i], &descriptor) == 0 && descriptor.idVendor == 0x18d1 &&
            (descriptor.idProduct == 0x2d00 || descriptor.idProduct == 0x2d01 ||
             descriptor.idProduct == 0x2d04 || descriptor.idProduct == 0x2d05)) { selected = devices[i]; ++matches; }
    }
    libusb_device_handle* candidate = nullptr;
    bool okay = false;
    if (matches == 1 && libusb_open(selected, &candidate) == 0) {
        okay = identify(candidate);
        if (okay) {
            const int result = libusb_reset_device(candidate);
            okay = result == 0 || result == LIBUSB_ERROR_NO_DEVICE;
        }
        libusb_close(candidate);
    }
    if (count >= 0) libusb_free_device_list(devices, 1);
    return okay;
}
void UsbTransport::start() {
    if (running_ || !handle_) return;
    running_ = true;
    reader_ = std::thread([this] {
        unsigned char bytes[16384];
        while (running_) {
            int transferred = 0;
            const int result = libusb_bulk_transfer(handle_, input_, bytes, sizeof(bytes), &transferred, 250);
            if (transferred > 0) {
                const QByteArray data(reinterpret_cast<char*>(bytes), transferred);
                QMetaObject::invokeMethod(this, [this, data] { if (running_) emit dataReceived(data); }, Qt::QueuedConnection);
            }
            if (result != 0 && result != LIBUSB_ERROR_TIMEOUT) {
                running_ = false;
                QMetaObject::invokeMethod(this, [this] { emit error("USB connection ended"); emit disconnected(); }, Qt::QueuedConnection);
            }
        }
    });
    emit connected();
}
void UsbTransport::write(const QByteArray& data) {
    std::lock_guard<std::mutex> guard(outputMutex_);
    if (!running_ || data.size() > 1024 * 1024) return;
    int offset = 0;
    while (offset < data.size() && running_) {
        int transferred = 0;
        const int result = libusb_bulk_transfer(handle_, output_,
            reinterpret_cast<unsigned char*>(const_cast<char*>(data.constData() + offset)),
            data.size() - offset, &transferred, 1000);
        if (result != 0 || transferred <= 0) {
            emit error(QString("USB write failed (%1)").arg(QString::fromLatin1(libusb_error_name(result))));
            return;
        }
        offset += transferred;
    }
}
void UsbTransport::stop() {
    const bool wasRunning = running_.exchange(false);
    if (reader_.joinable()) reader_.join();
    std::lock_guard<std::mutex> guard(outputMutex_);
    if (handle_) { libusb_release_interface(handle_, interface_); libusb_close(handle_); handle_ = nullptr; }
    if (wasRunning) emit disconnected();
}
