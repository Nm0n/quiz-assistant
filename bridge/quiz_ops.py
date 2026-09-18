# bridge/quiz_ops.py
# QuizOpsMixin：负责作答、模式切换、收藏/错题/记忆开关、导航。
# 该 Mixin 只依赖 self._controller，不直接引用其他 Mixin。

from PySide6.QtCore import Slot

from core.mode_constants import MODE_ALL, MODE_WRONG, MODE_FAVORITE, MODE_DISPLAY
from core.utils import map_judgment


class QuizOpsMixin:
    """刷题操作 Mixin：模式 / 标签 / 记忆 / 作答 / 导航"""

    # ---------- 初始化钩子 ----------
    def _init_quiz_ops(self):
        """由主类显式调用，当前无额外状态"""
        pass

    # ==============================================================
    # 模式 / 标签 / 记忆
    # ==============================================================
    @Slot(str)
    def switchMode(self, mode):
        if mode not in (MODE_ALL, MODE_WRONG, MODE_FAVORITE):
            return
        if not self._controller.engine:
            self._refresh()
            return

        self._controller.switch_mode(mode)
        self._refresh()
        suffix = "（记忆模式保持开启）" if self._controller.memory_mode.is_active() else ""
        self.infoMessage.emit(
            "模式切换成功：{}，进度已重置{}".format(MODE_DISPLAY.get(mode, mode), suffix)
        )

    @Slot(result=bool)
    def toggleFavorite(self):
        if not self._controller.has_questions():
            return False
        state = self._controller.toggle_favorite()
        self._refresh()
        return bool(state)

    @Slot(result=bool)
    def toggleWrong(self):
        if not self._controller.has_questions():
            return False
        state = self._controller.toggle_wrong()
        self._refresh()
        return bool(state)

    @Slot(result=bool)
    def toggleShuffle(self):
        if not self._controller.has_questions():
            return False
        enabled = self._controller.toggle_shuffle()
        self._refresh()
        self.infoMessage.emit("🎲 乱序已" + ("开启" if enabled else "关闭"))
        return bool(enabled)

    @Slot(result=bool)
    def toggleMemoryMode(self):
        enabled = self._controller.toggle_memory_mode()
        self._refresh()
        self.infoMessage.emit(
            "🧠 已进入记忆模式：显示答案与解析，选项只读"
            if enabled else "已退出记忆模式"
        )
        return bool(enabled)

    # ==============================================================
    # 作答
    # ==============================================================
    @Slot(str, result=bool)
    def submitAnswer(self, user_answer):
        if not self._controller.has_questions():
            return False
        if self._controller.memory_mode.is_active():
            self.infoMessage.emit("记忆模式下选项已锁定，请先退出记忆模式再作答")
            return False

        question = self._controller.get_current_question()
        if question is None:
            return False
        if question.is_answered:
            self.infoMessage.emit("本题已作答，不能重复提交")
            return False
        if not user_answer:
            self.infoMessage.emit("请至少选择一个选项")
            return False

        is_correct = self._controller.submit_answer(user_answer)
        self._refresh()

        if is_correct:
            self.infoMessage.emit("✅ 回答正确！")
        else:
            answer = question.answer
            if question.type == "判断题":
                self.infoMessage.emit("❌ 回答错误，正确答案是 {}".format(map_judgment(answer)))
            elif question.type == "多选题":
                user_set, correct_set = set(user_answer or ""), set(answer or "")
                if user_set and user_set.issubset(correct_set):
                    self.infoMessage.emit("⚠️ 漏选，正确答案是 {}".format(answer))
                else:
                    self.infoMessage.emit("❌ 错选，正确答案是 {}".format(answer))
            else:
                self.infoMessage.emit("❌ 回答错误，正确答案是 {}".format(answer))
        return bool(is_correct)

    @Slot(str)
    def updateExplanation(self, text):
        self._controller.update_explanation(text)

    # ==============================================================
    # 导航
    # ==============================================================
    @Slot()
    def nextQuestion(self):
        if self._controller.has_questions():
            self._controller.next_question()
            self._refresh()

    @Slot()
    def prevQuestion(self):
        if self._controller.has_questions():
            self._controller.prev_question()
            self._refresh()
