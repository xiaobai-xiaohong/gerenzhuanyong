"""
MnemOS Python SDK — 简化记忆系统调用
一行代码归档、检索、注入记忆
"""
import json
from typing import List, Optional, Dict, Any

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False
    import urllib.request
    import urllib.parse


class MnemosyneClient:
    """MnemOS 客户端"""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8010",
        api_key: str = "",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["x-api-key"] = self.api_key
        return h

    # ── 同步 API ──────────────────────────────────────────────────────────────

    def archive(
        self,
        content: str,
        memory_type: str = "D",
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """归档一条记忆"""
        data = {"content": content, "memory_type": memory_type}
        if tags:
            data["tags"] = tags
        if category:
            data["category"] = category
        return self._post("/api/v5/memory/archive", data)

    def search(
        self,
        query: str,
        top_k: int = 5,
        depth: str = "auto",
    ) -> Dict[str, Any]:
        """语义检索"""
        return self._post("/api/v5/memory/search", {
            "query": query, "top_k": top_k, "depth": depth
        })

    def inject(
        self,
        query: str,
        top_k: int = 3,
        depth: str = "L0",
    ) -> str:
        """获取注入上下文（直接返回格式化文本）"""
        result = self._post(
            f"/api/v5/memory/inject?query={urllib.parse.quote(query)}&top_k={top_k}&depth={depth}",
            method="POST"
        )
        return result.get("data", {}).get("context", "")

    def feedback(self, memory_id: str, helpful: bool) -> Dict[str, Any]:
        """Trust 反馈"""
        return self._post(
            f"/api/v5/memory/feedback?memory_id={memory_id}&helpful={str(helpful).lower()}",
            method="POST"
        )

    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._get("/api/v5/memory/trust-stats")

    def health(self) -> Dict[str, Any]:
        """健康检查"""
        return self._get("/health")

    def extract(
        self,
        content: str,
        memory_type: str = "D",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """LLM 提取事实"""
        url = f"/api/v5/memory/extract?content={urllib.parse.quote(content)}&memory_type={memory_type}"
        if tags:
            url += f"&tags={','.join(tags)}"
        return self._post(url, method="POST")

    # ── 内部方法 ──────────────────────────────────────────────────────────────

    def _get(self, path: str) -> Dict[str, Any]:
        url = self.base_url + path
        if _HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.get(url, headers=self._headers())
                return r.json()
        else:
            req = urllib.request.Request(url, headers=self._headers())
            return json.loads(urllib.request.urlopen(req, timeout=self.timeout).read())

    def _post(self, path: str, data: Any = None, method: str = "POST") -> Dict[str, Any]:
        url = self.base_url + path
        body = json.dumps(data).encode() if data else None
        if _HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.request(method, url, content=body, headers=self._headers())
                return r.json()
        else:
            req = urllib.request.Request(url, data=body, headers=self._headers(), method=method)
            return json.loads(urllib.request.urlopen(req, timeout=self.timeout).read())


# ── 便捷函数 ──────────────────────────────────────────────────────────────

_client: Optional[MnemosyneClient] = None


def init(base_url: str = "http://127.0.0.1:8010", api_key: str = "") -> MnemosyneClient:
    """初始化全局客户端"""
    global _client
    _client = MnemosyneClient(base_url, api_key)
    return _client


def archive(content: str, memory_type: str = "D", **kwargs) -> Dict[str, Any]:
    """归档记忆（便捷函数）"""
    return _get_client().archive(content, memory_type, **kwargs)


def search(query: str, top_k: int = 5, **kwargs) -> Dict[str, Any]:
    """检索记忆（便捷函数）"""
    return _get_client().search(query, top_k, **kwargs)


def inject(query: str, **kwargs) -> str:
    """获取注入上下文（便捷函数）"""
    return _get_client().inject(query, **kwargs)


def _get_client() -> MnemosyneClient:
    global _client
    if _client is None:
        _client = MnemosyneClient()
    return _client
