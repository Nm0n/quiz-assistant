# platform_utils.py
# 平台判断工具：全局唯一的 Android 判定入口。
#
# 为什么不用 sys.platform == "android"：
#   Python 3.12 及更早版本在 Android 上返回 sys.platform == "linux"，
#   直到 Python 3.13 才正式改为 "android"（PEP 783）。
#   本项目使用 Python 3.11.5，必须使用 sys.getandroidapilevel() 检测。
#
# sys.getandroidapilevel() 自 Python 3.7 起可用，仅在 Android 环境下存在。
# 参考：https://docs.python.org/3/library/sys.html#sys.getandroidapilevel

import sys


def is_android() -> bool:
    """
    判断当前是否运行在 Android 环境。

    检测策略（优先级从高到低）：
      1. sys.getandroidapilevel() 存在 → 确定是 Android（最可靠）
      2. sys.platform == "android" → 未来 Python 3.13+ 的官方标识
      3. 环境变量 ANDROID_ARGUMENT → p4a 打包环境的兜底检测
    """
    # 方法 1：Python 3.7+ 在 Android 上独有的属性
    if hasattr(sys, "getandroidapilevel"):
        return True

    # 方法 2：Python 3.13+ 的官方标识
    if sys.platform == "android":
        return True

    # 方法 3：p4a 环境变量兜底
    import os
    if "ANDROID_ARGUMENT" in os.environ:
        return True

    return False
