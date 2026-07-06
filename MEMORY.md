repo=C:/Users/Administrator/gerenzhuanyong; files=MEMORY.md, entities.json, VERSION.md
§
用户使用 Windows (Git-Bash/MSYS2)，偏好简洁直接的沟通方式，不需要多余解释。
Git代理：仅 github.com 走代理（http.https://github.com.proxy），其他直连。无代理时 fetch/push 完全失败，用户直连 GitHub 无问题，保持无代理。
vision_analyze 返回 "Image loaded into your context — use your built-in vision to answer" 表示图片可见，不要说"无法看到"。
§
国内期货CTP直采 (2026-07-05): ①勿绕路三方API，直接用md_spi.dll/md_bridge.dll（MSVC编译）②MinGW调CTP DLL vtable必崩（ACCESS_VIOLATION），换MSVC编译的dll桥接③正确ABI: CTP vtable的this指针在栈上(esp[4])④64位Python无法加载32位DLL，用MinGW编译C wrapper走TCP通信⑤md_spi.dll ordinal: 1=GetMdSpi, 2=StartSpi, 3=StopSpi, StartListener(TCP JSON)⑥md_bridge.dll: StartMdBridge→返回TCP端口⑦MinGW编译必须os.add_dll_directory(r'C:\msys64\mingw32\bin')⑧SimNow: tcp://182.254.243.31:40001, broker=9999, user=264147, pass=Zsq/015618⑨CTP v6.3.19_P1 vtable: 0=RegisterSpi,1=RegisterFront,2=Init,3=Release,5=SubscribeMarketData,6=ReqUserLogin; ordinal6=CreateFtdcMdApi⑩工作目录: C:\Users\Administrator\Desktop\ctp_md\
§
MnemOS v6.0 API: base=http://localhost:8010/api/v5, archive=POST /memory/archive, search=POST /memory/search, stats=GET /health/full。7种memory_type: W铁律/K工具/I人物/D对话/E踩坑/R反思/S研究。encoding修复: docker-compose.yml加PYTHONUTF8=1等环境变量。TF-IDF对英文关键词召回差，用中文关键词验证。乱码记录无法修复，只能DELETE重建。
§
多步骤任务默认批量执行，不等确认。拿到数据就下一步，不要重复查同一个答案。一个方法失败时，先读报错信息修正参数再重试同一工具，最多重试2次仍失败就如实汇报，不要偷偷换方法。用户提示优先于工具验证：任务描述里给出的参数值、路径、类型等默认直接使用，不要用工具验证是否正确，除非执行结果矛盾。接到模糊指令时，优先回顾MEMORY.md最近新增内容推断意图。文件路径对不上时告诉用户"XX不在仓库里，要不要新建？"。用户没明确说"逐条/分步/等我说"时，所有步骤一次执行完再汇报。逐条等待是特殊模式，不是默认。
连续3次同类操作返回相同失败结果时，必须停下来如实报告，不允许通过微调参数、换编译选项、换工具路径等方式绕过去。这些不算"新方案"，算重试。比如编译退出码0但不生成文件，换cc或g++或加save-temps都算同类重试。
§
## MnemOS 读写 + 实体同步（规则6-7）
规则6: archive新记忆时，正则提取"X是Y/X的老板是Y"等关系三元组，同步更新entities.json（entities分类入库，relations追加关系）。由background_review.py的_mnemos_store调用统一封装的_entities_sync()执行。MnemOS search无DELETE，entities.json删除靠人工确认。路径: C:/Users/Administrator/gerenzhuanyong/entities.json。
规则7: 检测多跳查询模式（"X的老板"、"X曾任职Y"等）时，先从entities.json推路径，再定向查MnemOS对应实体ID，避免纯向量搜索碎片化。多跳结果与向量结果合并排序。
§
## Git标准流程 + VERSION（规则8-9）
规则8: 每次MEMORY.md或entities.json更新后，执行: git pull --rebase → git add -A → git commit（附简短描述）→ git push。push前必须先pull --rebase，rebase有冲突停下来报告，禁止force push。不允许只commit不push。
规则9: 每次MEMORY.md或entities.json更新后，VERSION.md的Z+1（路径: C:/Users/Administrator/gerenzhuanyong/VERSION.md，格式MnemOS X.Y/Z，X.Y用户手动升，助手只动Z）。涉及git操作时合并到同一commit，不拆成两个。
§
## 定期蒸馏（规则10）
每累计20轮对话或每天（取先到），自动扫描MnemOS中memory_type=general/空的记忆，LLM判断归类W/K/I/D/E/R/S，删除重复/无价值内容，将高质量碎片提炼合并入MEMORY.md对应章节。操作: ①扫描general ②LLM分类+去重 ③写回MnemOS更新类型 ④提炼内容追加MEMORY.md ⑤执行规则8+9。
§
## 启动同步 + 测试清理（规则11-12）
规则11: 每次会话启动时，git status --porcelain检查未提交变更。有变更 → 执行规则8+9。无变更 → 跳过。
规则12: 验证产生的临时文件（test_*.txt、hermes-verify-*.sh等）通过验证后立即删除，再执行规则8+9。禁止将测试文件混入正常commit。
§
## 主动精简（规则13）
每次新增规则后，检查MEMORY.md是否有: ①功能重叠（多条规则操作同一件事）②已被新规则覆盖的旧规则③可压缩的冗余表述。发现后主动合并或删除。MEMORY.md硬上限88行（不含§分隔符），超过时必须合并：优先保留高频使用的，低频的蒸馏成一句话写进相关规则。
