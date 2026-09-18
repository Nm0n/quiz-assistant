# bridge/signals.py
# 信号集中定义。
#
# 设计原因：
#   - PySide6 的 @Property(notify=...) 在类体求值时会解析 notify 参数，
#     若 notify 指向一个未在类命名空间中出现的名字，会报 NameError；
#   - 若每个 Mixin 各自定义信号，会带来"同一信号多次定义"的隐式覆盖风险；
#   - 因此让所有 Mixin 继承同一个 BridgeSignals 基类，信号只在此处定义一次，
#     整个继承链上只有一个 QObject 基类，符合 Shiboken 的单 QObject 约束。
#
# 信号名、参数类型、顺序与拆分前的 ControllerBridge 完全一致。

from PySide6.QtCore import QObject, Signal


class BridgeSignals(QObject):
    """所有 QML 可见信号的集中定义，作为各 Mixin 的公共基类。"""

    viewStateChanged = Signal()
    infoMessage = Signal(str)
    errorOccurred = Signal(str)
    qmlFileDialogRequested = Signal()
    # 请求 QML 显示"需要存储权限"引导对话框
    storagePermissionRequired = Signal()
