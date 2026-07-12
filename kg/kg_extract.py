"""
研报自动抽取 → 知识图谱
从研报文本中抽取实体和关系，自动入库
"""
import re
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from kg_engine import KnowledgeGraph


# ═══════════════════════════════════════════════════════════
#  抽取规则
# ═══════════════════════════════════════════════════════════

# 装置/工厂名（中文2-8字+装置/公司/厂/石化/炼化）
FACILITY_PATTERNS = [
    r'((?:神华|中煤|延长|中海油|中石化|中石油|恒力|荣盛|桐昆|盛虹|逸盛|虹港|万华|卫星|宝丰|陕煤|中原|新疆天业|山东海化|湖北宜化)[\u4e00-\u9fa5]{0,4}(?:石化|炼化|化工|能源|煤化|集团|MTO|EG|PP|PTA)?)',
    r'([\u4e00-\u9fa5]{2,6}(?:石化|炼化|化工|集团)(?:有限|股份)?)',
]

# 港口名
PORT_KEYWORDS = ['太仓', '广东', '宁波', '连云港', '舟山', '青岛', '天津', '南京',
                 '钦州', '防城港', '湛江', '日照', '烟台', '大连', '营口']

# 区域名
REGION_KEYWORDS = ['内蒙', '陕西', '新疆', '山东', '江苏', '浙江', '广东', '四川',
                   '宁夏', '甘肃', '山西', '河南', '安徽', '湖北', '湖南', '福建']

# 品种关键词 → entity_id 映射
COMMODITY_MAP = {
    '甲醇': 'ma', 'MA': 'ma', 'methanol': 'ma',
    '乙二醇': 'eg', 'EG': 'eg', 'MEG': 'eg',
    '对二甲苯': 'px', 'PX': 'px',
    'PTA': 'pta', '精对苯二甲酸': 'pta',
    '聚丙烯': 'pp', 'PP': 'pp',
    '聚乙烯': 'pe', 'PE': 'pe', 'LLDPE': 'pe',
    '聚氯乙烯': 'pvc', 'PVC': 'pvc',
    '纯碱': 'soda_ash', '烧碱': 'caustic',
    '玻璃': 'glass', '原油': 'crude', '石脑油': 'naphtha',
    'LPG': 'lpg', '丙烯': 'propylene', '乙烯': 'ethylene',
    '涤纶': 'polyester', '聚酯': 'polyester',
    '沥青': 'bitumen', '燃料油': 'fuel_oil',
    '纯苯': 'benzene', '苯乙烯': 'styrene', 'SM': 'styrene',
    '尿素': 'urea', '焦炭': 'coke', '煤炭': 'coal',
    'MTBE': 'mtbe', '甲醛': 'formaldehyde',
}

# 事件关键词
EVENT_KEYWORDS = {
    '霍尔木兹': 'hormuz_close', '海峡': 'hormuz_close',
    '台风': 'typhoon_bawei', '巴威': 'typhoon_bawei',
    '检修': 'summer检修', '停车': 'summer检修', '重启': 'summer检修',
    '制裁': 'us_iran_sanction', '伊朗': 'us_iran_sanction',
    '能耗双控': 'energy_cap', '碳中和': 'carbon_neutral',
}

# 数据指标模式
DATA_PATTERNS = {
    'inventory': r'(?:库存|到港量|港存)[\s:：]*(\d+\.?\d*)\s*(?:万吨|万)',
    'capacity': r'(?:开工率|负荷|产能利用率)[\s:：]*(\d+\.?\d*)\s*%',
    'price': r'(?:现货|价格|收盘)[\s:：]*(\d+\.?\d*)\s*(?:元/吨|元)',
    'profit': r'(?:利润|亏损)[\s:：]*(-?\d+\.?\d*)\s*(?:元/吨|元)',
}


def extract_entities(text: str, kg: KnowledgeGraph) -> list:
    """从文本中抽取实体"""
    found = []

    # 1. 品种
    for keyword, eid in COMMODITY_MAP.items():
        if keyword in text:
            found.append({"type": "commodity", "id": eid, "name": keyword})

    # 2. 装置
    for pattern in FACILITY_PATTERNS:
        for match in re.finditer(pattern, text):
            name = match.group(1)
            if len(name) >= 3:  # 过滤太短的
                found.append({"type": "facility", "name": name})

    # 3. 港口
    for port in PORT_KEYWORDS:
        if port in text:
            found.append({"type": "port", "name": port})

    # 4. 区域
    for region in REGION_KEYWORDS:
        if region in text:
            found.append({"type": "region", "name": region})

    # 5. 事件
    for keyword, eid in EVENT_KEYWORDS.items():
        if keyword in text:
            found.append({"type": "event", "id": eid, "name": keyword})

    return found


def extract_relations(text: str, entities: list) -> list:
    """从文本和实体中推断关系"""
    relations = []
    commodity_ids = [e["id"] for e in entities if e["type"] == "commodity" and "id" in e]
    facility_names = list(set(e["name"] for e in entities if e["type"] == "facility" and len(e["name"]) >= 3))
    port_names = [e["name"] for e in entities if e["type"] == "port"]
    event_ids = [e["id"] for e in entities if e["type"] == "event" and "id" in e]

    # 1. 装置-品种关联（基于上下文窗口）
    for facility in facility_names:
        for eid in commodity_ids:
            # 在文本中查找装置名和品种名的距离
            f_pos = text.find(facility)
            c_pos = text.find(COMMODITY_MAP.get(eid, eid))
            if f_pos >= 0 and c_pos >= 0 and abs(f_pos - c_pos) < 30:
                # 检查是否有生产/运行/开工等关键词
                window = text[min(f_pos, c_pos):max(f_pos, c_pos) + len(facility)]
                if any(kw in window for kw in ['开工', '运行', '生产', '负荷', '产量', '装置', '投产', '检修', '停车']):
                    relations.append((facility, eid, "PRODUCES", 0.7))

    # 2. 事件-品种关联
    for eid in event_ids:
        for cid in commodity_ids:
            relations.append((eid, cid, "IMPACTS", 0.6))

    # 3. 港口-品种关联
    for port in port_names:
        for cid in commodity_ids:
            c_pos = text.find(COMMODITY_MAP.get(cid, cid))
            p_pos = text.find(port)
            if c_pos >= 0 and p_pos >= 0 and abs(c_pos - p_pos) < 20:
                relations.append((cid, port, "SHIPPED_VIA", 0.5))

    return relations


def extract_data_points(text: str) -> dict:
    """提取数据指标"""
    data = {}
    for key, pattern in DATA_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            data[key] = [float(m) for m in matches]
    return data


def process_report(text: str, source: str = "report",
                   title: str = "", kg: KnowledgeGraph = None) -> dict:
    """
    处理单篇研报，抽取实体和关系入库

    Returns:
        {
            "entities_found": [...],
            "relations_added": [...],
            "data_points": {...}
        }
    """
    if kg is None:
        kg = KnowledgeGraph()

    full_text = f"{title}\n{text}" if title else text

    # 抽取
    entities = extract_entities(full_text, kg)
    relations = extract_relations(full_text, entities)
    data_points = extract_data_points(full_text)

    # 入库
    added_relations = []
    for src, tgt, rel_type, weight in relations:
        if src in kg.graph and tgt in kg.graph:
            if kg.add_relation(src, tgt, rel_type, weight, source_from=source):
                added_relations.append(f"{src} --[{rel_type}]--> {tgt}")

    # 记录事件
    for e in entities:
        if e["type"] == "event" and "id" in e:
            kg.conn.execute(
                "INSERT INTO events (entity_id, event_type, title, detail, occurred_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (e["id"], "report", title[:100], text[:500])
            )
            kg.conn.commit()

    return {
        "entities_found": entities,
        "relations_added": added_relations,
        "data_points": data_points,
    }


def process_report_file(filepath: str, kg: KnowledgeGraph = None) -> dict:
    """处理研报文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    title = os.path.basename(filepath)
    return process_report(text, source="report", title=title, kg=kg)


def batch_process_dir(dirpath: str, kg: KnowledgeGraph = None):
    """批量处理目录下所有 .md 文件"""
    if kg is None:
        kg = KnowledgeGraph()

    total_entities = 0
    total_relations = 0

    for root, dirs, files in os.walk(dirpath):
        for fname in files:
            if fname.endswith('.md'):
                fpath = os.path.join(root, fname)
                try:
                    result = process_report_file(fpath, kg)
                    n_ent = len(result["entities_found"])
                    n_rel = len(result["relations_added"])
                    total_entities += n_ent
                    total_relations += n_rel
                    if n_ent > 0 or n_rel > 0:
                        print(f"  ✅ {fname[:40]:40s} 实体:{n_ent} 关系:{n_rel}")
                except Exception as ex:
                    print(f"  ❌ {fname[:40]:40s} 错误: {ex}")

    print(f"\n📊 批量处理完成:")
    print(f"  实体抽取: {total_entities} 条")
    print(f"  关系入库: {total_relations} 条")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python kg_extract.py file <研报.md>        # 处理单个文件")
        print("  python kg_extract.py dir <研报目录>        # 批量处理目录")
        print("  python kg_extract.py text '<文本>'          # 处理文本片段")
        sys.exit(1)

    kg = KnowledgeGraph()
    action = sys.argv[1]

    try:
        if action == "file":
            result = process_report_file(sys.argv[2], kg)
            print(f"实体: {len(result['entities_found'])} 条")
            print(f"关系: {len(result['relations_added'])} 条")
            print(f"数据: {result['data_points']}")
        elif action == "dir":
            batch_process_dir(sys.argv[2], kg)
        elif action == "text":
            result = process_report(sys.argv[2], kg=kg)
            print(f"实体: {len(result['entities_found'])} 条")
            print(f"关系: {len(result['relations_added'])} 条")
    finally:
        kg.close()
