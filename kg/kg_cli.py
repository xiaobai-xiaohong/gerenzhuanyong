"""
知识图谱 CLI 接口
用法:
  python kg_cli.py stats                    # 图谱统计
  python kg_cli.py chain MA                 # 产业链查询
  python kg_cli.py upstream MA              # 上游链路
  python kg_cli.py downstream MA            # 下游链路
  python kg_cli.py neighbors MA             # 邻居节点
  python kg_cli.py impact "霍尔木兹海峡"     # 事件影响追踪
  python kg_cli.py path MA EG               # 两品种间路径
  python kg_cli.py substitutes EG           # 替代品种
  python kg_cli.py search 甲醇              # 搜索实体
  python kg_cli.py affected "台风"          # 受影响品种
  python kg_cli.py mermaid                  # 导出Mermaid图
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from kg_engine import KnowledgeGraph


def fmt_entity(e: dict) -> str:
    """格式化实体"""
    name = e.get("name", e.get("entity_id", "?"))
    etype = e.get("entity_type", "")
    return f"{name}({etype})"


def cmd_stats(kg):
    s = kg.stats()
    print(f"📊 知识图谱统计")
    print(f"  实体总数: {s['total_entities']}")
    print(f"  关系总数: {s['total_relations']}")
    print(f"\n  实体类型:")
    for t, c in sorted(s['entity_types'].items()):
        print(f"    {t}: {c}")
    print(f"\n  关系类型:")
    for t, c in sorted(s['relation_types'].items()):
        print(f"    {t}: {c}")


def cmd_chain(kg, entity_id: str, direction: str = "both"):
    """产业链查询"""
    # 先搜索
    entities = kg.find_entity(entity_id)
    if not entities:
        print(f"❌ 未找到: {entity_id}")
        return
    target = entities[0]
    eid = target["entity_id"]
    print(f"🔗 {target['name']} 产业链\n")

    if direction in ("downstream", "both"):
        print("▼ 下游产品:")
        chain = kg.get_chain(eid, "downstream")
        for level in chain:
            for item in level:
                print(f"  {item['name']} --[{item['relation']}]--> ", end="")
            print()
        if not chain:
            print("  (无)")

    if direction in ("upstream", "both"):
        print("\n▲ 上游原料:")
        chain = kg.get_chain(eid, "upstream")
        for level in chain:
            for item in level:
                print(f"  {item['name']} --[{item['relation']}]--> ", end="")
            print()
        if not chain:
            print("  (无)")


def cmd_neighbors(kg, entity_id: str):
    """邻居节点"""
    entities = kg.find_entity(entity_id)
    if not entities:
        print(f"❌ 未找到: {entity_id}")
        return
    target = entities[0]
    eid = target["entity_id"]
    print(f"🔗 {target['name']} 的关联节点:\n")

    neighbors = kg.get_neighbors(eid, "both")
    if not neighbors:
        print("  (无关联)")
        return

    # 按关系分组
    grouped = {}
    for n in neighbors:
        rel = n.get("relation", "unknown")
        grouped.setdefault(rel, []).append(n)

    for rel, items in grouped.items():
        print(f"  [{rel}]")
        for item in items:
            direction = "→" if item.get("direction") == "out" else "←"
            print(f"    {direction} {item.get('name', item['entity_id'])} ({item.get('entity_type', '?')})")
        print()


def cmd_impact(kg, keyword: str):
    """事件影响追踪"""
    entities = kg.find_entity(keyword)
    if not entities:
        print(f"❌ 未找到事件: {keyword}")
        return
    target = entities[0]
    eid = target["entity_id"]
    print(f"⚡ {target['name']} 影响路径:\n")

    paths = kg.trace_impact(eid)
    if not paths:
        print("  (无影响路径)")
        return

    for p in paths:
        indent = "  " * p["step"]
        print(f"{indent}→ {p['target_name']}({p['target_type']}) [{p['relation']}]")


def cmd_path(kg, source: str, target: str):
    """两品种间路径"""
    src_entities = kg.find_entity(source)
    tgt_entities = kg.find_entity(target)
    if not src_entities:
        print(f"❌ 未找到: {source}")
        return
    if not tgt_entities:
        print(f"❌ 未找到: {target}")
        return

    src_eid = src_entities[0]["entity_id"]
    tgt_eid = tgt_entities[0]["entity_id"]
    src_name = src_entities[0]["name"]
    tgt_name = tgt_entities[0]["name"]

    print(f"🛤️ {src_name} → {tgt_name} 的路径:\n")

    path = kg.find_path(src_eid, tgt_eid)
    if not path:
        print("  (无路径)")
        return

    for i, step in enumerate(path):
        prefix = "  " * i
        arrow = "→" if i < len(path) - 1 else " ✓"
        print(f"{prefix}{step['name']} [{step['relation']}]{arrow}")


def cmd_substitutes(kg, entity_id: str):
    """替代品种"""
    entities = kg.find_entity(entity_id)
    if not entities:
        print(f"❌ 未找到: {entity_id}")
        return
    target = entities[0]
    eid = target["entity_id"]
    print(f"🔄 {target['name']} 的替代品种:\n")

    subs = kg.find_substitutes(eid)
    if not subs:
        print("  (无替代关系)")
        return
    for s in subs:
        print(f"  - {s.get('name', s['entity_id'])} ({s.get('entity_type', '?')})")


def cmd_search(kg, keyword: str):
    """搜索实体"""
    results = kg.find_entity(keyword)
    if not results:
        print(f"❌ 未找到: {keyword}")
        return
    print(f"🔍 搜索 '{keyword}' 的结果 ({len(results)} 条):\n")
    for r in results:
        aliases = r.get("aliases", [])
        alias_str = f" (别名: {', '.join(aliases)})" if aliases else ""
        print(f"  {r['entity_id']:20s} {r.get('name', '?'):10s} [{r.get('entity_type', '?')}]{alias_str}")


def cmd_affected(kg, keyword: str):
    """受影响品种"""
    results = kg.find_affected_by(keyword)
    if not results:
        print(f"❌ 未找到受 '{keyword}' 影响的品种")
        return
    print(f"⚡ 受 '{keyword}' 影响的品种:\n")
    for r in results:
        print(f"  - {r['name']} ({r['type']}) [{r['via']}]")


def cmd_mermaid(kg):
    """导出Mermaid"""
    print(kg.export_mermaid())


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    kg = KnowledgeGraph()

    try:
        if cmd == "stats":
            cmd_stats(kg)
        elif cmd == "chain":
            cmd_chain(kg, args[0]) if args else print("用法: chain <品种ID>")
        elif cmd == "upstream":
            cmd_chain(kg, args[0], "upstream") if args else print("用法: upstream <品种ID>")
        elif cmd == "downstream":
            cmd_chain(kg, args[0], "downstream") if args else print("用法: downstream <品种ID>")
        elif cmd == "neighbors":
            cmd_neighbors(kg, args[0]) if args else print("用法: neighbors <品种ID>")
        elif cmd == "impact":
            cmd_impact(kg, args[0]) if args else print("用法: impact <事件关键词>")
        elif cmd == "path":
            if len(args) >= 2:
                cmd_path(kg, args[0], args[1])
            else:
                print("用法: path <起点> <终点>")
        elif cmd == "substitutes":
            cmd_substitutes(kg, args[0]) if args else print("用法: substitutes <品种ID>")
        elif cmd == "search":
            cmd_search(kg, args[0]) if args else print("用法: search <关键词>")
        elif cmd == "affected":
            cmd_affected(kg, args[0]) if args else print("用法: affected <事件关键词>")
        elif cmd == "mermaid":
            cmd_mermaid(kg)
        else:
            print(f"未知命令: {cmd}")
            print(__doc__)
    finally:
        kg.close()


if __name__ == "__main__":
    main()
