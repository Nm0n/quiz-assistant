# data_manager.py
# 数据持久层：负责从 Excel 读取题目、读写完整题库 JSON（含所有标签）
# 支持从任意路径加载/保存 JSON 文件，默认数据目录 data/ 仅作为后备
#
# 兼容扩展（Android 适配）：
#   load_from_excel / load_from_json_file / save_to_json_file
#   现支持传入 str 路径，或任何具有 read() / write() 的文件对象
#   （如 io.BytesIO、QFile）。桌面端传 str 路径时行为与原来完全一致。

import os
import json
from typing import List, Dict, Any
from core.models import Question
from core.utils import normalize_answer, get_option_letter


class DataManager:
    """
    数据管理器，负责题目的导入、收藏/错题状态的持久化，以及完整题库的保存与加载
    """

    def __init__(self, data_dir: str = "data"):
        """
        初始化数据管理器，自动创建数据目录（Android 下自动回退到可写目录）
        """
        # 尝试创建用户指定的目录；失败则回退到系统临时目录
        try:
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)
        except Exception:
            import tempfile
            data_dir = os.path.join(tempfile.gettempdir(), "quizassistant")
            os.makedirs(data_dir, exist_ok=True)
        self.data_dir = data_dir

    def _get_default_path(self, filename: str = "questions.json") -> str:
        """获取默认路径（仅用于向后兼容）"""
        return os.path.join(self.data_dir, filename)

    # ========== 从 Excel 导入 ==========
    def load_from_excel(self, source) -> List[Question]:
        """
        从 Excel 文件读取题目，返回 Question 对象列表
        支持选项A~F（可选的E列和F列），支持"解析"/"题目解析"列
        :param source: Excel 文件路径（str），或任何支持 read() 的文件对象
        :return: 题目列表
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError(
                "当前环境缺少 pandas / openpyxl，无法导入 Excel。\n"
                "请先在桌面端把 Excel 转为 JSON 后再导入。"
            ) from e

        is_stream = hasattr(source, "read")
        if not is_stream and not os.path.exists(source):
            raise FileNotFoundError(f"文件不存在: {source}")

        try:
            df = pd.read_excel(source, engine='openpyxl')
        except Exception as e:
            raise ValueError(f"读取 Excel 文件失败: {str(e)}")

        required_columns = ["题型", "题干", "答案"]
        df.columns = [str(col).strip() for col in df.columns]
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Excel 缺少必要列: {', '.join(missing_cols)}")

        questions = []
        for idx, row in df.iterrows():
            row = {k: (str(v).strip() if v is not None else "") for k, v in row.items()}

            if not row.get("题干", "").strip():
                continue

            q_type = row.get("题型", "").strip()
            stem = row.get("题干", "").strip()
            answer_raw = row.get("答案", "").strip()

            if q_type not in ["单选题", "多选题", "判断题"]:
                continue

            # ========== 读取解析列（兼容"解析"和"题目解析"） ==========
            explanation = ""
            for col_name in ["解析", "题目解析"]:
                val = row.get(col_name, "")
                if val:
                    explanation = val
                    break
           
            # ==========================================================

            # 收集所有非空选项（A~F）
            options = []
            for col in ["选项A", "选项B", "选项C", "选项D", "选项E", "选项F"]:
                opt = row.get(col, "").strip()
                if opt:
                    options.append(opt)

            if q_type == "判断题":
                options = ["对", "错"]
                if answer_raw.upper() not in ["A", "B"]:
                    continue
                answer = answer_raw.upper()
            else:
                answer = normalize_answer(answer_raw)
                if not answer:
                    continue
                if q_type == "单选题":
                    if len(answer) != 1 or answer not in "ABCDEF":
                        continue
                elif q_type == "多选题":
                    valid_letters = set(get_option_letter(i) for i in range(len(options)))
                    if not set(answer).issubset(valid_letters):
                        continue

            question = Question.create_from_excel_row(
                q_type=q_type,
                stem=stem,
                options=options,
                answer=answer,
                explanation=explanation,                
            )
            questions.append(question)

        return questions

    # ========== 从任意 JSON 路径 / 流加载、保存 ==========
    def load_from_json_file(self, source) -> List[Question]:
        """
        从指定来源加载完整题库
        :param source: JSON 文件路径（str），或任何支持 read() 的文件对象
        :return: 题目列表；若来源不存在或解析失败返回空列表
        """
        is_stream = hasattr(source, "read")
        if not is_stream and not os.path.exists(source):
            return []

        try:
            if is_stream:
                raw = source.read()
                text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
                data = json.loads(text)
            else:
                with open(source, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            if isinstance(data, list):
                return [Question.from_dict(item) for item in data]
            return []
        except Exception:
            return []

    def save_to_json_file(self, target, question_list: List[Question]) -> None:
        """
        将完整题库保存到指定目标
        :param target: JSON 文件路径（str），或任何支持 write() 的文件对象
        :param question_list: 题目列表
        """
        try:
            text = json.dumps(
                [q.to_dict() for q in question_list],
                ensure_ascii=False,
                indent=2,
            )

            if hasattr(target, "write"):
                # 文本流：直接写；二进制流（如 QFile）：编码后写
                try:
                    target.write(text)
                except TypeError:
                    target.write(text.encode("utf-8"))
                return

            # 本地路径
            dir_path = os.path.dirname(target)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f:
                f.write(text)
        except Exception as e:
            raise IOError(f"保存题库失败: {str(e)}")

    # ========== 默认路径的兼容方法（仅供旧代码调用） ==========
    def load_full_data(self, filename: str = "questions.json") -> List[Question]:
        """从默认路径加载（向后兼容）"""
        file_path = self._get_default_path(filename)
        return self.load_from_json_file(file_path)

    def save_full_data(self, question_list: List[Question], filename: str = "questions.json") -> None:
        """保存到默认路径（向后兼容）"""
        file_path = self._get_default_path(filename)
        self.save_to_json_file(file_path, question_list)

    # ========== 废弃方法 ==========
    def save_favorites(self, *args, **kwargs):
        pass

    def load_favorites(self, *args, **kwargs):
        return []

    def save_questions_to_json(self, *args, **kwargs):
        pass

    def load_questions_from_json(self, *args, **kwargs):
        return []
