// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QLabel>
#include <QFontMetrics>
#include <QJsonObject>
#include <QRegularExpression>
#include <QTimer>
#include <algorithm>

// Application-owned overlay: no new top-level window, HTML, input interception,
// saved phone data or unrestricted style strings from the HTTP service.
class NoticeOverlay final : public QLabel {
public:
    explicit NoticeOverlay(QWidget* parent) : QLabel(parent) {
        setTextFormat(Qt::PlainText); setAlignment(Qt::AlignCenter); setWordWrap(true);
        setAttribute(Qt::WA_TransparentForMouseEvents); hide();
        timer_.setSingleShot(true);
        connect(&timer_, &QTimer::timeout, this, [this] { clear(); kind_.clear(); hide(); });
    }
    bool apply(const QJsonObject& data) {
        const QString kind=data.value("kind").toString();
        static const QRegularExpression color("^#[0-9a-fA-F]{6}$");
        const QString bg=data.value("background").toString(), fg=data.value("foreground").toString();
        if (!color.match(bg).hasMatch() || !color.match(fg).hasMatch()) return false;
        const bool theme=kind=="theme";
        if (!theme && kind!="toast" && kind!="output" && kind!="input" && kind!="track") return false;
        if (!theme) {
            const auto duration=data.value("duration"), message=data.value("message");
            if (!duration.isDouble() || duration.toDouble()!=duration.toInt() || duration.toInt()<1 || duration.toInt()>15 || !message.isString() || message.toString().toUcs4().size()>256) return false;
            if (message.toString().isEmpty()) {
                if (kind_==kind) {timer_.stop(); clear(); kind_.clear(); hide();}
                return true;
            }
            if (kind=="track" && !isHidden() && kind_!="track") return true;
            kind_=kind; setText(message.toString()); timer_.start(duration.toInt()*1000);
        }
        background_=bg; foreground_=fg; place(bottom_);
        if (!theme) {show(); raise();}
        return true;
    }
    void place(int taskbarHeight) {
        bottom_=taskbarHeight;
        const double scale=std::max(0.55, std::min(parentWidget()->width()/1280.,parentWidget()->height()/720.));
        QFont f("Roboto"); f.setPixelSize(qRound(32*scale)); setFont(f);
        const int padding=qRound(20*scale), gap=qRound(40*scale);
        setStyleSheet(QString("QLabel {background:%1; color:%2; border-radius:%3px; padding:%4px %5px;}")
            .arg(background_,foreground_).arg(qRound(12*scale)).arg(padding).arg(qRound(30*scale)));
        const int limit=std::max(1,parentWidget()->width()-24);
        setFixedWidth(std::min({limit,qRound(1050*scale),fontMetrics().horizontalAdvance(text())+qRound(60*scale)}));
        const int h=std::clamp(heightForWidth(width()),qRound(78*scale),std::max(qRound(78*scale),parentWidget()->height()/3));
        setFixedHeight(h);
        move((parentWidget()->width()-width())/2,std::max(0,parentWidget()->height()-bottom_-gap-h));
        if (!isHidden()) raise();
    }
private:
    QTimer timer_; QString kind_, background_="#ffd7ee", foreground_="#69345a"; int bottom_=0;
};
