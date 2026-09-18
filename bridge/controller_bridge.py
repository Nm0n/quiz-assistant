# bridge/controller_bridge.py
# 主类定义：把 SessionController 适配为 QML 可用的 Qt 对象。
#
# 修正要点：
#   PySide6/Shiboken 不会从 Mixin 里收集 @Slot / @Property。
#   因此改为：
#     1. 各功能模块以"模块级函数"形式提供实现（带 @Slot / @Property 装饰器）；
#     2. 主类通过类属性赋值把这些函数引入自己的命名空间；
#     3. Shiboken 扫描主类命名空间时识别这些带装饰器的函数对象，
#        从而在 QML 元对象系统里注册对应的 Slot / Property。
#
# 这样既拆分了文件，又保证所有 QML 可见名字与拆分前完全一致。
#
# 顶层 @Property（viewState）必须在主类里直接定义：
#   @Property 装饰器需要在类体求值时处理，跨模块赋值不保证被识别。

from PySide6.QtCore import Property

from core.session_controller import SessionController

from .signals import BridgeSignals
from . import android_storage, file_ops, quiz_ops, view_state


class ControllerBridge(BridgeSignals):
    """把 SessionController 适配为 QML 可用的 Qt 对象。"""

    # ============================================================
    # 构造
    # ============================================================
    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller = SessionController()

    # ============================================================
    # 视图状态（@Property 必须在主类里定义）
    # ============================================================
    @Property("QVariantMap", notify=BridgeSignals.viewStateChanged)
    def viewState(self):
        return view_state.build_view_state(self)

    def _refresh(self):
        self.viewStateChanged.emit()

    # ============================================================
    # Android 存储（从 android_storage 模块引入）
    # ============================================================
    isAndroid = android_storage.isAndroid
    hasStoragePermission = android_storage.hasStoragePermission
    openStoragePermissionSettings = android_storage.openStoragePermissionSettings
    ensureWatchDir = android_storage.ensureWatchDir
    getWatchDir = android_storage.getWatchDir
    listJsonFiles = android_storage.listJsonFiles
    loadJsonFile = android_storage.loadJsonFile
    copyToClipboard = android_storage.copyToClipboard

    # 静态方法：用 staticmethod 包装，保持静态语义
    _get_watch_dir = staticmethod(android_storage._get_watch_dir)
    _resolve_read = staticmethod(android_storage._resolve_read)
    _resolve_write = staticmethod(android_storage._resolve_write)
    _read_android_uri = staticmethod(android_storage._read_android_uri)
    _open_android_uri_for_write = staticmethod(android_storage._open_android_uri_for_write)
    _basename = staticmethod(android_storage._basename)

    # ============================================================
    # 文件操作（从 file_ops 模块引入）
    # ============================================================
    loadFromJson = file_ops.loadFromJson
    loadFromExcel = file_ops.loadFromExcel
    saveToFile = file_ops.saveToFile
    saveCurrent = file_ops.saveCurrent

    # ============================================================
    # 刷题操作（从 quiz_ops 模块引入）
    # ============================================================
    switchMode = quiz_ops.switchMode
    toggleFavorite = quiz_ops.toggleFavorite
    toggleWrong = quiz_ops.toggleWrong
    toggleShuffle = quiz_ops.toggleShuffle
    toggleMemoryMode = quiz_ops.toggleMemoryMode
    submitAnswer = quiz_ops.submitAnswer
    updateExplanation = quiz_ops.updateExplanation
    nextQuestion = quiz_ops.nextQuestion
    prevQuestion = quiz_ops.prevQuestion
