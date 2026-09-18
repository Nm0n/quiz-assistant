# platform_utils.py
# 平台判断工具：全局唯一的 Android 判定入口。
#
# 检测策略（不触发 JNI，可安全用于启动早期）：
#   1. sys.getandroidapilevel() 存在 → 确定是 Android
#   2. sys.platform == "android" → Python 3.13+ 的官方标识
#   3. ANDROID_ARGUMENT / ANDROID_PRIVATE 环境变量 → p4a 打包环境的兜底
#
# 注意：不要在本文件里导入 jnius / android / autoclass，
# 那些会触发 JNI 初始化，干扰 Qt 的 JVM 状态。

import os
import sys


def is_android() -> bool:
    """判断当前是否运行在 Android 环境（不触发 JNI）"""
    if hasattr(sys, "getandroidapilevel"):
        return True

    if sys.platform == "android":
        return True

    if "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ:
        return True

    return False
