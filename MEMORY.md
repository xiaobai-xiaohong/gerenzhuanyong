用户使用 Windows (Git-Bash/MSYS2)，偏好简洁直接的沟通方式，不需要多余解释。
§
Git 全局代理配置 (http.proxy) 在代理服务未运行时会是 git fetch/push 完全失败的原因。用户的网络直连 GitHub 无问题，应保持无代理状态。
§
vision_analyze on this runtime returns "Image loaded into your context — use your built-in vision to answer". THAT specific message means the image IS visible to me on the next turn — do NOT reply "I cannot see the image" if you see that exact phrase. If the response is something else (a text description from auxiliary vision, an error, or missing altogether), then the image is unreadable.
§
国内期货CTP直采 (2026-07-05更新):
① **不要绕路三方API**; 直接用md_spi.dll或md_bridge.dll（MSVC编译，已验证可用）
② **MinGW调CTP DLL vtable必崩** — MSVC SEH (__try/__except) 与MinGW libgcc不兼容; ACCESS_VIOLATION; 解法: 换用已MSVC编译的md_spi.dll或md_bridge.dll做桥接
③ **正确ABI**: CTP vtable的this指针在**栈**上(esp[4]), 不是ECX; MSVC正确写法: ((void(__cdecl*)(char*,void*))*((char**)this)[0])((char*)this, spi)
④ **64位Python无法加载32位DLL** (Error 193); 解法: MinGW编译C wrapper→Python用TCP/named pipe通信
⑤ **md_spi.dll** (MSVC): ordinal 1=GetMdSpi, 2=StartSpi(返回0=成功), 3=StopSpi, StartListener(TCP客户端连Python); tick数据走TCP JSON
⑥ **md_bridge.dll** (MSVC): StartMdBridge(front,broker,user,pass)→返回TCP端口; Python连该端口收行情JSON
⑦ **MinGW编译**: 必须os.add_dll_directory(r'C:\msys64\mingw32\bin')，否则cc1.exe崩溃0xC0000005
⑧ **SimNow**: tcp://182.254.243.31:40001, broker=9999, user=264147, pass=Zsq/015618
⑨ **CTP v6.3.19_P1 vtable**: 0=RegisterSpi,1=RegisterFront,2=Init,3=Release,5=SubscribeMarketData,6=ReqUserLogin; ordinal6=CreateFtdcMdApi
⑩ **工作目录**: C:\Users\Administrator\Desktop\ctp_md\
§
MnemOS v6.0 API base=http://localhost:8010/api/v5, archive=POST /memory/archive, search=POST /memory/search, stats=GET /health/full。7种memory_type: W铁律/K工具/I人物/D对话/E踩坑/R反思/S研究。encoding bug修复: docker-compose.yml加PYTHONUTF8=1/PYTHONIOENCODING=utf-8/LANG=C.UTF-8/LC_ALL=C.UTF-8。TF-IDF fallback对英文关键词召回差，应用中文关键词验证。已有乱码记录无法修复，只能DELETE重建。
§
多步骤任务默认批量执行，不等确认。拿到数据就下一步，不要重复查同一个答案。一个方法失败时，先读报错信息修正参数再重试同一工具，最多重试2次仍失败就如实汇报，不要偷偷换方法。用户提示优先于工具验证：任务描述里给出的参数值、路径、类型等，默认直接使用，不要用工具验证用户说的是不是对的。除非执行结果和用户说的矛盾，否则不质疑。接到模糊指令时，优先回顾 MEMORY.md 最近新增或修改的内容，用它推断用户说的"XX系统"、"新规则"具体指什么。文件路径对不上时不要直接说"没找到"，而是告诉用户"XX不在仓库里，要不要我把规则写到仓库新建一个文件？"。用户没明确说"逐条"、"分步"、"等我说"时，所有步骤一次执行完再汇报。逐条等待是需要用户明确触发的特殊模式，不是默认。
§
## 规则 6：写入 MnemOS 时同步提取实体到 entities.json
每次 archive 新记忆时，正则提取"X是Y/X的老板是Y/X曾任职Y"等关系三元组，同步更新 entities.json（entities 分类入库，relations 追加关系）。由 background_review.py 的 _mnemos_store 调用统一封装为 _entities_sync()。MnemOS search 无 DELETE，entities.json 删除靠人工确认。
路径：C:/Users/Administrator/gerenzhuanyong/entities.json（仓库根目录）。

## 规则 7：搜索 MnemOS 时先查 entities.json 再定向搜
检测多跳查询模式（如"X的老板"、"X曾任职Y"）时，先从 entities.json 推路径，再定向查 MnemOS 对应实体 ID，避免纯向量搜索的碎片化问题。多跳结果与向量结果合并排序。
entities.json 路径：C:/Users/Administrator/gerenzhuanyong/entities.json。
§
## 规则 8：更新 MEMORY.md 或 entities.json 后走完整 git add -A → commit → push
三者缺一不可：git add -A、git commit、git push 必须在一个操作流里执行完。不允许只 commit 不 push，也不允许依赖外部手动推。每次更新 MEMORY.md 或 entities.json 后，立即在仓库根目录（C:/Users/Administrator/gerenzhuanyong）执行 git add -A → commit（附简短描述）→ push。会话启动时的自动同步（检查 24h 条件）也走同一流程。
文件路径：C:/Users/Administrator/gerenzhuanyong/MEMORY.md 和 C:/Users/Administrator/gerenzhuanyong/entities.json。

## 规则 9：每次更新 MEMORY.md 或 entities.json 后，VERSION.md 的 Z +1
路径：C:/Users/Administrator/gerenzhuanyong/VERSION.md。格式 MnemOS X.Y/Z。X.Y 由用户手动升（重置 Z=1），助手只动 Z。每次完成 memory/entities 更新后，读取当前 Z → +1 → 写回。涉及 git 操作时合并到同一 commit（不要拆成两个 commit）。

## 规则 10：定期蒸馏 MnemOS 碎片记忆为结构化 MEMORY.md
每累计 20 轮对话或每天（取先到），自动扫描 MnemOS 中 memory_type=general/空的记忆，用 LLM 判断每条应归类 W/K/I/D/E/R/S，删除重复/无价值内容，将高质量碎片提炼合并入 MEMORY.md 对应章节。操作顺序：(1) 扫描 general 类型；(2) LLM 分类 + 去重；(3) 写回 MnemOS 更新类型；(4) 提炼内容追加到 MEMORY.md；(5) git add -A → commit → push → VERSION Z+1。
文件路径：C:/Users/Administrator/gerenzhuanyong/MEMORY.md。
§
## 规则 11：会话启动时检查未提交变更并自动同步
每次会话启动时：运行 `git status --porcelain` 检查仓库是否有未提交变更。有变更 → git add -A → git commit -m "session: auto-sync YYYY-MM-DD" → git push。无变更 → 跳过什么都不做。
仓库根目录：C:/Users/Administrator/gerenzhuanyong。
