# platform_utils.py
# 全局唯一的平台判断函数。


def is_android() -> bool:
    """
    判断当前是否运行在 Android 平台。

    PySide6 Android 环境下 sys.platform 的值可能是 "linux" 而不是 "android"，
    因此改用 `import jnius` 是否成功作为判断依据。
    """
    try:
        import jnius  # noqa: F401
        return True
    except ImportError:
        return False
