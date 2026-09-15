# models.py
# 数据定义层：定义 Question 数据类及相关序列化方法

from dataclasses import dataclass
from typing import List, Dict, Any
from core.utils import generate_question_id


@dataclass
class Question:
    """
    题目数据类，用于表示一道题目及其属性
    """
    id: str                  # 题目唯一标识（基于题干+选项的哈希值）
    type: str               # 题型：单选题、多选题、判断题
    stem: str               # 题干
    options: List[str]      # 选项列表，动态长度（仅包含非空选项，对应A~F）
    answer: str             # 标准答案，统一为大写字母组合（无分隔符）
    is_favorite: bool = False  # 是否收藏，默认False
    is_wrong: bool = False     # 是否为错题，默认False（独立于收藏）
    user_answer: str = ""      # 用户作答的答案（标准化后）
    is_answered: bool = False  # 是否已作答
    explanation: str = ""      # 题目解析文本（新增，默认空字符串）

    def to_dict(self) -> Dict[str, Any]:
        """
        将题目对象转换为字典，用于 JSON 序列化
        """
        return {
            "id": self.id,
            "type": self.type,
            "stem": self.stem,
            "options": self.options,
            "answer": self.answer,
            "is_favorite": self.is_favorite,
            "is_wrong": self.is_wrong,
            "user_answer": self.user_answer,
            "is_answered": self.is_answered,
            "explanation": self.explanation,  # 新增字段
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Question':
        """
        从字典创建 Question 实例，用于 JSON 反序列化
        兼容旧版 JSON：若缺少 explanation 字段则默认为空字符串
        """
        return cls(
            id=data["id"],
            type=data["type"],
            stem=data["stem"],
            options=data["options"],
            answer=data["answer"],
            is_favorite=data.get("is_favorite", False),
            is_wrong=data.get("is_wrong", False),
            user_answer=data.get("user_answer", ""),
            is_answered=data.get("is_answered", False),
            explanation=data.get("explanation", ""),  # 缺失时默认空字符串
        )

        @classmethod
    def create_from_excel_row(cls, q_type: str, stem: str, options: List[str],
                              answer: str, explanation: str = "",
                              is_favorite: bool = False,
                              is_wrong: bool = False) -> 'Question':
        """
        从Excel行数据创建Question实例（工厂方法），自动生成哈希ID
        :param is_favorite: 是否收藏（默认False）
        :param is_wrong: 是否为错题（默认False）
        """
        q_id = generate_question_id(stem, options)
        return cls(
            id=q_id,
            type=q_type,
            stem=stem,
            options=options,
            answer=answer,
            is_favorite=is_favorite,
            is_wrong=is_wrong,
            user_answer="",
            is_answered=False,
            explanation=explanation,
        )
