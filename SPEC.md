# MnemOS v6.0 — duMem × Mnemosyne 结合系统规格书

> 融合 duMem 记忆智能层 + Mnemosyne Docker 架构的记忆操作系统

**版本**: 6.0.0  **日期**: 2026-07-04

---

## 核心架构

Layer 3: 记忆智能层（duMem精华）
  - Trust Scoring + Bayesian平滑
  - Social Closer 废话过滤
  - Jaccard 语义去重
  - 7类记忆分类 W/K/I/D/E/R/S
  - 半衰期衰减
  - L0/L1/L2 分层注入

Layer 2: 知识生产层（Mnemosyne原生）
  - 三馆闭环 Archive→Research→Engineering
  - Triple Recall: 向量+全文+分类
  - Score_final = w1·Sim + w2·Qual + w3·Hot + w4·Time

Layer 1: 存储引擎
  - PostgreSQL + pgvector
  - Memory表扩展: trust_score, source_authority, decay_at, memory_type

Layer 0: 基础设施
  - mnemosyne-core (:8010) + postgres (:5432) + redis (:6379)

---

## 7类记忆

| 代码 | 类型 | 半衰期 | Trust初始 |
|------|------|--------|-----------|
| W | 铁律 | ∞ | 1.0 |
| K | 工具知识 | 180天 | 0.8 |
| I | 人物信息 | 365天 | 0.7 |
| D | 对话摘要 | 30天 | 0.5 |
| E | 踩坑经验 | 90天 | 0.8 |
| R | 反思总结 | 60天 | 0.6 |
| S | 研究笔记 | 120天 | 0.5 |

---

## 4级权威

| 级别 | 来源 | Trust加成 |
|------|------|----------|
| L1 | 用户终端指令 | +0.3 |
| L2 | 显式注入/配置 | +0.2 |
| L3 | 官方文档 | 0.0 |
| L4 | LLM生成 | -0.1 |

---

## 新增API

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | /api/v5/memory/inject-context | pre-LLM上下文注入 |
| POST | /api/v5/memory/feedback | Trust反馈 |
| GET | /api/v5/memory/trust-stats | 记忆质量统计 |
| POST | /api/v5/memory/decay | 手动触发衰减扫描 |
| GET | /api/v5/memory/dedup-report | 去重报告 |
| POST | /api/v5/maintenance/ciraaf | CIRAAF周日重构 |

---

## 自动化Cron

| 任务 | 时间 | 功能 |
|------|------|------|
| decay_scanner.py | 每日02:30 | 半衰期扫描 |
| dedup_facts.py | 每周日03:00 | Jaccard去重 |
| recompute_trust.py | 每周日04:00 | Trust重算 |
| ciraaf_sunday.py | 每周日03:30 | 宏观重构 |
| experience_distiller.py | 每日07:00 | 踩坑经验提取 |

---

## 收益

- L0 token节省: 30% → 55%+
- Social Closer: 废话不调embedding
- Trust < 0.2: 自动过滤
- 重复记忆: Jaccard去重
- 全自动维护: 0手动操作
