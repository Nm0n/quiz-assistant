# bridge/controller_bridge.py
# ControllerBridge 主类：通过 Mixin 组合把原单类拆分为多职责。
# 主类只保留：
#   - 两个跨 Mixin 共享的信号 infoMessage / errorOccurred
#   - __init__：创建 SessionController 并调用各 Mixin 的初始化钩子
# 所有 Slot / Property / 业务方法均在各自 Mixin 中定义。

from PySide6.QtCore import QObject, Signal

from core.session_controller import SessionController

from .file_ops import FileOpsMixin
from .quiz_ops import QuizOpsMixin
from .android_storage import AndroidStorageMixin
from .view_state import ViewStateMixin


class ControllerBridge(FileOpsMixin, QuizOpsMixin, AndroidStorageMixin, ViewStateMixin, QObject):
    """把 SessionController 适配为 QML 可用的 Qt 对象。"""

    infoMessage = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller = SessionController()
        self._init_file_ops()
        self._init_quiz_ops()
        self._init_android_storage()
        self._init_view_state()
