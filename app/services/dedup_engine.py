"""
Jaccard Semantic Dedup Engine — duMem 语义去重
判断新内容是否与已有记忆重复，阈值 0.85
不调用 embedding，纯词语集合比较
"""
import re
from typing import List, Set


def _tokenize(text: str) -> Set[str]:
    """中英文混合分词，转小写"""
    text = text.lower()
    tokens = re.sub(r'[^\w\s]', ' ', text).split()
    chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
    for chars in chinese_chars:
        for i in range(len(chars) - 1):
            tokens.append(chars[i:i+2])
    return set(tokens)


def jaccard_sim(set_a: Set[str], set_b: Set[str]) -> float:
    """Jaccard 相似度 = |A∩B| / |A∪B|"""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def is_duplicate(
    new_content: str,
    existing_contents: List[str],
    threshold: float = 0.85,
) -> bool:
    """
    判断 new_content 是否与 existing_contents 中的任一内容重复
    threshold: Jaccard > threshold → 判定为重复
    返回 True = 重复，应跳过归档
    """
    if not new_content or not new_content.strip():
        return True

    new_tokens = _tokenize(new_content)
    if not new_tokens:
        return True

    for exist in existing_contents:
        if not exist:
            continue
        exist_tokens = _tokenize(exist)
        sim = jaccard_sim(new_tokens, exist_tokens)
        if sim > threshold:
            return True
    return False


def find_duplicates(
    contents: List[str],
    threshold: float = 0.85,
) -> List[List[int]]:
    """找出所有重复内容组"""
    n = len(contents)
    groups = []
    used = set()

    for i in range(n):
        if i in used:
            continue
        group = [i]
        for j in range(i + 1, n):
            if j in used:
                continue
            sim = jaccard_sim(_tokenize(contents[i]), _tokenize(contents[j]))
            if sim > threshold:
                group.append(j)
                used.add(j)
        if len(group) > 1:
            groups.append(group)
            for idx in group:
                used.add(idx)

    return groups


def dedup_report(contents: List[str], titles: List[str]) -> dict:
    """生成去重报告"""
    groups = find_duplicates(contents)
    total_deduped = sum(len(g) - 1 for g in groups)
    return {
        "total_memories": len(contents),
        "duplicate_groups": len(groups),
        "total_deduped": total_deduped,
        "groups": [
            {
                "indices": g,
                "titles": [titles[i] if i < len(titles) else "" for i in g],
            }
            for g in groups
        ],
    }
