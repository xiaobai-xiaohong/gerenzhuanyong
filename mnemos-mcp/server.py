#!/usr/bin/env python3
"""
MnemOS v6.0 MCP Server — stdio transport
=========================================
Exposes MnemOS memory/recall/feedback/health as MCP tools to any MCP client.

Tools
-----
  mnemos_health        GET  /api/v5/health/full
  mnemos_search        POST /api/v5/memory/search
  mnemos_memories      GET  /api/v5/memory/trust-stats
  mnemos_feedback      POST /api/v5/memory/feedback

Config (config.yaml)
--------------------
  mcp_servers:
    mnemos:
      command: python
      args: [C:/Users/Administrator/gerenzhuanyong/mnemos-mcp/server.py]
      timeout: 60

Transport: stdio (JSON-RPC over stdin/stdout)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# MnemOS API client
# ---------------------------------------------------------------------------

MNEMOS_BASE = os.environ.get("MNEMOS_BASE_URL", "http://localhost:8010")
TIMEOUT = int(os.environ.get("MNEMOS_TIMEOUT", "30"))


def _mnemos_get(path: str) -> Dict[str, Any]:
    url = f"{MNEMOS_BASE}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return json.loads(body)
        except Exception:
            return {"error": f"HTTP {e.code}", "detail": body}
    except Exception as e:
        return {"error": str(e)}


def _mnemos_post(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{MNEMOS_BASE}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return json.loads(body)
        except Exception:
            return {"error": f"HTTP {e.code}", "detail": body}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

try:
    from mcp.server.fastmcp import FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False


def create_server() -> "FastMCP":
    if not FASTMCP_AVAILABLE:
        raise ImportError(
            "FastMCP not available. "
            "Install with: pip install 'mcp[server]' "
            "or use the hermes venv python."
        )

    mcp = FastMCP(
        "mnemos",
        instructions=(
            "MnemOS v6.0 memory system. Stores, retrieves, and quality-scores "
            "persistent agent memories with trust scoring, semantic deduplication, "
            "and half-life decay. Base URL: http://localhost:8010"
        ),
    )

    # -------------------------------------------------------------------------
    # Tool: mnemos_health
    # -------------------------------------------------------------------------
    @mcp.tool(
        title="MnemOS Health",
        description=(
            "Check MnemOS v6.0 health status, version, active features, "
            "and memory statistics (total, avg_trust, type_distribution)."
        ),
    )
    def mnemos_health() -> str:
        """Poll the /api/v5/health/full endpoint."""
        result = _mnemos_get("/api/v5/health/full")
        if "error" in result:
            return json.dumps({"success": False, "error": result["error"]}, indent=2)
        data = result.get("data", {})
        return json.dumps(
            {
                "success": True,
                "version": data.get("version"),
                "features": data.get("features", []),
                "memory_stats": data.get("memory_stats", {}),
                "status": data.get("status"),
            },
            indent=2,
            ensure_ascii=False,
        )

    # -------------------------------------------------------------------------
    # Tool: mnemos_search
    # -------------------------------------------------------------------------
    @mcp.tool(
        title="MnemOS Search",
        description=(
            "Search long-term memory using semantic vector similarity across "
            "three recall depths: L0 (fast, ~3 results), L1 (medium, ~5 results), "
            "L2 (deep, ~10 results). Returns memory_id, title, summary, content_type, "
            "trust_score, memory_type, final_score, and decay_at. "
            "Set depth='auto' for automatic depth selection."
        ),
    )
    def mnemos_search(
        query: str,
        depth: str = "auto",
        top_k: int = 5,
    ) -> str:
        """
        Search MnemOS memories.

        Args:
            query: Natural-language search query.
            depth: 'auto' | 'L0' | 'L1' | 'L2'. L0=fresh session, L1=recent, L2=archival.
            top_k: Number of results to return (default 5).
        """
        body = {"query": query, "depth": depth, "top_k": top_k}
        result = _mnemos_post("/api/v5/memory/search", body)
        if "error" in result:
            return json.dumps({"success": False, "error": result["error"]}, indent=2)
        data = result.get("data", {})
        outputs = []
        for r in data.get("results", []):
            outputs.append(
                {
                    "memory_id": r.get("memory_id"),
                    "title": r.get("title", "")[:120],
                    "summary": r.get("summary", "")[:300],
                    "content_type": r.get("content_type"),
                    "memory_type": r.get("memory_type"),
                    "trust_score": r.get("trust_score"),
                    "final_score": round(r.get("final_score", 0), 4),
                    "decay_at": r.get("decay_at"),
                }
            )
        return json.dumps(
            {
                "success": True,
                "depth_used": data.get("depth_used"),
                "total": data.get("total"),
                "results": outputs,
            },
            indent=2,
            ensure_ascii=False,
        )

    # -------------------------------------------------------------------------
    # Tool: mnemos_memories
    # -------------------------------------------------------------------------
    @mcp.tool(
        title="MnemOS Memory Stats",
        description=(
            "Retrieve memory quality statistics: total count, average trust score, "
            "low-trust count (below 0.2 threshold), memory type distribution, "
            "and the current trust threshold."
        ),
    )
    def mnemos_memories() -> str:
        """Get MnemOS memory statistics and trust breakdown."""
        result = _mnemos_get("/api/v5/memory/trust-stats")
        if "error" in result:
            return json.dumps({"success": False, "error": result["error"]}, indent=2)
        data = result.get("data", {})
        return json.dumps(
            {
                "success": True,
                "total": data.get("total"),
                "avg_trust": data.get("avg_trust"),
                "low_trust_count": data.get("low_trust_count"),
                "type_distribution": data.get("type_distribution", {}),
                "threshold_blacklist": data.get("threshold_blacklist"),
            },
            indent=2,
            ensure_ascii=False,
        )

    # -------------------------------------------------------------------------
    # Tool: mnemos_feedback
    # -------------------------------------------------------------------------
    @mcp.tool(
        title="MnemOS Feedback",
        description=(
            "Submit helpful/unhelpful feedback for a memory to update its trust score. "
            "Uses Bayesian smoothing: helpful=true increments count and raises trust toward 1.0; "
            "helpful=false decrements and penalizes toward 0.0. "
            "Returns the new_trust, delta, and updated counts."
        ),
    )
    def mnemos_feedback(
        memory_id: str,
        helpful: bool,
    ) -> str:
        """
        Submit feedback for a memory entry.

        Args:
            memory_id: The memory identifier (e.g. mem_xxxx).
            helpful: True if this memory was useful; False if it was harmful or wrong.
        """
        path = f"/api/v5/memory/feedback?memory_id={memory_id}&helpful={'true' if helpful else 'false'}"
        result = _mnemos_post(path, {})
        if "error" in result:
            return json.dumps({"success": False, "error": result["error"]}, indent=2)
        data = result.get("data", {})
        return json.dumps(
            {
                "success": True,
                "memory_id": data.get("memory_id"),
                "new_trust": data.get("new_trust"),
                "delta": data.get("delta"),
                "helpful": data.get("helpful"),
                "total_helpful": data.get("total_helpful"),
                "total_unhelpful": data.get("total_unhelpful"),
            },
            indent=2,
            ensure_ascii=False,
        )

    return mcp


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--get-version":
        print("1.0.0")
        sys.exit(0)

    if not FASTMCP_AVAILABLE:
        print(
            "ERROR: FastMCP (mcp[server]) is not installed. "
            "Run: pip install 'mcp[server]'",
            file=sys.stderr,
        )
        sys.exit(1)

    server = create_server()
    server.run(transport="stdio")
