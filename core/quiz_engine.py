# quiz_engine.py
# 核心业务层：负责题目导航、答案判断、收藏/错题切换、沙盒会话管理
# 不包含任何 UI 代码

import random
from typing import List, Optional, Set, Tuple
from copy import deepcopy
from core.models import Question
from core.utils import map_judgment


class QuizEngine:
    """
    刷题引擎，管理题目列表（快照）、当前题目索引、得分、收藏/错题状态切换
    采用沙盒会话机制：所有修改仅作用于快照，通过 changed_ids 记录变更，延迟同步到主数据
    """

    def __init__(self, master_list: List[Question], mode: str = "all"):
        """
        初始化引擎，根据模式从主列表中过滤出快照
        :param master_list: 主数据列表（外部数据，不会被直接修改）
        :param mode: 刷题模式，可选 "all" / "wrong" / "favorite"
        """
        self.master_list = master_list  # 仅用于同步，不直接修改
        self.mode = mode

        # 根据模式过滤出题目ID列表（用于构建快照）
        filtered_ids = self._filter_question_ids(master_list, mode)
        # 创建快照：深拷贝过滤出的题目（独立副本）
        self.questions: List[Question] = []
        for q in master_list:
            if q.id in filtered_ids:
                self.questions.append(deepcopy(q))

        self.current_index: int = 0
        self.score: int = 0  # 得分（累计答对次数）
        self.shuffle_enabled: bool = False
        self.original_order: List[str] = [q.id for q in self.questions]  # 按原始ID顺序
        self.changed_ids: Set[str] = set()  # 记录本次会话中标签被修改的题目ID

        # 如果开启了乱序（默认关闭），无需额外操作

    def _filter_question_ids(self, master_list: List[Question], mode: str) -> Set[str]:
        """
        根据模式从主列表中筛选出符合条件的题目ID集合
        :param master_list: 主数据列表
        :param mode: 模式
        :return: ID集合
        """
        if mode == "all":
            return {q.id for q in master_list}
        elif mode == "wrong":
            return {q.id for q in master_list if q.is_wrong}
        elif mode == "favorite":
            return {q.id for q in master_list if q.is_favorite}
        else:
            raise ValueError(f"未知模式: {mode}")

    def toggle_shuffle(self) -> bool:
        """
        切换乱序状态（开启/关闭）
        :return: 切换后的乱序状态
        """
        self.shuffle_enabled = not self.shuffle_enabled
        if self.shuffle_enabled:
            # 开启乱序：对当前快照随机打乱
            random.shuffle(self.questions)
            # 重置当前索引为0
            self.current_index = 0
        else:
            # 关闭乱序：恢复为原始顺序（按ID升序）
            id_to_question = {q.id: q for q in self.questions}
            # 按原始顺序重建列表
            self.questions = [id_to_question[qid] for qid in self.original_order if qid in id_to_question]
            self.current_index = 0
        return self.shuffle_enabled

    def next_question(self) -> Optional[Question]:
        """
        跳转到下一题，如果当前已在最后一题则循环到第一题
        :return: 切换后的当前题目对象；若题目列表为空则返回 None
        """
        if not self.questions:
            return None
        self.current_index = (self.current_index + 1) % len(self.questions)
        return self.get_current_question()

    def prev_question(self) -> Optional[Question]:
        """
        跳转到上一题，如果当前已在第一题则循环到最后一题
        :return: 切换后的当前题目对象；若题目列表为空则返回 None
        """
        if not self.questions:
            return None
        self.current_index = (self.current_index - 1) % len(self.questions)
        return self.get_current_question()

    def get_current_question(self) -> Optional[Question]:
        """
        获取当前题目对象
        :return: 当前题目；若题目列表为空则返回 None
        """
        if not self.questions:
            return None
        return self.questions[self.current_index]

    def check_answer(self, user_input: str) -> bool:
        """
        检查当前题目的用户作答是否正确，并更新题目状态（user_answer, is_answered, is_wrong）
        答对时自动清除错题标记，答错时自动标记为错题
        :param user_input: 用户输入的答案字符串（标准化前）
        :return: 布尔值，True 表示回答正确，False 表示错误
        """
        question = self.get_current_question()
        if question is None:
            return False

        from core.utils import normalize_answer
        user_clean = normalize_answer(user_input)
        correct_clean = normalize_answer(question.answer)

        # 更新作答记录
        question.user_answer = user_clean
        question.is_answered = True

        # 判断正确性
        is_correct = (user_clean == correct_clean)

        # 更新错题状态：答对则清除错题标记，答错则标记为错题
        if is_correct:
            # 如果之前是错题，现在做对了，从错题本中移除
            if question.is_wrong:
                question.is_wrong = False
                self.changed_ids.add(question.id)
        else:
            # 如果之前不是错题，现在答错了，标记为错题
            if not question.is_wrong:
                question.is_wrong = True
                self.changed_ids.add(question.id)

        return is_correct

    def toggle_favorite(self) -> bool:
        """
        翻转当前题目的收藏状态
        :return: 翻转后的收藏状态（True 表示已收藏，False 表示未收藏）
        """
        question = self.get_current_question()
        if question:
            question.is_favorite = not question.is_favorite
            self.changed_ids.add(question.id)
            return question.is_favorite
        return False

    def toggle_wrong(self) -> bool:
        """
        翻转当前题目的错题标记（手动切换）
        :return: 翻转后的错题状态
        """
        question = self.get_current_question()
        if question:
            question.is_wrong = not question.is_wrong
            self.changed_ids.add(question.id)
            return question.is_wrong
        return False

    def apply_changes_to_master(self, master_list: List[Question]) -> None:
        """
        将快照中 changed_ids 记录的标签变更同步回主数据
        遵循“互不覆盖”原则：仅修改被变更的标签，且不触碰另一个标签
        :param master_list: 主数据列表（外部传入，将被修改）
        """
        if not self.changed_ids:
            return

        # 构建快照ID到Question对象的映射
        snapshot_map = {q.id: q for q in self.questions}

        # 遍历主数据，仅处理 changed_ids 中的题目
        for master_q in master_list:
            if master_q.id in self.changed_ids:
                snapshot_q = snapshot_map.get(master_q.id)
                if snapshot_q:
                    # 只更新被变更的字段，遵循互不覆盖原则
                    # 但我们需要知道具体哪些字段变了。由于我们记录的是ID，但未记录具体变更，所以直接检查快照与主数据差异
                    # 更严谨：比较快照和主数据的 is_favorite 和 is_wrong，只同步差异
                    if master_q.is_favorite != snapshot_q.is_favorite:
                        master_q.is_favorite = snapshot_q.is_favorite
                    if master_q.is_wrong != snapshot_q.is_wrong:
                        master_q.is_wrong = snapshot_q.is_wrong
                    # 注意：同步后，不应自动清除 changed_ids，因为可能后续还需要再次同步，但通常调用后清空
                    # 我们将在调用后清空

        # 同步完成后清空变更记录
        self.changed_ids.clear()

    def get_answered_count(self) -> int:
        """
        获取当前快照中已答题数量
        :return: 已答题数
        """
        return sum(1 for q in self.questions if q.is_answered)

    def get_total_count(self) -> int:
        """
        获取当前快照总题数
        :return: 总题数
        """
        return len(self.questions)

    def reset_current_index(self) -> None:
        """
        重置当前索引为0
        """
        self.current_index = 0

    def get_mode_display(self) -> str:
        """
        获取当前模式的显示名称
        :return: 模式中文名
        """
        from core.mode_constants import MODE_DISPLAY
        return MODE_DISPLAY.get(self.mode, "未知模式")