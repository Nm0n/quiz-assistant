# bridge/android_storage.py
# AndroidStorageMixin：负责 Android 存储权限、目录扫描、content:// URI 读写。
# 该 Mixin 通过 self.errorOccurred / self.infoMessage 动态派发到主类的信号，
# 不直接引用其他 Mixin。

import os

from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from platform_utils import is_android


# 公共扫描目录（Android）
ANDROID_WATCH_DIR = "/storage/emulated/0/Download/quizassistant"


class AndroidStorageMixin:
    """Android 存储 Mixin：权限、目录、URI"""

    # ---------- 信号 ----------
    storagePermissionRequired = Signal()

    # ---------- 初始化钩子 ----------
    def _init_android_storage(self):
        """由主类显式调用，当前无额外状态"""
        pass

    # ==============================================================
    # 平台判断（供 QML 读取）
    # ==============================================================
    @Property(bool, constant=True)
    def isAndroid(self):
        return is_android()

    # ==============================================================
    # 存储权限（Android 11+ MANAGE_EXTERNAL_STORAGE）
    # ==============================================================
    @Slot(result=bool)
    def hasStoragePermission(self):
        if not is_android():
            return True
        try:
            from jnius import autoclass
            Environment = autoclass("android.os.Environment")
            return bool(Environment.isExternalStorageManager())
        except Exception as e:
            print("[hasStoragePermission] failed: {}".format(e))
            return False

    @Slot()
    def openStoragePermissionSettings(self):
        """跳转到本应用的「所有文件访问」权限设置页"""
        if not is_android():
            return
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")
            Uri = autoclass("android.net.Uri")

            activity = PythonActivity.mActivity
            package_name = activity.getPackageName()

            intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
            intent.setData(Uri.parse("package:" + package_name))
            activity.startActivity(intent)
            print("[openStoragePermissionSettings] launched for " + package_name)
        except Exception as e:
            print("[openStoragePermissionSettings] failed: {}".format(e))
            self.errorOccurred.emit(
                "无法打开权限设置页，请手动前往：\n"
                "系统设置 → 应用 → 智能刷题助手 → 权限 → 所有文件访问"
            )

    @Slot(result=bool)
    def ensureWatchDir(self):
        """确保扫描目录存在，返回是否成功"""
        try:
            target = self._get_watch_dir()
            if not os.path.exists(target):
                os.makedirs(target, exist_ok=True)
            return os.path.isdir(target)
        except Exception as e:
            print("[ensureWatchDir] failed: {}".format(e))
            return False

    # ==============================================================
    # 应用专属 JSON 文件目录
    # ==============================================================
    @staticmethod
    def _get_watch_dir():
        """
        返回应用专属题库目录，无需任何运行时权限。
        Android: /data/data/<包名>/files/app/data/quizassistant/
        桌面:   <项目根>/data/quizassistant/
        """
        base = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(base)
        path = os.path.join(project_root, "data", "quizassistant")
        os.makedirs(path, exist_ok=True)
        return path

    @Slot(result=str)
    def getWatchDir(self):
        return self._get_watch_dir()

    @Slot(result="QVariantList")
    def listJsonFiles(self):
        """扫描目录，返回 JSON 文件列表 [{name, path, size, mtime}, ...]"""
        watch_dir = self._get_watch_dir()
        result = []
        try:
            if not os.path.isdir(watch_dir):
                print("[listJsonFiles] dir not exist: {}".format(watch_dir))
                return result
            for name in sorted(os.listdir(watch_dir)):
                if not name.lower().endswith(".json"):
                    continue
                full = os.path.join(watch_dir, name)
                if not os.path.isfile(full):
                    continue
                try:
                    st = os.stat(full)
                    result.append({
                        "name": name,
                        "path": full,
                        "size": int(st.st_size),
                        "mtime": int(st.st_mtime),
                    })
                except OSError:
                    continue
        except Exception as e:
            print("[listJsonFiles] failed: {}".format(e))
        print("[listJsonFiles] dir={} count={}".format(watch_dir, len(result)))
        return result

    @Slot(str)
    def copyToClipboard(self, text):
        try:
            cb = QGuiApplication.clipboard()
            if cb is not None:
                cb.setText(text)
                self.infoMessage.emit("已复制到剪贴板")
        except Exception as e:
            print("[copyToClipboard] failed: {}".format(e))

    # ==============================================================
    # Android content:// URI 读写（由 FileOpsMixin 动态派发调用）
    # ==============================================================
    def _read_android_uri(self, uri_str):
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        Uri = autoclass("android.net.Uri")
        ByteArrayOutputStream = autoclass("java.io.ByteArrayOutputStream")

        uri = Uri.parse(uri_str)
        resolver = activity.getContentResolver()
        stream = resolver.openInputStream(uri)
        if stream is None:
            return None
        try:
            baos = ByteArrayOutputStream()
            buf = bytearray(8192)
            while True:
                n = stream.read(buf)
                if n <= 0:
                    break
                baos.write(buf, 0, n)
            return bytes(baos.toByteArray())
        finally:
            stream.close()

    def _open_android_uri_for_write(self, uri_str):
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        Uri = autoclass("android.net.Uri")

        uri = Uri.parse(uri_str)
        resolver = activity.getContentResolver()
        stream = resolver.openOutputStream(uri)
        if stream is None:
            raise IOError("openOutputStream returned null")

        class _AndroidOutputStream:
            def __init__(self, java_stream):
                self._stream = java_stream

            def write(self, data):
                if isinstance(data, str):
                    data = data.encode("utf-8")
                self._stream.write(data)

            def close(self):
                if self._stream is not None:
                    self._stream.close()
                    self._stream = None

        return _AndroidOutputStream(stream)
