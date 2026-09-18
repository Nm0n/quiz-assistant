# platform_utils.py
# 全局唯一的平台判断函数。
#
# 历史教训：
#   - `sys.platform == "android"` 在 PySide6 Android 环境下可能返回 "linux"，不可靠；
#   - `import jnius` 是 Kivy/p4a 传统栈的模块，PySide6 部署不装，必然 ImportError。
#
# 可靠判据：
#   PySide6 的 Android 部署基于 python-for-android，其 Python 解释器内置
#   `sys.getandroidapilevel` 函数，桌面 Python 没有。用它作主判据。

import sys


def is_android() -> bool:
    """判断当前是否运行在 Android 平台。"""
    if hasattr(sys, "getandroidapilevel"):
        return True
    if sys.platform == "android":
        return True
    return False
