# bridge/view_state.py
# ViewStateMixin：构建 viewState 字典并对外发出刷新信号。
#
# 与拆分前 ControllerBridge 中对应方法一一对应，方法名、@Property 装饰器、
# 返回结构完全一致。唯一调整是 notify=viewStateChanged 改为
# notify=BridgeSignals.viewStateChanged，原因见文件头注释上方说明。

from PySide6.QtCore import Property

from core.mode_constants import MODE_DISPLAY
from .signals import BridgeSignals


class ViewStateMixin(BridgeSignals):
    """构建 QML 侧 viewState 字典、触发刷新。"""

    @Property("QVariantMap", notify=BridgeSignals.viewStateChanged)
    def viewState(self):
        return self._build_view_state()

    def _build_view_state(self):
        c = self._controller
        engine = c.engine

        base = {
            "hasQuestion": False,
            "index": 0, "total": 0, "progress": 0, "score": 0,
            "modeDisplay": MODE_DISPLAY.get(c.current_mode, ""),
            "currentMode": c.current_mode,
            "memoryEnabled": c.memory_mode.is_active(),
            "shuffleEnabled": bool(engine.shuffle_enabled) if engine else False,
            "isModified": bool(c.is_modified),
            "fileName": self._basename(c.current_file_path),
            "hasFilePath": bool(c.current_file_path),
            "question": {},
        }

        state = c.get_view_state()
        if state is None:
            return base

        q = state["question"]
        base.update({
            "hasQuestion": True,
            "index": state["index"],
            "total": state["total"],
            "progress": state["progress"],
            "score": state["score"],
            "modeDisplay": state["mode_display"],
            "memoryEnabled": state["memory_enabled"],
            "question": {
                "id": q.id,
                "type": q.type,
                "stem": q.stem,
                "options": list(q.options),
                "answer": q.answer,
                "isFavorite": bool(q.is_favorite),
                "isWrong": bool(q.is_wrong),
                "userAnswer": q.user_answer or "",
                "isAnswered": bool(q.is_answered),
                "explanation": q.explanation or "",
            },
        })
        return base

    def _refresh(self):
        self.viewStateChanged.emit()
