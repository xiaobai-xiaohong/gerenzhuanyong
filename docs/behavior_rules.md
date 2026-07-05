# Hermes Agent 行为规则

## 规则 1：多步骤任务默认批量执行
多步骤任务默认批量执行，不等确认。拿到数据就下一步，不要重复查同一个答案。用户没明确说"逐条"、"分步"、"等我说"时，所有步骤一次执行完再汇报。逐条等待是需要用户明确触发的特殊模式，不是默认。

## 规则 2：失败时修正重试同一工具
一个方法失败时，先读报错信息修正参数再重试同一工具，最多重试2次仍失败就如实汇报，不要偷偷换方法。

## 规则 3：用户提示优先于工具验证
任务描述里给出的参数值、路径、类型等，默认直接使用，不要用工具验证用户说的是不是对的。除非执行结果和用户说的矛盾，否则不质疑。

## 规则 4：MnemOS v6.0 编码修复
encoding bug 修复：docker-compose.yml 加 PYTHONUTF8=1 / PYTHONIOENCODING=utf-8 / LANG=C.UTF-8 / LC_ALL=C.UTF-8。TF-IDF fallback 对英文关键词召回差，应用中文关键词验证。已有乱码记录无法修复，只能 DELETE 重建。

7 种 memory_type：W铁律 / K工具 / I人物 / D对话 / E踩坑 / R反思 / S研究。

## 规则 5：模糊指令优先回顾 MEMORY.md
接到模糊指令时，优先回顾当前会话 MEMORY.md 最近新增或修改的内容，用它推断用户说的"XX系统"、"新规则"具体指什么。文件路径对不上时不要直接说"没找到"，而是告诉用户"XX不在仓库里，要不要我把规则写到仓库新建一个文件？"。

## 规则 6：MnemOS 记忆 CRUD 操作（2026-07-05）
- MnemOS v6.0 API base=http://localhost:8010/api/v5
- archive=POST /memory/archive，search=POST /memory/search，stats=GET /health/full
- 删记忆：API 无 DELETE 端点，直接 `docker exec mnemosyne-pg psql` 操作 DB
