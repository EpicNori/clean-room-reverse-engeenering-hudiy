"""Fullscreen Qt WebEngine application; no browser toolbar or desktop chrome."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    try:
        from PyQt6.QtCore import Qt,QUrl,QTimer
        from PyQt6.QtGui import QKeySequence,QShortcut
        from PyQt6.QtWidgets import QApplication,QMainWindow
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile
    except ImportError:
        sys.exit('Install python3-pyqt6 and python3-pyqt6.qtwebengine from Raspberry Pi OS packages.')
    service=None
    url='http://127.0.0.1:8766/'
    def healthy():
        try:
            with urllib.request.urlopen(url+'api/status',timeout=1) as r:return r.status==200
        except OSError:return False
    if not healthy():
        service=subprocess.Popen([sys.executable,str(ROOT/'service'/'server.py')],cwd=ROOT)
        for _ in range(40):
            if healthy():break
            if service.poll() is not None:sys.exit('Dashboard service could not start')
            time.sleep(.1)
        else:
            service.terminate()
            sys.exit('Dashboard service did not become ready')
    app=QApplication(sys.argv)
    app.setApplicationName('hudiy-recreation')
    app.setDesktopFileName('hudiy-recreation')
    window=QMainWindow()
    window.setWindowTitle('Hudiy recreation')
    window.resize(1280,720)
    window.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint)
    profile=QWebEngineProfile('hudiy-recreation',window)
    profile.setPersistentStoragePath(str(Path.home()/'.local/share/hudiy-recreation/web'))
    class LocalPage(QWebEnginePage):
        def acceptNavigationRequest(self,target,kind,is_main):
            return target.scheme()=='http' and target.host()=='127.0.0.1' and target.port()==8766
    view=QWebEngineView(window)
    page=LocalPage(profile,view)
    view.setPage(page)
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    window.setCentralWidget(view)
    shortcut=QShortcut(QKeySequence('Ctrl+Alt+Shift+Q'),window)
    shortcut.activated.connect(app.quit)
    window.showFullScreen()
    QTimer.singleShot(1000,window.showFullScreen)
    QTimer.singleShot(2000,lambda:print('Window geometry:',window.geometry().getRect(),'fullscreen:',window.isFullScreen(),flush=True))
    view.setUrl(QUrl(url))
    try:return app.exec()
    finally:
        if service:
            service.terminate()
            try:service.wait(timeout=5)
            except subprocess.TimeoutExpired:service.kill()
if __name__=='__main__':sys.exit(main())
