# platform_utils.py
# 平台判断工具：全局唯一的 Android 判定入口。
#
# 注意：本阶段严格保持与原 main.py 中 `sys.platform == "android"` 的语义一致。
# 已知在 PySide6 Android 环境下 sys.platform 可能为 "linux"，
# 导致本函数返回 False，进而引发路径错误、权限引导不弹等问题。
# 这是拆分前就存在的 bug，本阶段不修复，留待独立阶段处理。

import sys


def is_android() -> bool:
    """判断当前是否运行在 Android 环境（保持原 sys.platform 判断语义）"""
    return sys.platform == "android"
