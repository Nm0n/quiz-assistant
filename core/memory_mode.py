# memory_mode.py
# 记忆模式状态容器：纯状态管理，不依赖任何 UI 控件
# 用于记录全局"记忆模式"的开关状态，由 MainWindow 持有，
# 因此切换刷题模式（重建 QuizEngine）不会影响该状态


class MemoryMode:
    """记忆模式全局开关状态容器"""

    def __init__(self):
        # 默认关闭记忆模式
        self.enabled: bool = False

    def toggle(self) -> bool:
        """
        翻转记忆模式状态
        :return: 翻转后的状态（True 表示已开启）
        """
        self.enabled = not self.enabled
        return self.enabled

    def is_active(self) -> bool:
        """
        返回当前是否处于记忆模式
        """
        return self.enabled