# bridge/view_state.py
# ViewStateMixin：负责构建 viewState 字典，供 QML 读取。
# 该 Mixin 只依赖 self._controller，不直接引用其他 Mixin。

import os

from PySide6.QtCore import Property, QUrl, Signal

from core.mode_constants import MODE_DISPLAY


class ViewStateMixin:
    """视图状态 Mixin：viewState Property 与相关构建逻辑"""

    # ---------- 信号 ----------
    viewStateChanged = Signal()

    # ---------- 初始化钩子 ----------
    def _init_view_state(self):
        """由主类显式调用，当前无额外状态"""
        pass

    # ---------- Property ----------
    @Property("QVariantMap", notify=viewStateChanged)
    def viewState(self):
        return self._build_view_state()

    # ---------- 内部构建 ----------
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

    # ---------- 工具函数（原 staticmethod 保留） ----------
    @staticmethod
    def _basename(path_or_uri):
        if not path_or_uri:
            return "未命名"
        name = QUrl(path_or_uri).fileName()
        return name or os.path.basename(path_or_uri) or "未命名"
