"""
LLM Service — 调用 LLM 提取对话中的关键事实
支持 DeepSeek / OpenAI 兼容 API
"""
import json
import logging
from typing import List, Optional
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("mnemosyne.llm")

EXTRACT_PROMPT = """从以下对话中提取关键事实，返回 JSON 数组。
每个事实包含：
- content: 事实内容（一句话，50-200字）
- memory_type: 类型（W铁律/K工具/I人物/D对话/E踩坑/R反思/S研究）
- tags: 标签数组（1-3个）

规则：
1. 只提取可操作的事实，跳过闲聊
2. 踩坑记录要包含错误和解决方案
3. 铁律是不可违反的规则
4. 不确定的标记为 D（对话）

对话内容：
{content}

返回格式（纯 JSON，不要 markdown）：
[
  {{"content": "...", "memory_type": "K", "tags": ["docker", "部署"]}}
]"""


class LLMService:
    def __init__(self):
        self._api_key = settings.llm_api_key
        self._base_url = settings.llm_base_url.rstrip("/")
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens

    @property
    def available(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    async def extract_facts(self, content: str) -> List[dict]:
        """从对话内容中提取关键事实"""
        if not self.available:
            logger.warning("[LLM] API key not configured, skipping extraction")
            return []

        import httpx
        prompt = EXTRACT_PROMPT.format(content=content[:8000])

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                proxy=None,
                trust_env=False,
            ) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": self._max_tokens,
                        "temperature": 0.1,
                    },
                )
                if resp.status_code != 200:
                    logger.warning(f"[LLM] API error: {resp.status_code}")
                    return []

                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                # 清理 markdown 代码块
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text.rsplit("```", 1)[0]
                text = text.strip()

                facts = json.loads(text)
                if isinstance(facts, list):
                    logger.warning(f"[LLM] Extracted {len(facts)} facts")
                    return facts
                return []
        except Exception as e:
            logger.warning(f"[LLM] Extraction failed: {e}")
            return []


llm_service = LLMService()
