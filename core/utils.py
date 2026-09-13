# utils.py
# 工具函数模块：提供ID生成、答案标准化、判断题映射、选项字母辅助

import hashlib
from typing import List

def generate_question_id(stem: str, options: List[str]) -> str:
    """
    根据题干和选项文本生成确定性8位十六进制ID
    :param stem: 题干字符串
    :param options: 选项列表（可能包含空字符串）
    :return: 8位十六进制字符串
    """
    # 拼接题干和所有选项（过滤空选项，但保留顺序）
    combined = stem + "|" + "|".join(options)
    # 使用md5生成哈希
    hash_obj = hashlib.md5(combined.encode('utf-8'))
    hex_digest = hash_obj.hexdigest()
    # 取前8位
    return hex_digest[:8]

def normalize_answer(raw: str) -> str:
    """
    清洗答案字符串：去除分隔符，仅保留字母，转大写，排序并去重
    :param raw: 原始答案字符串，如 "A, B, C" 或 "AB"
    :return: 标准化后的答案，如 "ABC"
    """
    if not raw:
        return ""
    # 常见分隔符
    separators = [",", ";", "|", " ", "\t", "，", "；"]
    cleaned = raw.upper()
    for sep in separators:
        cleaned = cleaned.replace(sep, "")
    # 仅保留字母
    cleaned = ''.join(filter(str.isalpha, cleaned))
    # 去重并排序
    unique = sorted(set(cleaned))
    return ''.join(unique)

def map_judgment(letter: str) -> str:
    """
    将答案字母 A/B 映射为中文“对”/“错”
    :param letter: 大写字母 'A' 或 'B'
    :return: '对' 或 '错'
    """
    if letter.upper() == 'A':
        return "对"
    elif letter.upper() == 'B':
        return "错"
    else:
        return letter  # 降级

def get_option_letter(index: int) -> str:
    """
    根据索引返回对应的选项字母（0→A, 1→B ... 5→F）
    :param index: 0~5
    :return: 大写字母
    """
    if 0 <= index <= 5:
        return chr(ord('A') + index)
    else:
        raise ValueError("索引必须在0~5之间")