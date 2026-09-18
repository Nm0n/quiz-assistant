# bridge/__init__.py
# 桥接层包入口：对外只暴露 ControllerBridge。

from .controller_bridge import ControllerBridge

__all__ = ["ControllerBridge"]
