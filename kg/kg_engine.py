"""
能化产业链知识图谱引擎
NetworkX (图遍历) + SQLite (持久化)
"""
import json
import sqlite3
import os
import networkx as nx
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set

DB_PATH = os.path.join(os.path.dirname(__file__), "kg.db")


# ═══════════════════════════════════════════════════════════
#  数据模型
# ═══════════════════════════════════════════════════════════

# 实体类型
ENTITY_TYPES = {
    "commodity": "品种",       # MA、EG、PX、PTA、PP、原油...
    "facility": "装置/工厂",   # 神华宁煤MTO、盛虹炼化...
    "port": "港口",           # 太仓、广东、宁波...
    "region": "区域",         # 内蒙、陕西、新疆...
    "event": "事件",          # 霍尔木兹海峡关闭、台风...
    "policy": "政策",         # 伊朗制裁、碳中和...
    "demand_sector": "需求端", # MTO、聚酯、甲醛...
    "feedstock": "原料",      # 煤、天然气、石脑油...
}

# 关系类型
RELATION_TYPES = {
    "UPSTREAM": "上游原料",
    "DOWNSTREAM": "下游产品",
    "SUBSTITUTE": "可替代",
    "PRODUCED_BY": "生产装置",
    "SHIPPED_VIA": "运输港口",
    "IMPACTED_BY": "受事件影响",
    "FEEDSTOCK": "原料供给",
    "COMPETES_WITH": "竞争关系",
    "PRODUCES": "生产",
    "LOCATED_IN": "所在地",
    "USES": "使用",
    "IMPACTS": "影响",
}


# ═══════════════════════════════════════════════════════════
#  SQLite 持久层
# ═══════════════════════════════════════════════════════════

def _init_db(conn: sqlite3.Connection):
    """初始化数据库表"""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS entities (
        entity_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        aliases TEXT,  -- JSON array
        attrs TEXT,    -- JSON dict
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS relations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        rel_type TEXT NOT NULL,
        weight REAL DEFAULT 1.0,
        attrs TEXT,  -- JSON dict
        source_from TEXT,  -- 来源：manual/report/news
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (source_id) REFERENCES entities(entity_id),
        FOREIGN KEY (target_id) REFERENCES entities(entity_id),
        UNIQUE(source_id, target_id, rel_type)
    );

    CREATE TABLE IF NOT EXISTS events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id TEXT,
        event_type TEXT,
        title TEXT,
        detail TEXT,
        impact_score REAL DEFAULT 0.5,
        occurred_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
    );

    CREATE INDEX IF NOT EXISTS idx_rel_source ON relations(source_id);
    CREATE INDEX IF NOT EXISTS idx_rel_target ON relations(target_id);
    CREATE INDEX IF NOT EXISTS idx_rel_type ON relations(rel_type);
    CREATE INDEX IF NOT EXISTS idx_entity_type ON entities(entity_type);
    CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_id);
    """)


# ═══════════════════════════════════════════════════════════
#  核心图谱类
# ═══════════════════════════════════════════════════════════

class KnowledgeGraph:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        _init_db(self.conn)
        self.graph = nx.DiGraph()
        self._load_graph()

    def _load_graph(self):
        """从SQLite加载图到内存"""
        # 加载实体
        rows = self.conn.execute("SELECT * FROM entities").fetchall()
        for r in rows:
            attrs = json.loads(r["attrs"]) if r["attrs"] else {}
            aliases = json.loads(r["aliases"]) if r["aliases"] else []
            self.graph.add_node(
                r["entity_id"],
                name=r["name"],
                entity_type=r["entity_type"],
                aliases=aliases,
                **attrs
            )
        # 加载关系
        rows = self.conn.execute("SELECT * FROM relations").fetchall()
        for r in rows:
            attrs = json.loads(r["attrs"]) if r["attrs"] else {}
            self.graph.add_edge(
                r["source_id"], r["target_id"],
                rel_type=r["rel_type"],
                weight=r["weight"],
                source_from=r["source_from"],
                **attrs
            )

    def close(self):
        self.conn.close()

    # ── 实体操作 ──────────────────────────────────────

    def add_entity(self, entity_id: str, name: str, entity_type: str,
                   aliases: list = None, attrs: dict = None) -> str:
        """添加实体"""
        aliases = aliases or []
        attrs = attrs or {}
        self.conn.execute(
            "INSERT OR REPLACE INTO entities (entity_id, name, entity_type, aliases, attrs, updated_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (entity_id, name, entity_type, json.dumps(aliases, ensure_ascii=False),
             json.dumps(attrs, ensure_ascii=False))
        )
        self.conn.commit()
        self.graph.add_node(entity_id, name=name, entity_type=entity_type,
                           aliases=aliases, **attrs)
        return entity_id

    def get_entity(self, entity_id: str) -> Optional[dict]:
        """获取实体"""
        if entity_id in self.graph:
            data = self.graph.nodes[entity_id]
            return {"entity_id": entity_id, **data}
        return None

    def find_entity(self, keyword: str) -> List[dict]:
        """按关键词搜索实体（名称/别名/ID）"""
        keyword_lower = keyword.lower()
        results = []
        for nid, data in self.graph.nodes(data=True):
            name = data.get("name", "")
            aliases = data.get("aliases", [])
            if (keyword_lower in name.lower() or
                keyword_lower in nid.lower() or
                any(keyword_lower in a.lower() for a in aliases)):
                results.append({"entity_id": nid, **data})
        return results

    # ── 关系操作 ──────────────────────────────────────

    def add_relation(self, source_id: str, target_id: str, rel_type: str,
                     weight: float = 1.0, attrs: dict = None,
                     source_from: str = "manual") -> bool:
        """添加关系"""
        if source_id not in self.graph or target_id not in self.graph:
            return False
        attrs = attrs or {}
        self.conn.execute(
            "INSERT OR REPLACE INTO relations (source_id, target_id, rel_type, weight, attrs, source_from) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (source_id, target_id, rel_type, weight,
             json.dumps(attrs, ensure_ascii=False), source_from)
        )
        self.conn.commit()
        self.graph.add_edge(source_id, target_id, rel_type=rel_type,
                           weight=weight, source_from=source_from, **attrs)
        return True

    # ── 图查询 ──────────────────────────────────────

    def get_neighbors(self, entity_id: str, direction: str = "both",
                      rel_type: str = None) -> List[dict]:
        """获取邻居节点"""
        results = []
        if direction in ("out", "both"):
            for _, target, data in self.graph.out_edges(entity_id, data=True):
                if rel_type and data.get("rel_type") != rel_type:
                    continue
                node = self.graph.nodes[target]
                results.append({
                    "entity_id": target,
                    "relation": data.get("rel_type"),
                    "direction": "out",
                    "weight": data.get("weight", 1.0),
                    **node
                })
        if direction in ("in", "both"):
            for source, _, data in self.graph.in_edges(entity_id, data=True):
                if rel_type and data.get("rel_type") != rel_type:
                    continue
                node = self.graph.nodes[source]
                results.append({
                    "entity_id": source,
                    "relation": data.get("rel_type"),
                    "direction": "in",
                    "weight": data.get("weight", 1.0),
                    **node
                })
        return results

    def get_chain(self, entity_id: str, direction: str = "downstream",
                  max_depth: int = 5) -> List[List[dict]]:
        """获取产业链链路"""
        chain = []
        visited = set()

        def _walk(current, depth):
            if depth > max_depth or current in visited:
                return
            visited.add(current)
            if direction == "downstream":
                edges = self.graph.out_edges(current, data=True)
            else:
                edges = self.graph.in_edges(current, data=True)

            for _, target, data in edges:
                rel = data.get("rel_type", "")
                if direction == "downstream" and rel not in ("DOWNSTREAM", "PRODUCES", "USES"):
                    continue
                if direction == "upstream" and rel not in ("UPSTREAM", "FEEDSTOCK"):
                    continue
                node = self.graph.nodes[target]
                chain.append([{
                    "from": current,
                    "to": target,
                    "relation": rel,
                    "name": node.get("name", target),
                    "type": node.get("entity_type", ""),
                }])
                _walk(target, depth + 1)

        _walk(entity_id, 0)
        return chain

    def trace_impact(self, event_id: str, max_depth: int = 4) -> List[dict]:
        """追踪事件影响路径"""
        paths = []

        def _bfs(start, depth):
            if depth > max_depth:
                return
            for _, target, data in self.graph.out_edges(start, data=True):
                rel = data.get("rel_type", "")
                if rel not in ("IMPACTS", "IMPACTED_BY", "DOWNSTREAM", "UPSTREAM"):
                    continue
                node = self.graph.nodes[target]
                paths.append({
                    "step": depth + 1,
                    "from": start,
                    "to": target,
                    "relation": rel,
                    "target_name": node.get("name", target),
                    "target_type": node.get("entity_type", ""),
                })
                _bfs(target, depth + 1)

        _bfs(event_id, 0)
        return paths

    def find_path(self, source_id: str, target_id: str,
                  max_length: int = 6) -> Optional[List[dict]]:
        """查找两点间最短路径"""
        try:
            # NetworkX 3.x 移除了 cutoff 参数，手动限制深度
            path = nx.shortest_path(self.graph.to_undirected(),
                                   source=source_id, target=target_id)
            if len(path) - 1 > max_length:
                # 路径太长，用 BFS 限制深度
                queue = [(source_id, [source_id])]
                visited = {source_id}
                path = None
                while queue:
                    current, p = queue.pop(0)
                    if len(p) - 1 > max_length:
                        continue
                    if current == target_id:
                        path = p
                        break
                    for neighbor in self.graph.to_undirected()[current]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append((neighbor, p + [neighbor]))
                if path is None:
                    return None

            result = []
            for i in range(len(path) - 1):
                data = self.graph.get_edge_data(path[i], path[i + 1]) or \
                       self.graph.get_edge_data(path[i + 1], path[i]) or {}
                node = self.graph.nodes[path[i + 1]]
                result.append({
                    "from": path[i],
                    "to": path[i + 1],
                    "relation": data.get("rel_type", "unknown"),
                    "name": node.get("name", path[i + 1]),
                })
            return result
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def find_substitutes(self, entity_id: str) -> List[dict]:
        """查找可替代品种"""
        results = []
        for _, target, data in self.graph.out_edges(entity_id, data=True):
            if data.get("rel_type") == "SUBSTITUTE":
                node = self.graph.nodes[target]
                results.append({"entity_id": target, **node})
        for source, _, data in self.graph.in_edges(entity_id, data=True):
            if data.get("rel_type") == "SUBSTITUTE":
                node = self.graph.nodes[source]
                results.append({"entity_id": source, **node})
        return results

    def find_affected_by(self, keyword: str) -> List[dict]:
        """查找受某事件/政策影响的品种"""
        affected = []
        entities = self.find_entity(keyword)
        for ent in entities:
            eid = ent["entity_id"]
            # 正向：事件→品种
            for _, target, data in self.graph.out_edges(eid, data=True):
                if data.get("rel_type") in ("IMPACTS", "IMPACTED_BY"):
                    node = self.graph.nodes[target]
                    affected.append({
                        "entity_id": target,
                        "name": node.get("name", target),
                        "type": node.get("entity_type", ""),
                        "via": data.get("rel_type"),
                    })
            # 反向：品种→事件
            for source, _, data in self.graph.in_edges(eid, data=True):
                if data.get("rel_type") in ("IMPACTS", "IMPACTED_BY"):
                    node = self.graph.nodes[source]
                    affected.append({
                        "entity_id": source,
                        "name": node.get("name", source),
                        "type": node.get("entity_type", ""),
                        "via": data.get("rel_type"),
                    })
        return affected

    # ── 统计 ──────────────────────────────────────

    def stats(self) -> dict:
        """图谱统计"""
        entity_counts = {}
        for _, data in self.graph.nodes(data=True):
            t = data.get("entity_type", "unknown")
            entity_counts[t] = entity_counts.get(t, 0) + 1

        rel_counts = {}
        for _, _, data in self.graph.edges(data=True):
            r = data.get("rel_type", "unknown")
            rel_counts[r] = rel_counts.get(r, 0) + 1

        return {
            "total_entities": self.graph.number_of_nodes(),
            "total_relations": self.graph.number_of_edges(),
            "entity_types": entity_counts,
            "relation_types": rel_counts,
        }

    def export_mermaid(self, max_nodes: int = 30) -> str:
        """导出 Mermaid 图谱可视化"""
        lines = ["graph LR"]
        node_map = {}
        idx = 0

        for nid, data in self.graph.nodes(data=True):
            if idx >= max_nodes:
                break
            name = data.get("name", nid)
            ntype = data.get("entity_type", "")
            label = f"{name}"
            node_map[nid] = f"N{idx}"
            shape = {"commodity": "([{}])", "event": "{{{{{}}}}}",
                     "facility": "[[{}]]", "policy": "{{{{{}}}}}"}.get(ntype, "({})")
            lines.append(f"  N{idx}{shape.format(label)}")
            idx += 1

        for u, v, data in self.graph.edges(data=True):
            if u in node_map and v in node_map:
                rel = data.get("rel_type", "")
                lines.append(f"  {node_map[u]} -->|{rel}| {node_map[v]}")

        return "\n".join(lines)
