# session_controller.py
# 会话控制器：平台无关的业务逻辑层
# 负责持有 DataManager / QuizEngine / MemoryMode 以及文件状态，
# 并把所有与界面无关的业务规则集中在此。
# 严禁 import PySide6 或任何 Qt 模块。
#
# 兼容扩展（Android 适配）：
#   load_from_json_file / load_from_excel_file / save_to_file
#   现支持传入 str 路径，或任何 file-like 对象。
#   仅当传入 str 路径时才会更新 current_file_path；
#   传入 file-like 时由调用方（桥接层）负责维护该状态。

import os
from typing import List, Optional, Dict, Any

from core.data_manager import DataManager
from core.quiz_engine import QuizEngine
from core.memory_mode import MemoryMode
from core.mode_constants import MODE_ALL, MODE_WRONG, MODE_FAVORITE, MODE_DISPLAY
from core.models import Question


class SessionController:
    """
    会话控制器：
    - 持有 data_manager / engine / memory_mode / current_mode / current_file_path / is_modified
    - 对外暴露纯业务方法，供 UI 层调用
    - 返回值尽量保持简单（bool / int / str / dict），便于 UI 层决定如何展示
    """

    def __init__(self):
        self.data_manager: DataManager = DataManager()
        self.engine: Optional[QuizEngine] = None
        self.memory_mode: MemoryMode = MemoryMode()
        self.current_mode: str = MODE_ALL
        self.current_file_path: Optional[str] = None
        self.is_modified: bool = False

    # ================================================================
    # 加载 / 保存
    # ================================================================
    def load_from_json_file(self, source) -> int:
        """
        从 JSON 来源加载题库并重建引擎
        :param source: str 路径，或 file-like 对象
        :return: 加载到的题目数量；若为空则返回 0（不改变当前状态）
        """
        questions = self.data_manager.load_from_json_file(source)
        if not questions:
            return 0

        self.engine = QuizEngine(questions, mode=MODE_ALL)
        self.current_mode = MODE_ALL
        # 仅当传入的是字符串路径时才记录到 current_file_path；
        # file-like 场景下由桥接层负责设置（通常是 content:// URI）。
        if isinstance(source, str):
            self.current_file_path = source
        self.is_modified = False
        self.engine.current_index = 0
        self.engine.score = 0
        return len(questions)

    def load_from_excel_file(self, source) -> int:
        """
        从 Excel 来源加载题库（去重后）并重建引擎
        :param source: str 路径，或 file-like 对象
        :return: 去重后的题目数量；若为空则返回 0
        :raises: 读取失败时抛出异常（由 UI 层捕获并提示）
        """
        questions = self.data_manager.load_from_excel(source)
        if not questions:
            return 0

        # 按 id 去重，保留首次出现的题目
        unique_questions: Dict[str, Question] = {}
        for q in questions:
            if q.id not in unique_questions:
                unique_questions[q.id] = q
        questions = list(unique_questions.values())

        self.engine = QuizEngine(questions, mode=MODE_ALL)
        self.current_mode = MODE_ALL
        self.current_file_path = None
        self.is_modified = True
        self.engine.current_index = 0
        self.engine.score = 0
        return len(questions)

    def save_to_file(self, target) -> bool:
        """
        将当前 master_list 保存到指定目标
        :param target: str 路径，或 file-like 对象
        :return: 是否保存成功
        :raises: 保存失败时可能抛出 IOError（由 UI 层捕获）
        """
        if not self.engine or not self.engine.master_list:
            return False
        self.engine.apply_changes_to_master(self.engine.master_list)
        self.data_manager.save_to_json_file(target, self.engine.master_list)

        # 仅当写入本地路径时才更新状态；file-like 场景由桥接层负责。
        if isinstance(target, str):
            self.current_file_path = target
            self.is_modified = False
        return True

    def save_current(self) -> bool:
        """
        尝试保存到当前文件路径
        :return: True 表示保存成功；False 表示没有可用路径（应由 UI 层改走另存为）
        """
        if not self.current_file_path:
            return False
        dir_path = os.path.dirname(self.current_file_path)
        if not dir_path or not os.path.exists(dir_path):
            return False
        return self.save_to_file(self.current_file_path)

    # ================================================================
    # 模式 / 标签 / 作答
    # ================================================================
    def switch_mode(self, mode: str) -> str:
        """
        切换刷题模式：先同步标签回主数据，再基于同一 master_list 重建引擎
        :param mode: 新模式标识（MODE_ALL / MODE_WRONG / MODE_FAVORITE）
        :return: 切换后的模式标识
        """
        if not self.engine:
            self.current_mode = mode
            return mode

        if self.engine.master_list:
            self.engine.apply_changes_to_master(self.engine.master_list)

        master_list = self.engine.master_list
        new_engine = QuizEngine(master_list, mode=mode)
        new_engine.current_index = 0
        new_engine.score = 0
        self.engine = new_engine
        self.current_mode = mode
        self.is_modified = True
        return mode

    def toggle_favorite(self) -> bool:
        """翻转当前题目的收藏状态；无引擎时返回 False"""
        if not self.engine:
            return False
        state = self.engine.toggle_favorite()
        self.is_modified = True
        return state

    def toggle_wrong(self) -> bool:
        """翻转当前题目的错题标记；无引擎时返回 False"""
        if not self.engine:
            return False
        state = self.engine.toggle_wrong()
        self.is_modified = True
        return state

    def toggle_shuffle(self) -> bool:
        """切换乱序状态；无引擎时返回 False"""
        if not self.engine:
            return False
        return self.engine.toggle_shuffle()

    def submit_answer(self, user_answer: str) -> bool:
        """
        提交当前题目的答案
        :param user_answer: 用户答案（标准化前）
        :return: True 表示答对，False 表示答错或没有当前题目
        """
        if not self.engine:
            return False
        is_correct = self.engine.check_answer(user_answer)
        self.is_modified = True
        if is_correct:
            self.engine.score += 1
        return is_correct

    def update_explanation(self, text: str) -> None:
        """
        更新当前题目的解析内容，并同步到 master_list
        :param text: 新的解析文本
        """
        if not self.engine:
            return
        q = self.engine.get_current_question()
        if q is None:
            return
        if q.explanation == text:
            return
        q.explanation = text
        if self.engine.master_list:
            for mq in self.engine.master_list:
                if mq.id == q.id:
                    mq.explanation = text
                    break
        self.is_modified = True

    # ================================================================
    # 导航
    # ================================================================
    def next_question(self) -> Optional[Question]:
        if not self.engine:
            return None
        return self.engine.next_question()

    def prev_question(self) -> Optional[Question]:
        if not self.engine:
            return None
        return self.engine.prev_question()

    # ================================================================
    # 记忆模式
    # ================================================================
    def toggle_memory_mode(self) -> bool:
        """翻转记忆模式状态；返回翻转后的状态"""
        return self.memory_mode.toggle()

    # ================================================================
    # 视图状态查询
    # ================================================================
    def has_questions(self) -> bool:
        """当前是否持有可用题目"""
        return bool(self.engine and self.engine.questions)

    def get_current_question(self) -> Optional[Question]:
        """返回当前题目；无引擎或无题目返回 None"""
        if not self.engine:
            return None
        return self.engine.get_current_question()

    def get_view_state(self) -> Optional[Dict[str, Any]]:
        """
        汇总一次界面渲染所需的全部信息
        :return: dict，包含 index / total / question / progress /
                 mode_display / score / memory_enabled；
                 若没有可用题目则返回 None
        """
        if not self.engine or not self.engine.questions:
            return None
        question = self.engine.get_current_question()
        if question is None:
            return None

        total = len(self.engine.questions)
        current = self.engine.current_index + 1
        answered = self.engine.get_answered_count()
        progress = int((answered / total) * 100) if total > 0 else 0

        return {
            "index": current,
            "total": total,
            "question": question,
            "progress": progress,
            "mode_display": self.engine.get_mode_display(),
            "score": self.engine.score,
            "memory_enabled": self.memory_mode.is_active(),
        }