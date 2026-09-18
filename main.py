# main.py
# 移动端 / 跨平台入口：加载 QML，注册桥接对象，启动应用。
#
# 文件加载策略：
#   - Android：应用内文件浏览器，扫描 /storage/emulated/0/Download/quizassistant/
#              需要 MANAGE_EXTERNAL_STORAGE 权限（首次使用引导用户开启）
#   - 桌面：走 QML FileDialog
#
# 拆分说明：所有桥接逻辑已移至 bridge/ 包，本文件只保留 QML 路径探测与 main()。

import os
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from bridge import ControllerBridge
from platform_utils import is_android


QQuickStyle.setStyle("Basic")


def _qml_candidates():
    candidates = []
    candidates.append("qrc:/qml/main.qml")
    candidates.append("assets:/qml/main.qml")

    base = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base, "qml", "main.qml"))
    candidates.append(os.path.join(base, "..", "qml", "main.qml"))
    candidates.append(os.path.join(os.getcwd(), "qml", "main.qml"))

    if is_android():
        try:
            from android import mActivity  # type: ignore
            ctx = mActivity.getApplicationContext()
            files_dir = ctx.getFilesDir().getAbsolutePath()
            candidates.append(os.path.join(files_dir, "qml", "main.qml"))
            candidates.append(os.path.join(files_dir, "app", "qml", "main.qml"))
        except Exception as e:
            print("[QML] android 私有目录探测失败：{}".format(e))

    return candidates


def main():
    app = QGuiApplication(sys.argv)
    app.setApplicationName("智能刷题助手")
    app.setOrganizationName("QuizAssistant")

    engine = QQmlApplicationEngine()
    bridge = ControllerBridge()
    engine.rootContext().setContextProperty("bridge", bridge)

    loaded = False
    for path in _qml_candidates():
        print("[QML] Trying: {}".format(path))

        if path.startswith("qrc:/") or path.startswith("assets:/"):
            engine.load(QUrl(path))
        else:
            if not os.path.exists(path):
                print("[QML] Not found: {}".format(path))
                continue
            engine.load(QUrl.fromLocalFile(path))

        if engine.rootObjects():
            print("[QML] Loaded successfully: {}".format(path))
            loaded = True
            break
        else:
            print("[QML] Load failed: {}".format(path))

    if not loaded:
        print("[QML] No QML file could be loaded", file=sys.stderr)
        sys.exit(-1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
