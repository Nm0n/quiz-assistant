# bridge/view_state.py
# viewState 字典构建。
#
# 注意：@Property 装饰器必须在主类里直接定义（Shiboken 在类体求值时处理），
# 因此本模块只提供 build_view_state(self) 函数。
# 主类 ControllerBridge 里定义：
#     @Property("QVariantMap", notify=BridgeSignals.viewStateChanged)
#     def viewState(self):
#         return view_state.build_view_state(self)

from core.mode_constants import MODE_DISPLAY


def build_view_state(self):
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
