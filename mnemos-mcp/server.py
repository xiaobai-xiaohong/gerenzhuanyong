"""
MCP Server — 将 MnemOS 封装为标准 MCP 工具
让 Hermes 等支持 MCP 的 Agent 直接调用记忆系统
"""
import json
import sys
import asyncio
from typing import Any, Dict, List, Optional

# MCP 工具定义
TOOLS = [
    {
        "name": "mnemosyne_archive",
        "description": "归档一条记忆到永久记忆库。支持7类记忆：W铁律/K工具/I人物/D对话/E踩坑/R反思/S研究",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要归档的记忆内容"
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["W", "K", "I", "D", "E", "R", "S"],
                    "default": "D",
                    "description": "记忆类型"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "mnemosyne_search",
        "description": "从永久记忆库中检索相关知识与历史经验",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词或问题描述"
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "description": "返回结果数量"
                },
                "depth": {
                    "type": "string",
                    "enum": ["auto", "L0", "L1", "L2"],
                    "default": "auto",
                    "description": "检索深度"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "mnemosyne_inject",
        "description": "获取相关记忆上下文，用于注入到LLM对话中",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "当前对话主题或问题"
                },
                "top_k": {
                    "type": "integer",
                    "default": 3,
                    "description": "注入的记忆数量"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "mnemosyne_feedback",
        "description": "对记忆提供反馈，更新Trust评分",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "记忆ID"
                },
                "helpful": {
                    "type": "boolean",
                    "description": "是否有帮助"
                }
            },
            "required": ["memory_id", "helpful"]
        }
    },
    {
        "name": "mnemosyne_stats",
        "description": "获取记忆系统统计信息",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


class MnemosyneMCPServer:
    """MCP 协议服务端"""

    def __init__(self, base_url: str = "http://127.0.0.1:8010", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理 MCP 请求"""
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        if method == "initialize":
            return self._response(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mnemosyne", "version": "6.0.0"}
            })
        elif method == "tools/list":
            return self._response(req_id, {"tools": TOOLS})
        elif method == "tools/call":
            result = await self._call_tool(params.get("name"), params.get("arguments", {}))
            return self._response(req_id, result)
        elif method == "ping":
            return self._response(req_id, {})
        else:
            return self._error(req_id, -32601, f"Method not found: {method}")

    async def _call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """调用 MCP 工具"""
        import httpx

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        async with httpx.AsyncClient(timeout=30.0) as client:
            if name == "mnemosyne_archive":
                resp = await client.post(
                    f"{self.base_url}/api/v5/memory/archive",
                    json={
                        "content": args["content"],
                        "memory_type": args.get("memory_type", "D"),
                        "tags": args.get("tags"),
                    },
                    headers=headers,
                )
                data = resp.json()
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(data, ensure_ascii=False, indent=2)
                    }]
                }

            elif name == "mnemosyne_search":
                resp = await client.post(
                    f"{self.base_url}/api/v5/memory/search",
                    json={
                        "query": args["query"],
                        "top_k": args.get("top_k", 5),
                        "depth": args.get("depth", "auto"),
                    },
                    headers=headers,
                )
                data = resp.json()
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(data, ensure_ascii=False, indent=2)
                    }]
                }

            elif name == "mnemosyne_inject":
                import urllib.parse
                resp = await client.post(
                    f"{self.base_url}/api/v5/memory/inject?query={urllib.parse.quote(args['query'])}&top_k={args.get('top_k', 3)}",
                    headers=headers,
                )
                data = resp.json()
                return {
                    "content": [{
                        "type": "text",
                        "text": data.get("data", {}).get("context", "")
                    }]
                }

            elif name == "mnemosyne_feedback":
                resp = await client.post(
                    f"{self.base_url}/api/v5/memory/feedback?memory_id={args['memory_id']}&helpful={str(args['helpful']).lower()}",
                    headers=headers,
                )
                data = resp.json()
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(data, ensure_ascii=False, indent=2)
                    }]
                }

            elif name == "mnemosyne_stats":
                resp = await client.get(
                    f"{self.base_url}/api/v5/memory/trust-stats",
                    headers=headers,
                )
                data = resp.json()
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(data, ensure_ascii=False, indent=2)
                    }]
                }

            else:
                return {
                    "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True
                }

    def _response(self, req_id: Any, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _error(self, req_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


async def main():
    """启动 MCP 服务器（stdio 模式）"""
    import os
    base_url = os.getenv("MNEMOSYNE_URL", "http://127.0.0.1:8010")
    api_key = os.getenv("MNEMOSYNE_API_KEY", "")

    server = MnemosyneMCPServer(base_url, api_key)

    # 从 stdin 读取请求，写入 stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = await server.handle_request(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            error_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
            print(json.dumps(error_resp), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
