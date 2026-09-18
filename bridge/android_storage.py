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

    # ==============================================================
    # Android 原生文件选择器（通过 ACTION_OPEN_DOCUMENT）
    # ==============================================================
    def _init_android_file_picker(self):
        """在 __init__ 中调用，注册 on_activity_result 回调。"""
        try:
            from android import activity
            activity.bind(on_activity_result=self._on_activity_result)
            print("[AndroidFilePicker] on_activity_result bound")
        except Exception as e:
            print("[AndroidFilePicker] bind failed: {}".format(e))

    # 请求码，用于区分我们的文件选择结果
    _FILE_PICK_REQUEST_CODE = 1001

    @Slot()
    def openFilePickerAndroid(self):
        """
        启动 Android 系统文件选择器（ACTION_OPEN_DOCUMENT）。
        结果通过 _on_activity_result 回调返回。
        """
        try:
            from jnius import autoclass, cast
            from android import mActivity

            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")

            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType("application/json")
            # 兜底：有些系统不认 application/json，加上 */* 确保能显示所有文件
            intent.putExtra(Intent.EXTRA_MIME_TYPES, ["application/json", "*/*"])

            current_activity = cast(
                "android.app.Activity", PythonActivity.mActivity
            )
            current_activity.startActivityForResult(
                intent, self._FILE_PICK_REQUEST_CODE
            )
            print("[AndroidFilePicker] ACTION_OPEN_DOCUMENT launched")
        except Exception as e:
            print("[AndroidFilePicker] launch failed: {}".format(e))
            self.errorOccurred.emit(
                "无法打开系统文件选择器：{}\n\n"
                "请确认应用已安装且系统文件管理器可用。".format(e)
            )

    def _on_activity_result(self, request_code, result_code, intent):
        """
        Android onActivityResult 回调。
        通过 activity.bind(on_activity_result=...) 注册。
        """
        if request_code != self._FILE_PICK_REQUEST_CODE:
            return

        # Activity.RESULT_OK = -1
        if result_code != -1:
            print("[AndroidFilePicker] user cancelled")
            return

        try:
            uri = intent.getData()
            if uri is None:
                self.errorOccurred.emit("未获取到文件信息")
                return

            data = self._read_content_uri(uri)
            if data is None:
                self.errorOccurred.emit("无法读取所选文件")
                return

            name = self._get_display_name(uri) or "imported.json"

            # 交给 FileOpsMixin 处理加载
            self._handle_android_import(data, name)
        except Exception as e:
            print("[AndroidFilePicker] onActivityResult failed: {}".format(e))
            self.errorOccurred.emit("读取文件失败：{}".format(e))

    def _read_content_uri(self, uri):
        """从 content:// URI 读取字节数据。"""
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        ByteArrayOutputStream = autoclass("java.io.ByteArrayOutputStream")

        resolver = PythonActivity.mActivity.getContentResolver()
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

    def _get_display_name(self, uri):
        """从 content:// URI 查询显示文件名。"""
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        resolver = PythonActivity.mActivity.getContentResolver()
        cursor = resolver.query(uri, None, None, None, None)
        if cursor is None:
            return None
        try:
            if cursor.moveToFirst():
                idx = cursor.getColumnIndex("_display_name")
                if idx != -1:
                    return cursor.getString(idx)
            return None
        finally:
            cursor.close()

    def _handle_android_import(self, data, name):
        """
        接收 Android 文件选择器返回的字节数据，写入私有目录后加载。
        由 FileOpsMixin 提供具体实现（动态派发）。
        """
        if hasattr(self, "_process_imported_bytes"):
            self._process_imported_bytes(data, name)
        else:
            self.errorOccurred.emit("内部错误：导入处理未初始化")

