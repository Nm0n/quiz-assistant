# bridge/__init__.py
# bridge 包入口：只导出 ControllerBridge，保证 `from bridge import ControllerBridge` 可用。

from .controller_bridge import ControllerBridge

__all__ = ["ControllerBridge"]
