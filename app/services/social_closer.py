"""
Social Closer Filter — duMem 废话过滤
过滤 ok👍yesno 等无意义内容，不调用 embedding，节省 API 调用
"""
import re


def _is_emoji_char(c: str) -> bool:
    """精准判断单个字符是否为 emoji"""
    o = ord(c)
    return (
        0x2600 <= o <= 0x27FF
        or 0x1F000 <= o <= 0x1FFFF
        or 0x2300 <= o <= 0x23FF
        or 0x2700 <= o <= 0x27BF
    )


def is_social_closer(text: str) -> bool:
    """
    判断一段文本是否为"社交结束语"（无意义废话）
    返回 True = 应该跳过（不归档/不embedding）
    """
    if not text:
        return True

    stripped = text.strip()
    if not stripped:
        return True

    lower = stripped.lower()

    # 规则1: 纯单字或单符号（≤2字符）
    if len(stripped) <= 2:
        return True

    # 规则2: 全文本为 emoji
    if all(_is_emoji_char(c) for c in stripped):
        return True

    # 规则3: 废话关键词列表
    noise_phrases = {
        "ok", "okay", "okk", "okkk",
        "好", "好的", "好哒", "好嘞",
        "是的", "嗯", "嗯嗯", "嗯呐",
        "thanks", "thank you", "thx", "ty",
        "please", "pls", "plz",
        "ngl", "tbh", "imo", "imho",
        "got it", "gotcha", "g",
        "no", "yes", "yeah", "yep", "nope",
        "👍", "👎", "👏", "🙌", "🙏",
        "100", "666", "88", "bx",
        "辛苦了", "谢谢", "么么", "笔芯",
    }
    if lower in noise_phrases:
        return True

    # 规则4: 纯标点符号
    if re.match(r'^[\s\W]+$', stripped):
        return True

    return False


def strip_social_closer(content: str) -> str:
    """从长文本中移除末尾的社交结束语部分"""
    lines = content.strip().split('\n')
    filtered_lines = []
    for line in lines:
        if is_social_closer(line):
            continue
        filtered_lines.append(line)
    return '\n'.join(filtered_lines).strip()
