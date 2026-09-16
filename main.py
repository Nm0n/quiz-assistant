# main.py
# 移动端 / 跨平台入口：加载 QML，注册桥接对象，启动应用。
#
# core/ 前提：IO 方法接受 str 路径或 file-like 对象。
# 桥接层把 QML 传来的字符串统一转成 core 能消费的「路径或流」。
#
# Android 适配要点：
#   - content:// URI 无法用 QFile 读取，必须走 ContentResolver
#   - 使用原生 Intent 打开文件选择器，避免 QML FileDialog 的 JNI 竞态
#   - 必须启动 Qt 事件循环（app.exec()），否则主线程退出会导致崩溃

import io
import os
import sys
from contextlib import contextmanager

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot, QFile, QIODevice, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from core.session_controller import SessionController
from core.mode_constants import MODE_ALL, MODE_WRONG, MODE_FAVORITE, MODE_DISPLAY
from core.utils import map_judgment


# 使用 Basic style：允许 Button / ProgressBar 等完全自定义样式，
# 消除 Windows 原生 style 下的 "does not support customization" 警告。
QQuickStyle.setStyle("Basic")


class ControllerBridge(QObject):
    """把 SessionController 适配为 QML 可用的 Qt 对象。"""

    viewStateChanged = Signal()
    infoMessage = Signal(str)
    errorOccurred = Signal(str)
    # 桌面端请求 QML 打开 FileDialog（Android 端不走这个信号）
    qmlFileDialogRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller = SessionController()
        # 文件选择器回调绑定状态
        self._file_picker_bound = False
        self._file_picker_callback = None

    # ==============================================================
    # 平台判断（供 QML 读取）
    # ==============================================================
    @Property(bool, constant=True)
    def isAndroid(self):
        return sys.platform == "android"

    # ==============================================================
    # 路径 / URI 适配
    # ==============================================================
    @staticmethod
    def _resolve_read(raw):
        """
        QML 传来的字符串 → (source, resolved)
          source   : 传给 core 的读取对象（str 路径 或 BytesIO）
          resolved : 记录到 current_file_path 的位置（用于写回）
        无法读取时返回 (None, None)。
        """
        if not raw:
            return None, None

        # file:// URL → 用 QUrl 转本地路径（跨平台正确）
        if raw.startswith("file://"):
            local = QUrl(raw).toLocalFile()
            return (local, local) if local and os.path.exists(local) else (None, None)

        # 兜底：某些情况下可能残留 /D:/... 形式，纠正 Windows 盘符
        if len(raw) > 2 and raw[0] == "/" and raw[2] == ":":
            raw = raw[1:]

        # 本地路径
        if "://" not in raw:
            return (raw, raw) if os.path.exists(raw) else (None, None)

        # ========== Android content:// URI ==========
        if raw.startswith("content://"):
            if sys.platform != "android":
                return None, None
            try:
                data = ControllerBridge._read_android_uri(raw)
                if data is None:
                    return None, None
                return io.BytesIO(data), raw
            except Exception as e:
                print("[content://] read failed: {}".format(e))
                return None, None

        # 其它远程 URI（如 http://）→ 用 QFile 尝试
        qf = QFile(QUrl(raw))
        if not qf.open(QIODevice.ReadOnly):
            return None, None
        try:
            return io.BytesIO(bytes(qf.readAll())), raw
        finally:
            qf.close()

    @staticmethod
    @contextmanager
    def _resolve_write(raw):
        """
        QML 传来的字符串 → 产出 (target, resolved)。
        target 为 None 表示无法写入。
        """
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

        # ========== Android content:// URI（另存为场景）==========
        if raw.startswith("content://"):
            if sys.platform != "android":
                yield None, None
                return
            writer = None
            try:
                writer = ControllerBridge._open_android_uri_for_write(raw)
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

        # 其它远程 URI → 用 QFile
        qf = QFile(QUrl(raw))
        if not qf.open(QIODevice.WriteOnly | QIODevice.Truncate):
            yield None, None
            return
        try:
            yield qf, raw
        finally:
            qf.close()

    # ==============================================================
    # Android ContentResolver 辅助
    # ==============================================================
    @staticmethod
    def _read_android_uri(uri_str):
        """
        用 Android 的 ContentResolver.openInputStream() 读取 content:// URI 的全部字节。
        读取失败返回 None。
        """
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

    @staticmethod
    def _open_android_uri_for_write(uri_str):
        """
        用 Android 的 ContentResolver.openOutputStream() 打开 content:// URI 用于写入。
        返回一个模拟 file-like 的对象，支持 write(bytes) 和 close()。
        """
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

    @staticmethod
    def _basename(path_or_uri):
        if not path_or_uri:
            return "未命名"
        name = QUrl(path_or_uri).fileName()
        return name or os.path.basename(path_or_uri) or "未命名"

    # ==============================================================
    # 视图状态
    # ==============================================================
    @Property("QVariantMap", notify=viewStateChanged)
    def viewState(self):
        return self._build_view_state()

    def _build_view_state(self):
        c = self._controller
        engine = c.engine

        base = {
            "hasQuestion": False,
            "index": 0, "total": 0, "progress": 0, "score": 0,
            "modeDisplay": MODE_DISPLAY.get(c.current_mode, ""),
            "currentMode": c.current_mode,
            "memoryEnabled": c.memory_mode.is_active(),
            "shuffleEnabled": bool(engine.shuffle_enabled) if engine else False,
            "isModified": bool(c.is_modified),
            "fileName": self._basename(c.current_file_path),
            "hasFilePath": bool(c.current_file_path),
            "question": {},
        }

        state = c.get_view_state()
        if state is None:
            return base

        q = state["question"]
        base.update({
            "hasQuestion": True,
            "index": state["index"],
            "total": state["total"],
            "progress": state["progress"],
            "score": state["score"],
            "modeDisplay": state["mode_display"],
            "memoryEnabled": state["memory_enabled"],
            "question": {
                "id": q.id,
                "type": q.type,
                "stem": q.stem,
                "options": list(q.options),
                "answer": q.answer,
                "isFavorite": bool(q.is_favorite),
                "isWrong": bool(q.is_wrong),
                "userAnswer": q.user_answer or "",
                "isAnswered": bool(q.is_answered),
                "explanation": q.explanation or "",
            },
        })
        return base

    def _refresh(self):
        self.viewStateChanged.emit()

    # ==============================================================
    # 文件选择器（Android 原生 Intent / 桌面 QML FileDialog）
    # ==============================================================
    @Slot()
    def openFilePicker(self):
        """
        打开文件选择器：
          - Android：使用原生 Intent.ACTION_GET_CONTENT，通过 onActivityResult 拿到 content:// URI
          - 桌面：发出 qmlFileDialogRequested 信号，由 QML 打开 FileDialog
        """
        if sys.platform != "android":
            self.qmlFileDialogRequested.emit()
            return

        try:
            from jnius import autoclass
            from android import activity as android_activity

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")

            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType("*/*")
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

            current_activity = PythonActivity.mActivity

            # 确保同一时间只绑定一个回调
            if self._file_picker_bound and self._file_picker_callback is not None:
                try:
                    android_activity.unbind(self._file_picker_callback)
                except Exception:
                    pass
                self._file_picker_bound = False
                self._file_picker_callback = None

            def on_activity_result(request_code, result_code, data):
                # 一次性回调：立即解绑
                try:
                    android_activity.unbind(on_activity_result)
                except Exception:
                    pass
                self._file_picker_bound = False
                self._file_picker_callback = None

                if request_code != 1001:
                    return
                # RESULT_OK == -1
                if result_code != -1:
                    print("[FilePicker] cancelled, result_code={}".format(result_code))
                    return
                if data is None:
                    print("[FilePicker] data is None")
                    return

                try:
                    uri = data.getData()
                    if uri is None:
                        print("[FilePicker] uri is None")
                        return
                    uri_str = uri.toString()
                    print("[FilePicker] selected URI: " + uri_str)
                    # 切回 Qt 主线程处理
                    QTimer.singleShot(0, lambda: self._load_from_android_uri(uri_str))
                except Exception as e:
                    print("[FilePicker] handle result failed: {}".format(e))
                    self.errorOccurred.emit("处理选择结果失败：{}".format(e))

            self._file_picker_callback = on_activity_result
            self._file_picker_bound = True
            android_activity.bind(on_activity_result)

            current_activity.startActivityForResult(intent, 1001)

        except Exception as e:
            print("[FilePicker] start failed: {}".format(e))
            self.errorOccurred.emit("无法打开文件选择器：{}".format(e))

    def _load_from_android_uri(self, uri_str):
        """从 Android content:// URI 加载 JSON 文件（在主线程中执行）"""
        try:
            raw = self._read_android_uri(uri_str)
        except Exception as e:
            self.errorOccurred.emit("无法读取所选文件：{}".format(e))
            return

        if not raw:
            self.errorOccurred.emit("所选文件为空")
            return

        try:
            source = io.BytesIO(raw)
            count = self._controller.load_from_json_file(source)
        except Exception as e:
            self.errorOccurred.emit("加载失败：{}".format(e))
            return

        if count > 0:
            self._controller.current_file_path = uri_str
            self._controller.is_modified = False
            self.infoMessage.emit("已打开题库，共 {} 道题".format(count))
        else:
            self.errorOccurred.emit("该文件不包含有效题目数据")

        self._refresh()

    # ==============================================================
    # 文件操作（路径 / URI 通用入口）
    # ==============================================================
    @Slot(str, result=int)
    def loadFromJson(self, raw):
        source, resolved = self._resolve_read(raw)
        if source is None:
            self.errorOccurred.emit(
                "无法读取所选文件。\n\n"
                "Android 端请把 JSON 放到「下载」等可访问目录后再选择；"
                "云盘文件请先下载到本地。"
            )
            return 0

        try:
            count = self._controller.load_from_json_file(source)
        except Exception as e:
            self.errorOccurred.emit("打开失败：{}".format(e))
            return 0

        if count > 0:
            self._controller.current_file_path = resolved
            self._controller.is_modified = False

        self._refresh()
        if count == 0:
            self.errorOccurred.emit("该文件不包含有效题目数据")
        else:
            self.infoMessage.emit("已打开题库，共 {} 道题".format(count))
        return count

    @Slot(str, result=int)
    def loadFromExcel(self, raw):
        # Android 端 pandas/openpyxl 未打包，直接拒绝
        if sys.platform == "android":
            self.errorOccurred.emit("Android 端不支持 Excel 导入，请使用 JSON 格式的题库。")
            return 0

        source, _ = self._resolve_read(raw)
        if source is None:
            self.errorOccurred.emit("无法读取所选文件")
            return 0

        try:
            count = self._controller.load_from_excel_file(source)
        except Exception as e:
            self.errorOccurred.emit(
                "导入失败：{}\n\n"
                "Android 端通常不支持 Excel，请先在桌面端转为 JSON。".format(e)
            )
            return 0

        if count > 0:
            self._controller.current_file_path = None
            self._controller.is_modified = True

        self._refresh()
        if count == 0:
            self.errorOccurred.emit("Excel 文件中没有有效题目")
        else:
            self.infoMessage.emit("已从 Excel 导入 {} 道题，请记得保存".format(count))
        return count

    @Slot(str, result=bool)
    def saveToFile(self, raw):
        if not self._controller.has_questions():
            self.errorOccurred.emit("没有可保存的数据")
            return False

        with self._resolve_write(raw) as pair:
            target, resolved = pair
            if target is None:
                self.errorOccurred.emit("保存失败：无法写入所选位置")
                return False
            try:
                self._controller.save_to_file(target)
            except Exception as e:
                self.errorOccurred.emit("保存失败：{}".format(e))
                return False

        self._controller.current_file_path = resolved
        self._controller.is_modified = False
        self._refresh()
        self.infoMessage.emit("已保存")
        return True

    @Slot(result=bool)
    def saveCurrent(self):
        path = self._controller.current_file_path
        if not self._controller.has_questions() or not path:
            return False
        return self.saveToFile(path)

    # ==============================================================
    # 模式 / 标签 / 记忆
    # ==============================================================
    @Slot(str)
    def switchMode(self, mode):
        if mode not in (MODE_ALL, MODE_WRONG, MODE_FAVORITE):
            return
        if not self._controller.engine:
            self._refresh()
            return

        self._controller.switch_mode(mode)
        self._refresh()
        suffix = "（记忆模式保持开启）" if self._controller.memory_mode.is_active() else ""
        self.infoMessage.emit(
            "模式切换成功：{}，进度已重置{}".format(MODE_DISPLAY.get(mode, mode), suffix)
        )

    @Slot(result=bool)
    def toggleFavorite(self):
        if not self._controller.has_questions():
            return False
        state = self._controller.toggle_favorite()
        self._refresh()
        return bool(state)

    @Slot(result=bool)
    def toggleWrong(self):
        if not self._controller.has_questions():
            return False
        state = self._controller.toggle_wrong()
        self._refresh()
        return bool(state)

    @Slot(result=bool)
    def toggleShuffle(self):
        if not self._controller.has_questions():
            return False
        enabled = self._controller.toggle_shuffle()
        self._refresh()
        self.infoMessage.emit("🎲 乱序已" + ("开启" if enabled else "关闭"))
        return bool(enabled)

    @Slot(result=bool)
    def toggleMemoryMode(self):
        enabled = self._controller.toggle_memory_mode()
        self._refresh()
        self.infoMessage.emit(
            "🧠 已进入记忆模式：显示答案与解析，选项只读"
            if enabled else "已退出记忆模式"
        )
        return bool(enabled)

    # ==============================================================
    # 作答
    # ==============================================================
    @Slot(str, result=bool)
    def submitAnswer(self, user_answer):
        if not self._controller.has_questions():
            return False
        if self._controller.memory_mode.is_active():
            self.infoMessage.emit("记忆模式下选项已锁定，请先退出记忆模式再作答")
            return False

        question = self._controller.get_current_question()
        if question is None:
            return False
        if question.is_answered:
            self.infoMessage.emit("本题已作答，不能重复提交")
            return False
        if not user_answer:
            self.infoMessage.emit("请至少选择一个选项")
            return False

        is_correct = self._controller.submit_answer(user_answer)
        self._refresh()

        if is_correct:
            self.infoMessage.emit("✅ 回答正确！")
        else:
            answer = question.answer
            if question.type == "判断题":
                self.infoMessage.emit("❌ 回答错误，正确答案是 {}".format(map_judgment(answer)))
            elif question.type == "多选题":
                user_set, correct_set = set(user_answer or ""), set(answer or "")
                if user_set and user_set.issubset(correct_set):
                    self.infoMessage.emit("⚠️ 漏选，正确答案是 {}".format(answer))
                else:
                    self.infoMessage.emit("❌ 错选，正确答案是 {}".format(answer))
            else:
                self.infoMessage.emit("❌ 回答错误，正确答案是 {}".format(answer))
        return bool(is_correct)

    @Slot(str)
    def updateExplanation(self, text):
        # 刻意不 _refresh()，避免解析框被重新赋值导致光标跳动
        self._controller.update_explanation(text)

    # ==============================================================
    # 导航
    # ==============================================================
    @Slot()
    def nextQuestion(self):
        if self._controller.has_questions():
            self._controller.next_question()
            self._refresh()

    @Slot()
    def prevQuestion(self):
        if self._controller.has_questions():
            self._controller.prev_question()
            self._refresh()


# ==================================================================
# 入口
# ==================================================================
def _qml_candidates():
    """
    返回 QML 主文件的候选路径列表，按优先级排序。
    """
    candidates = []

    # 1) Qt 资源系统（qrc）
    candidates.append("qrc:/qml/main.qml")

    # 2) Android assets 协议
    candidates.append("assets:/qml/main.qml")

    # 3) 文件系统路径（桌面端主用）
    base = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base, "qml", "main.qml"))
    candidates.append(os.path.join(base, "..", "qml", "main.qml"))
    candidates.append(os.path.join(os.getcwd(), "qml", "main.qml"))

    # 4) Android 应用私有目录
    if sys.platform == "android":
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

    # 启动 Qt 事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
