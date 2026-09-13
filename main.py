# main.py
# 移动端 / 跨平台入口：加载 QML，注册桥接对象，启动应用。
#
# core/ 前提：IO 方法接受 str 路径或 file-like 对象。
# 桥接层把 QML 传来的字符串统一转成 core 能消费的「路径或流」。

import io
import os
import sys
from contextlib import contextmanager

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot, QFile, QIODevice
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller = SessionController()

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

        # content:// 等远程 URI → 读入内存
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
        target 为 None 表示无法写入。QFile 在 with 退出时自动关闭。
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

        qf = QFile(QUrl(raw))
        if not qf.open(QIODevice.WriteOnly | QIODevice.Truncate):
            yield None, None
            return
        try:
            yield qf, raw
        finally:
            qf.close()

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
    # 文件操作
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
def _qml_main_path():
    base = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base, "qml", "main.qml")
    return candidate if os.path.exists(candidate) else os.path.join(os.getcwd(), "qml", "main.qml")


def main():
    app = QGuiApplication(sys.argv)
    app.setApplicationName("智能刷题助手")
    app.setOrganizationName("QuizAssistant")

    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: [print("[QML WARN]", w.toString()) for w in ws])

    # ★★★ 关键：必须用变量持有 bridge，否则会被 Python GC 回收，
    #     导致 QML 侧 bridge === null，所有调用报
    #     "Cannot read property 'viewState' of null"。
    bridge = ControllerBridge()
    engine.rootContext().setContextProperty("bridge", bridge)

    qml_path = _qml_main_path()
    engine.load(QUrl.fromLocalFile(qml_path))
    if not engine.rootObjects():
        sys.stderr.write("QML 加载失败：{}\n".format(qml_path))
        sys.exit(-1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()