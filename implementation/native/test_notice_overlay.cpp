// SPDX-License-Identifier: GPL-3.0-or-later
#include "notice_overlay.hpp"
#include <QApplication>
#include <QEventLoop>
#include <iostream>
#include <cstdlib>

int main(int argc,char** argv) {
    QApplication app(argc,argv); QWidget root; root.resize(1280,720); root.show();
    NoticeOverlay notice(&root);
    auto require=[](bool valid) { if (!valid) {std::cerr<<"Overlay assertion failed\n"; std::exit(1);} };
    QJsonObject data{{"kind","output"},{"message","Volume 80"},{"duration",1},{"background","#123456"},{"foreground","#abcdef"}};
    require(notice.apply(data)); require(!notice.isHidden());
    require(notice.textFormat()==Qt::PlainText && notice.testAttribute(Qt::WA_TransparentForMouseEvents));
    notice.place(81); require(notice.geometry().bottom()<639);
    auto bad=data; bad["background"]="red; image:url(file:///etc/passwd)"; require(!notice.apply(bad));
    bad=data; bad["duration"]=1.2; require(!notice.apply(bad));
    bad=data; bad["message"]=QString(257,'a'); require(!notice.apply(bad));
    auto track=data; track["kind"]="track"; track["message"]="Song"; require(notice.apply(track)); require(notice.text()=="Volume 80");
    require(notice.apply({{"kind","theme"},{"background","#654321"},{"foreground","#fedcba"}}));
    require(notice.styleSheet().contains("#654321") && notice.text()=="Volume 80");
    QEventLoop wait; QTimer::singleShot(1200,&wait,&QEventLoop::quit); wait.exec(); require(notice.isHidden() && notice.text().isEmpty());
    data["message"]="<b>Literal</b>"; require(notice.apply(data)); require(notice.text()=="<b>Literal</b>");
    root.resize(360,240); notice.place(56); require(root.rect().contains(notice.geometry()));
    track["message"]=""; require(notice.apply(track)); require(!notice.isHidden());
    data["message"]=""; require(notice.apply(data)); require(notice.isHidden());
    std::cout<<"Native overlay bounds, timeout, priority, plain text and theme passed\n";
}
