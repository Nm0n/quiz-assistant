# bridge/controller_bridge.py
# 主类定义：把 SessionController 适配为 QML 可用的 Qt 对象。
#
# 本文件只做两件事：
#   1. 通过 Mixin 组合，把原来的 ControllerBridge 按职责拆分；
#   2. 在 __init__ 中创建 SessionController。
#
# 方法、Slot 名、信号名、属性名与拆分前完全一致，QML 端无需任何改动。

from core.session_controller import SessionController

from .file_ops import FileOpsMixin
from .quiz_ops import QuizOpsMixin
from .android_storage import AndroidStorageMixin
from .view_state import ViewStateMixin


class ControllerBridge(
    FileOpsMixin,
    QuizOpsMixin,
    AndroidStorageMixin,
    ViewStateMixin,
):
    """
    把 SessionController 适配为 QML 可用的 Qt 对象。

    Mixin 职责划分：
        FileOpsMixin        — 文件加载 / 保存 / Excel 导入
        QuizOpsMixin        — 作答、模式、收藏、错题、记忆、导航
        AndroidStorageMixin — 平台判断、存储权限、目录扫描、content:// URI 处理
        ViewStateMixin      — viewState 字典构建与刷新
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller = SessionController()
