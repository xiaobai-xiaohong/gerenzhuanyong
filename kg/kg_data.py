"""
能化产业链预置数据
品种：原油、石脑油、PX、PTA、聚酯、EG、甲醇、丙烯、PP、PVC、烧碱、纯碱、玻璃、LPG、沥青、燃油、纯苯、苯乙烯
"""
from kg_engine import KnowledgeGraph


def build_supply_chain(kg: KnowledgeGraph):
    """构建能化产业链图谱"""

    # ═══════════════════════════════════════════════════
    # 1. 品种实体
    # ═══════════════════════════════════════════════════
    commodities = {
        # 上游
        "crude":       ("原油", ["布伦特", "WTI", "SC", "国际油价"], {"exchange": "INE/Brent/WTI"}),
        "naphtha":     ("石脑油", ["轻脑油"], {}),
        "lpg":         ("LPG", ["液化石油气"], {}),
        "fuel_oil":    ("燃料油", [], {}),
        "bitumen":     ("沥青", [], {}),
        # 芳烃链
        "benzene":     ("纯苯", [], {}),
        "styrene":     ("苯乙烯", ["SM"], {}),
        "px":          ("PX", ["对二甲苯"], {"exchange": "郑商所"}),
        "pta":         ("PTA", ["精对苯二甲酸"], {"exchange": "郑商所"}),
        "polyester":   ("聚酯", ["涤纶", "PET"], {}),
        "dty":         ("涤纶长丝", ["DTY"], {}),
        "fdy":         ("涤纶牵伸丝", ["FDY"], {}),
        "poY":         ("涤纶预取向丝", ["POY"], {}),
        "staple":      ("涤纶短纤", ["PSF"], {"exchange": "郑商所"}),
        # 烯烃链
        "ethane":      ("乙烷", [], {}),
        "ethylene":    ("乙烯", [], {}),
        "propylene":   ("丙烯", [], {}),
        "eg":          ("EG", ["乙二醇", "MEG"], {"exchange": "郑商所/大商所"}),
        "pp":          ("PP", ["聚丙烯"], {"exchange": "大商所"}),
        "pe":          ("PE", ["聚乙烯", "LLDPE"], {"exchange": "大商所"}),
        "ma":          ("MA", ["甲醇", "methanol"], {"exchange": "郑商所"}),
        "mtbe":        ("MTBE", [], {}),
        "formaldehyde":("甲醛", [], {}),
        # 氯碱链
        "pvc":         ("PVC", ["聚氯乙烯"], {"exchange": "大商所"}),
        "caustic":     ("烧碱", ["NaOH"], {}),
        "soda_ash":    ("纯碱", ["苏打"], {"exchange": "郑商所"}),
        "glass":       ("玻璃", [], {"exchange": "郑商所"}),
        # 煤化工
        "coal":        ("煤炭", ["动力煤", "焦煤"], {}),
        "coke":        ("焦炭", [], {}),
        "urea":        ("尿素", [], {"exchange": "郑商所"}),
        # 其他
        "ammonia":     ("合成氨", [], {}),
        "acrylonitrile":("丙烯腈", ["AN"], {}),
    }

    for eid, (name, aliases, attrs) in commodities.items():
        kg.add_entity(eid, name, "commodity", aliases, attrs)

    # ═══════════════════════════════════════════════════
    # 2. 装置/工厂
    # ═══════════════════════════════════════════════════
    facilities = {
        # 甲醇装置
        "shenhua_ningxia":    ("神华宁煤", ["宁煤"], {"capacity": "100万吨/年", "type": "煤制甲醇"}),
        "yanchang":           ("延长石油", [], {"type": "煤/天然气制甲醇"}),
        "cnooc_tianjin":      ("中海油天津", [], {"type": "天然气制甲醇"}),
        "iran_kaveh":         ("Kaveh甲醇", [], {"location": "伊朗", "capacity": "165万吨/年"}),
        "iran_zpc":           ("ZPC", ["Zagros"], {"location": "伊朗", "capacity": "330万吨/年"}),
        "iran_kimiya":        ("Kimiya", [], {"location": "伊朗"}),
        "iran_sabalan":       ("Sabalan", [], {"location": "伊朗"}),
        # MTO装置
        "mto_shenhua":        ("神华包头MTO", [], {"capacity": "60万吨/年", "feedstock": "甲醇"}),
        "mto_ningxia":        ("宁煤MTO", [], {"feedstock": "甲醇"}),
        "mto_dalian":         ("大连恒力MTO", [], {"feedstock": "甲醇"}),
        # 聚酯装置
        "shenghong":          ("盛虹炼化", [], {"type": "炼化一体化", "capacity": "1600万吨/年"}),
        "honggang":           ("虹港石化", [], {"type": "PX/PTA"}),
        "yisheng":            ("逸盛石化", [], {"type": "PTA", "capacity": "1200万吨/年"}),
        "rongsheng":          ("荣盛石化", [], {"type": "PTA/聚酯"}),
        "tongkun":            ("桐昆股份", [], {"type": "聚酯/涤纶"}),
        # EG装置
        "shenghong_eg":       ("盛虹EG", [], {"type": "石油制EG"}),
        "yizheng_eg":         ("仪征EG", [], {"type": "石油制EG"}),
        "cooeg":              ("中石化炼化EG", [], {"type": "石油制EG"}),
        # 煤制EG
        "xinjiang_tianye":    ("新疆天业", [], {"type": "煤制EG"}),
        "zhongyuan_eg":       ("中原大化EG", [], {"type": "煤制EG"}),
        # PP装置
        "hengli_pp":          ("恒力PP", [], {"type": "油制PP"}),
        "zhejiang_pp":        ("浙江石化PP", [], {"type": "油制PP"}),
        # 纯碱/玻璃
        "shandong_soda":      ("山东海化", [], {"type": "纯碱"}),
        "hubei_soda":         ("湖北宜化", [], {"type": "纯碱"}),
    }

    for eid, (name, aliases, attrs) in facilities.items():
        kg.add_entity(eid, name, "facility", aliases, attrs)

    # ═══════════════════════════════════════════════════
    # 3. 港口
    # ═══════════════════════════════════════════════════
    ports = {
        "taicang":  ("太仓", ["太仓港"], {"province": "江苏"}),
        "guangdong":("广东", ["广东港", "南沙"], {"province": "广东"}),
        "ningbo":   ("宁波", ["宁波港"], {"province": "浙江"}),
        "lianyungang":("连云港", [], {"province": "江苏"}),
        "zhoushan": ("舟山", [], {"province": "浙江"}),
        "qingdao":  ("青岛", [], {"province": "山东"}),
        "tianjin":  ("天津", [], {"province": "天津"}),
    }

    for eid, (name, aliases, attrs) in ports.items():
        kg.add_entity(eid, name, "port", aliases, attrs)

    # ═══════════════════════════════════════════════════
    # 4. 区域
    # ═══════════════════════════════════════════════════
    regions = {
        "neimenggu":   ("内蒙", ["内蒙古"], {}),
        "shaanxi":     ("陕西", [], {}),
        "xinjiang":    ("新疆", [], {}),
        "shandong":    ("山东", [], {}),
        "jiangsu":     ("江苏", [], {}),
        "zhejiang":    ("浙江", [], {}),
        "iran":        ("伊朗", [], {}),
        "saudi":       ("沙特", ["沙特阿拉伯"], {}),
        "qatar":       ("卡塔尔", [], {}),
    }

    for eid, (name, aliases, attrs) in regions.items():
        kg.add_entity(eid, name, "region", aliases, attrs)

    # ═══════════════════════════════════════════════════
    # 5. 需求端
    # ═══════════════════════════════════════════════════
    demand_sectors = {
        "mto_sector":    ("MTO", ["甲醇制烯烃"], {}),
        "mtbe_sector":   ("MTBE", [], {}),
        "formal_sector": ("甲醛", [], {}),
        "acetic_sector": ("醋酸", [], {}),
        "polyester_sector": ("聚酯", ["涤纶"], {}),
        "glass_sector":  ("浮法玻璃", [], {}),
        "pipe_sector":   ("管材", [], {}),
        "film_sector":   ("薄膜", [], {}),
    }

    for eid, (name, aliases, attrs) in demand_sectors.items():
        kg.add_entity(eid, name, "demand_sector", aliases, attrs)

    # ═══════════════════════════════════════════════════
    # 6. 事件/政策
    # ═══════════════════════════════════════════════════
    events_policies = {
        "hormuz_close":    ("霍尔木兹海峡关闭", [], {"type": "geopolitical"}),
        "us_iran_sanction":("美国伊朗制裁", ["美伊制裁", "对伊制裁"], {"type": "policy"}),
        "typhoon_bawei":   ("台风巴威", [], {"type": "weather"}),
        "summer检修":      ("夏季检修季", ["检修", "春检", "秋检"], {"type": "seasonal"}),
        "carbon_neutral":  ("碳中和", [], {"type": "policy"}),
        "energy_cap":      ("能耗双控", [], {"type": "policy"}),
    }

    for eid, (name, aliases, attrs) in events_policies.items():
        kg.add_entity(eid, name, "event" if "policy" not in attrs.get("type", "") else "policy",
                     aliases, attrs)

    # ═══════════════════════════════════════════════════
    # 7. 原料
    # ═══════════════════════════════════════════════════
    feedstocks = {
        "coal_feed":    ("动力煤", ["煤"], {}),
        "gas_feed":     ("天然气", ["气"], {}),
        "naphtha_feed": ("石脑油", [], {}),
    }

    for eid, (name, aliases, attrs) in feedstocks.items():
        kg.add_entity(eid, name, "feedstock", aliases, attrs)

    print(f"✅ 实体导入完成: {kg.graph.number_of_nodes()} 个节点")

    # ═══════════════════════════════════════════════════
    # 8. 关系（产业链核心）
    # ═══════════════════════════════════════════════════
    relations = [
        # ── 原油产业链 ──
        ("crude", "naphtha", "DOWNSTREAM", 1.0),
        ("crude", "lpg", "DOWNSTREAM", 0.8),
        ("crude", "fuel_oil", "DOWNSTREAM", 0.7),
        ("crude", "bitumen", "DOWNSTREAM", 0.6),

        # ── 芳烃链: 石脑油→PX→PTA→聚酯 ──
        ("naphtha", "px", "DOWNSTREAM", 1.0),
        ("naphtha", "benzene", "DOWNSTREAM", 0.9),
        ("px", "pta", "DOWNSTREAM", 1.0),
        ("pta", "polyester", "DOWNSTREAM", 1.0),
        ("polyester", "dty", "DOWNSTREAM", 0.9),
        ("polyester", "fdy", "DOWNSTREAM", 0.9),
        ("polyester", "poY", "DOWNSTREAM", 0.9),
        ("polyester", "staple", "DOWNSTREAM", 0.8),

        # ── 烯烃链: 石脑油→乙烯/丙烯 ──
        ("naphtha", "ethylene", "DOWNSTREAM", 1.0),
        ("naphtha", "propylene", "DOWNSTREAM", 1.0),
        ("ethylene", "eg", "DOWNSTREAM", 1.0),
        ("ethylene", "pe", "DOWNSTREAM", 0.9),
        ("propylene", "pp", "DOWNSTREAM", 1.0),
        ("propylene", "acrylonitrile", "DOWNSTREAM", 0.6),

        # ── 甲醇链: 煤/气→甲醇→MTO/甲醛 ──
        ("coal", "ma", "DOWNSTREAM", 0.9),
        ("coal", "coke", "DOWNSTREAM", 1.0),
        ("ma", "mto_sector", "DOWNSTREAM", 1.0),
        ("ma", "formal_sector", "DOWNSTREAM", 0.7),
        ("ma", "mtbe_sector", "DOWNSTREAM", 0.6),
        ("mto_sector", "pp", "DOWNSTREAM", 0.8),
        ("mto_sector", "pe", "DOWNSTREAM", 0.8),

        # ── 氯碱链: ──
        ("caustic", "pvc", "DOWNSTREAM", 0.8),
        ("pvc", "pipe_sector", "DOWNSTREAM", 1.0),

        # ── 纯碱→玻璃 ──
        ("soda_ash", "glass", "DOWNSTREAM", 1.0),
        ("glass", "glass_sector", "DOWNSTREAM", 0.9),

        # ── LPG下游 ──
        ("lpg", "propylene", "DOWNSTREAM", 0.5),

        # ── 装置→产品 ──
        ("shenhua_ningxia", "ma", "PRODUCES", 1.0),
        ("yanchang", "ma", "PRODUCES", 0.8),
        ("cnooc_tianjin", "ma", "PRODUCES", 0.6),
        ("iran_kaveh", "ma", "PRODUCES", 1.0),
        ("iran_zpc", "ma", "PRODUCES", 1.0),
        ("iran_kimiya", "ma", "PRODUCES", 0.8),
        ("iran_sabalan", "ma", "PRODUCES", 0.7),
        ("shenghong", "px", "PRODUCES", 1.0),
        ("shenghong", "pta", "PRODUCES", 0.8),
        ("honggang", "px", "PRODUCES", 1.0),
        ("yisheng", "pta", "PRODUCES", 1.0),
        ("rongsheng", "pta", "PRODUCES", 0.9),
        ("tongkun", "polyester", "PRODUCES", 1.0),
        ("shenghong_eg", "eg", "PRODUCES", 1.0),
        ("cooeg", "eg", "PRODUCES", 0.8),
        ("xinjiang_tianye", "eg", "PRODUCES", 0.7),
        ("hengli_pp", "pp", "PRODUCES", 1.0),
        ("zhejiang_pp", "pp", "PRODUCES", 0.9),
        ("shandong_soda", "soda_ash", "PRODUCES", 1.0),
        ("hubei_soda", "soda_ash", "PRODUCES", 0.9),

        # ── 装置原料 ──
        ("coal_feed", "shenhua_ningxia", "FEEDSTOCK", 1.0),
        ("coal_feed", "mto_ningxia", "FEEDSTOCK", 1.0),
        ("naphtha_feed", "shenghong", "FEEDSTOCK", 1.0),

        # ── MTO装置使用甲醇 ──
        ("ma", "mto_shenhua", "USES", 1.0),
        ("ma", "mto_ningxia", "USES", 1.0),
        ("ma", "mto_dalian", "USES", 0.8),

        # ── 港口运输 ──
        ("ma", "taicang", "SHIPPED_VIA", 1.0),
        ("ma", "guangdong", "SHIPPED_VIA", 0.8),
        ("eg", "ningbo", "SHIPPED_VIA", 1.0),
        ("eg", "lianyungang", "SHIPPED_VIA", 0.7),
        ("pta", "taicang", "SHIPPED_VIA", 0.8),
        ("pta", "zhoushan", "SHIPPED_VIA", 0.9),
        ("px", "zhoushan", "SHIPPED_VIA", 1.0),

        # ── 装置所在区域 ──
        ("shenhua_ningxia", "neimenggu", "LOCATED_IN", 1.0),
        ("yanchang", "shaanxi", "LOCATED_IN", 1.0),
        ("xinjiang_tianye", "xinjiang", "LOCATED_IN", 1.0),
        ("shenghong", "jiangsu", "LOCATED_IN", 1.0),
        ("honggang", "jiangsu", "LOCATED_IN", 1.0),
        ("shandong_soda", "shandong", "LOCATED_IN", 1.0),

        # ── 伊朗装置→伊朗 ──
        ("iran_kaveh", "iran", "LOCATED_IN", 1.0),
        ("iran_zpc", "iran", "LOCATED_IN", 1.0),
        ("iran_kimiya", "iran", "LOCATED_IN", 1.0),
        ("iran_sabalan", "iran", "LOCATED_IN", 1.0),

        # ── 进口来源 ──
        ("iran", "ma", "DOWNSTREAM", 0.9),  # 伊朗→中国甲醇（进口）
        ("saudi", "naphtha", "DOWNSTREAM", 0.8),
        ("qatar", "lpg", "DOWNSTREAM", 0.7),

        # ── 替代关系 ──
        ("eg", "pta", "SUBSTITUTE", 0.6),  # 聚酯端EG和PTA可部分替代
        ("mto_sector", "naphtha", "SUBSTITUTE", 0.5),  # MTO和油制烯烃可替代
        ("coal", "gas_feed", "SUBSTITUTE", 0.4),  # 煤和气可替代（甲醇原料）
        ("pp", "pe", "SUBSTITUTE", 0.3),  # PP和PE部分应用可替代

        # ── 事件影响 ──
        ("hormuz_close", "ma", "IMPACTS", 1.0),   # 霍尔木兹关闭→影响甲醇进口
        ("hormuz_close", "lpg", "IMPACTS", 0.8),
        ("hormuz_close", "naphtha", "IMPACTS", 0.7),
        ("us_iran_sanction", "ma", "IMPACTS", 0.9),
        ("us_iran_sanction", "naphtha", "IMPACTS", 0.6),
        ("typhoon_bawei", "taicang", "IMPACTS", 1.0),  # 台风影响港口
        ("typhoon_bawei", "guangdong", "IMPACTS", 0.8),
        ("summer检修", "ma", "IMPACTS", 0.7),
        ("summer检修", "eg", "IMPACTS", 0.6),
        ("summer检修", "pta", "IMPACTS", 0.5),
        ("energy_cap", "ma", "IMPACTS", 0.8),  # 能耗双控影响煤化工
        ("energy_cap", "pvc", "IMPACTS", 0.9),
        ("energy_cap", "soda_ash", "IMPACTS", 0.7),
        ("carbon_neutral", "coal", "IMPACTS", 0.9),
        ("carbon_neutral", "ma", "IMPACTS", 0.6),

        # ── 竞争关系 ──
        ("ma", "lpg", "COMPETES_WITH", 0.4),  # 甲醇和LPG在MTO/MTP上竞争
        ("pp", "pvc", "COMPETES_WITH", 0.3),  # PP和PVC在管材上竞争
        ("soda_ash", "caustic", "COMPETES_WITH", 0.5),  # 纯碱和烧碱在氯碱上竞争
    ]

    count = 0
    for src, tgt, rel, weight in relations:
        if kg.add_relation(src, tgt, rel, weight, source_from="manual"):
            count += 1

    print(f"✅ 关系导入完成: {count} 条关系")
    return kg


if __name__ == "__main__":
    kg = KnowledgeGraph()
    build_supply_chain(kg)
    stats = kg.stats()
    print(f"\n📊 图谱统计:")
    print(f"  实体: {stats['total_entities']}")
    print(f"  关系: {stats['total_relations']}")
    print(f"  实体类型: {stats['entity_types']}")
    print(f"  关系类型: {stats['relation_types']}")
    kg.close()
