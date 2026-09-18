# bridge/android_storage.py
# Android 存储相关：平台判断、权限、目录扫描、content:// URI 处理。
#
# 本模块只提供"模块级函数"，每个函数第一个参数为 self（静态方法除外，
# 由 controller_bridge.py 用 staticmethod() 包装）。
# 顶层 @Slot / @Property 装饰器保留在各函数定义处，
# 由 controller_bridge.py 通过类属性赋值引入命名空间。

import io
import os
from contextlib import contextmanager

from PySide6.QtCore import QIODevice, Property, QFile, QUrl, Slot
from PySide6.QtGui import QGuiApplication

from platform_utils import is_android


# 公共扫描目录（Android）
ANDROID_WATCH_DIR = "/storage/emulated/0/Download/quizassistant"


# ==============================================================
# 平台判断
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
        target = _get_watch_dir()
        if not os.path.exists(target):
            os.makedirs(target, exist_ok=True)
        return os.path.isdir(target)
    except Exception as e:
        print("[ensureWatchDir] failed: {}".format(e))
        return False


# ==============================================================
# 应用专属 JSON 文件目录
# ==============================================================
def _get_watch_dir():
    """
    Android: /storage/emulated/0/Download/quizassistant/
    桌面:   <项目根>/data/

    本文件位于 <项目根>/bridge/android_storage.py，
    因此两次 dirname 回到项目根。
    """
    if is_android():
        return ANDROID_WATCH_DIR
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "data")
        os.makedirs(path, exist_ok=True)
        return path


@Slot(result=str)
def getWatchDir(self):
    return _get_watch_dir()


@Slot(result="QVariantList")
def listJsonFiles(self):
    """扫描目录，返回 JSON 文件列表 [{name, path, size, mtime}, ...]"""
    watch_dir = _get_watch_dir()
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


@Slot(str, result=int)
def loadJsonFile(self, path):
    # loadFromJson 由 file_ops 提供，通过 MRO 动态派发。
    return self.loadFromJson(path)


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
# 路径 / URI 适配（纯静态工具函数，由主类用 staticmethod 包装）
# ==============================================================
def _resolve_read(raw):
    if not raw:
        return None, None

    if raw.startswith("file://"):
        local = QUrl(raw).toLocalFile()
        return (local, local) if local and os.path.exists(local) else (None, None)

    if len(raw) > 2 and raw[0] == "/" and raw[2] == ":":
        raw = raw[1:]

    if "://" not in raw:
        return (raw, raw) if os.path.exists(raw) else (None, None)

    if raw.startswith("content://"):
        if not is_android():
            return None, None
        try:
            data = _read_android_uri(raw)
            if data is None:
                return None, None
            return io.BytesIO(data), raw
        except Exception as e:
            print("[content://] read failed: {}".format(e))
            return None, None

    qf = QFile(QUrl(raw))
    if not qf.open(QIODevice.ReadOnly):
        return None, None
    try:
        return io.BytesIO(bytes(qf.readAll())), raw
    finally:
        qf.close()


@contextmanager
def _resolve_write(raw):
    if not raw:
        yield None, None
        return

    if raw.startswith("file://"):
        raw = QUrl(raw).toLocalFile() or raw

    if len(raw) > 2 and raw[0] == "/" and raw[2] == ":":
        raw = raw[1:]

    if "://" not in raw:
        yield raw, raw
        return

    if raw.startswith("content://"):
        if not is_android():
            yield None, None
            return
        writer = None
        try:
            writer = _open_android_uri_for_write(raw)
            yield writer, raw
        except Exception as e:
            print("[content://] open for write failed: {}".format(e))
            yield None, None
        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass
        return

    qf = QFile(QUrl(raw))
    if not qf.open(QIODevice.WriteOnly | QIODevice.Truncate):
        yield None, None
        return
    try:
        yield qf, raw
    finally:
        qf.close()


def _read_android_uri(uri_str):
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


def _open_android_uri_for_write(uri_str):
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


def _basename(path_or_uri):
    if not path_or_uri:
        return "未命名"
    name = QUrl(path_or_uri).fileName()
    return name or os.path.basename(path_or_uri) or "未命名"
