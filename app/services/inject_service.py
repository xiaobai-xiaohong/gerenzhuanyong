"""
Inject Service — pre-LLM context injection
对标 duMem mem0-inject.sh：query → Social Closer过滤 → Trust过滤 → top-K检索 → L0注入
"""
from app.services.social_closer import is_social_closer
from app.services.search_service import SearchService

MEMORY_TYPE_LABELS = {
    "W": "【铁律】",
    "K": "【工具】",
    "I": "【人物】",
    "D": "【对话】",
    "E": "【踩坑】",
    "R": "【反思】",
    "S": "【研究】",
}

L0_SUMMARY_MAX_CHARS = 200


def _format_memory_for_inject(result: dict, depth: str) -> str:
    mem_type = result.get("memory_type", "D")
    label = MEMORY_TYPE_LABELS.get(mem_type, "【记忆】")
    title = result.get("title", "")
    summary = result.get("summary", "")

    if depth == "L0":
        content = summary[:L0_SUMMARY_MAX_CHARS]
    else:
        content = summary

    trust = result.get("trust_score", 0.0)
    score = result.get("final_score", 0.0)
    return f"{label}[{mem_type}] {title}\n{content}\n(t={trust:.2f}, s={score:.2f})"


class InjectService:
    def __init__(self, db):
        self.db = db

    async def inject(
        self,
        query: str,
        depth: str = "auto",
        top_k: int = 5,
        tenant_id: str = "default",
    ) -> dict:
        filters_applied = []

        # Social Closer 检查
        if is_social_closer(query):
            return {
                "injected_context": "",
                "memory_count": 0,
                "depth_used": "L0",
                "filters_applied": ["social_closer_skip"],
                "query_valid": False,
            }

        # 执行检索
        search = SearchService(self.db)
        depth_used, results = await search.search(
            query=query,
            depth=depth,
            top_k=top_k,
            tenant_id=tenant_id,
        )

        injected_memories = []
        for r in results:
            trust = r.get("trust_score", 0.0)
            if trust < 0.2:
                filters_applied.append(f"trust_skip_{r['memory_id']}")
                continue
            line = _format_memory_for_inject(r, depth_used)
            injected_memories.append(line)

        if injected_memories:
            header = "【相关记忆】\n" + "=" * 40 + "\n"
            footer = "=" * 40 + "\n【记忆结束】"
            injected_context = header + "\n\n".join(injected_memories) + "\n" + footer
        else:
            injected_context = ""
            filters_applied.append("no_relevant_memories")

        if depth_used == "L0":
            token_note = "L0省约55%token"
        elif depth_used == "L1":
            token_note = "L1省约30%token"
        else:
            token_note = "L2全文模式"

        return {
            "injected_context": injected_context,
            "memory_count": len(injected_memories),
            "depth_used": depth_used,
            "filters_applied": filters_applied,
            "query_valid": True,
            "token_note": token_note,
        }

    async def inject_context(
        self,
        query: str,
        depth: str = "L0",
        top_k: int = 5,
        tenant_id: str = "default",
    ) -> dict:
        """返回格式化的注入上下文（API 用）"""
        result = await self.inject(query, depth, top_k, tenant_id)
        return {
            "context": result["injected_context"],
            "memory_count": result["memory_count"],
            "depth_used": result["depth_used"],
            "query_valid": result["query_valid"],
        }
