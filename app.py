"""Portable Qt Quick shell; the same local CLI controls GUI and headless hosts."""
import sys,argparse
from pathlib import Path
ROOT=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
ASSETS=Path(getattr(sys,'_MEIPASS',ROOT))
if not getattr(sys,'frozen',False):sys.path.insert(0,str(ROOT/'lib'))
from PySide6.QtCore import QTimer,QUrl,QLocale
from PySide6.QtGui import QIcon,QPixmap,QPainter,QColor,QPen,QAction
from PySide6.QtWidgets import QApplication,QSystemTrayIcon,QMenu,QMessageBox
from PySide6.QtQml import QQmlApplicationEngine,qmlRegisterType
from PySide6.QtQuickControls2 import QQuickStyle
from settings import save_json


def app_icon():
    pix=QPixmap(64,64);pix.fill(QColor('transparent'));p=QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing);p.setBrush(QColor('#197b69'));p.setPen(QColor('#197b69'));p.drawRoundedRect(2,2,60,60,14,14)
    p.setPen(QPen(QColor('white'),5))
    for x,top,bottom in ((18,25,39),(27,15,49),(37,21,43),(46,27,37)):p.drawLine(x,top,x,bottom)
    p.end();return QIcon(pix)


def create_window(app,directory):
    # QApplication establishes the GUI thread's STA before SoundCard imports.
    # Audio workers initialize their own MTA. Native file dialogs require STA.
    from ui_model import Panel,AudioPlot
    qmlRegisterType(AudioPlot,'DualTone',1,0,'AudioPlot')
    panel=Panel(directory,app);qml=QQmlApplicationEngine()
    qml.rootContext().setContextProperty('panel',panel)
    qml.load(QUrl.fromLocalFile(str(ASSETS/'ui'/'Main.qml')))
    if not qml.rootObjects():panel.close();raise RuntimeError('界面加载失败，请检查安装目录。')
    window=qml.rootObjects()[0];app.aboutToQuit.connect(panel.close)
    return panel,qml,window


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',type=Path,default=ROOT/'data')
    parser.add_argument('--start-audio',action='store_true');parser.add_argument('--screenshot',type=Path)
    parser.add_argument('--qa-report',type=Path);parser.add_argument('--quit-after',type=float)
    parser.add_argument('--details',action='store_true')
    args=parser.parse_args()
    QQuickStyle.setStyle('FluentWinUI3');QLocale.setDefault(QLocale.c())
    app=QApplication(sys.argv[:1]);app.setApplicationName('DualTone');app.setWindowIcon(app_icon())
    try:panel,qml,window=create_window(app,args.data_dir)
    except RuntimeError as exc:QMessageBox.information(None,'DualTone',str(exc));return 1
    if args.details:window.setProperty('details',True)
    tray=QSystemTrayIcon(app.windowIcon(),app);tray.setToolTip('DualTone')
    menu=QMenu()
    def show():window.show();window.raise_();window.requestActivate()
    for title,fn in [('打开 DualTone',show),('开始 / 停止补声',panel.toggle),('静音 / 恢复补声',panel.toggleMute),('退出',panel.control_close)]:
        action=QAction(title,menu);action.triggered.connect(fn);menu.addAction(action)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason:show() if reason in (QSystemTrayIcon.Trigger,QSystemTrayIcon.DoubleClick) else None)
    if QSystemTrayIcon.isSystemTrayAvailable():tray.show();window.setProperty('trayAvailable',True)
    if args.start_audio:QTimer.singleShot(500,panel.control_start)
    if args.screenshot:
        def shot():
            args.screenshot.parent.mkdir(parents=True,exist_ok=True);window.grabWindow().save(str(args.screenshot))
            if args.details:
                for view in app.allWindows():
                    if view.objectName()=='editorWindow':view.grabWindow().save(str(args.screenshot.with_stem(args.screenshot.stem+'-details')))
        QTimer.singleShot(1500,shot)
    if args.quit_after:
        def finish():
            if args.qa_report:save_json(args.qa_report,dict(settings=panel.control_get(),status=panel.engine.status.copy(),save_issue=panel.error))
            panel.control_close()
        QTimer.singleShot(int(args.quit_after*1000),finish)
    return app.exec()

if __name__=='__main__':sys.exit(main())
