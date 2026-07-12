# 核心记忆

## 我是谁
- 我是 Hermes Agent，由 Nous Research 创建
- 运行在 Windows 10 上
- 使用 mimo-v2.5 模型

## 用户偏好
- 用户希望我主要用中文回复
- 思考过程也以中文为主
- 偏好简洁直接的沟通方式，不需要多余解释

## 工作环境
- 主机：Administrator
- 工作目录：C:\Users\Administrator
- Shell：bash (git-bash/MSYS)
- Git 代理：仅 github.com 走代理，其他直连
- vision_analyze 返回 "Image loaded" 表示图片可见，不要说"无法看到"

## 重要项目
- MnemOS v6.1 记忆系统已部署在 Docker 容器中
  - 端口：127.0.0.1:8010
  - 嵌入：SiliconFlow BGE-M3
  - LLM：SiliconFlow DeepSeek
  - API Key：68a2f89e...
  - GitHub：https://github.com/xiaobai-xiaohong/gerenzhuanyong

## 铁律
- 所有回复以中文为主
- 思考状态也以中文为主
- API Key 不要在聊天中明文发送
- Docker 国内需要配置镜像加速
- 修改 .env 后要重启容器才生效
- LLM 提示词中的 JSON 要用双大括号转义
- Dockerfile 代理要用 host.docker.internal

## CTP 踩坑记录 (2026-07-05)
1. 勿绕路三方API，直接用 md_spi.dll / md_bridge.dll（MSVC 编译）
2. MinGW 调 CTP DLL vtable 必崩（ACCESS_VIOLATION），换 MSVC 编译的 dll 桥接
3. 正确 ABI：CTP vtable 的 this 指针在栈上 (esp[4])
4. 64位 Python 无法加载 32位 DLL，用 MinGW 编译 C wrapper 走 TCP 通信
5. md_spi.dll ordinal：1=GetMdSpi, 2=StartSpi, 3=StopSpi, StartListener(TCP JSON)
6. md_bridge.dll：StartMdBridge → 返回 TCP 端口
7. MinGW 编译必须 os.add_dll_directory(r'C:\msys64\mingw32\bin')
8. SimNow：tcp://182.254.243.31:40001, broker=9999, user=264147, pass=Zsq/015618
9. CTP v6.3.19_P1 vtable：0=RegisterSpi,1=RegisterFront,2=Init,3=Release,5=SubscribeMarketData,6=ReqUserLogin
10. 工作目录：C:\Users\Administrator\Desktop\ctp_md\

## MnemOS API
- base：http://localhost:8010/api/v5
- 归档：POST /memory/archive
- 检索：POST /memory/search
- 统计：GET /health/full
- 7 种记忆类型：W铁律/K工具/I人物/D对话/E踩坑/R反思/S研究
- encoding 修复：docker-compose.yml 加 PYTHONUTF8=1 等环境变量
- TF-IDF 对英文关键词召回差，用中文关键词验证
- 乱码记录无法修复，只能 DELETE 重建

## 任务执行规则
- 多步骤任务默认批量执行，不等确认
- 拿到数据就下一步，不要重复查同一个答案
- 一个方法失败时，先读报错信息修正参数再重试同一工具，最多重试 2 次仍失败就如实汇报，不要偷偷换方法
- 用户提示优先于工具验证：任务描述里给出的参数值、路径、类型等默认直接使用，不要用工具验证是否正确，除非执行结果矛盾
- 接到模糊指令时，优先回顾 MEMORY.md 最近新增内容推断意图
- 文件路径对不上时告诉用户"XX不在仓库里，要不要新建？"
- 用户没明确说"逐条/分步/等我说"时，所有步骤一次执行完再汇报
- 逐条等待是特殊模式，不是默认

## 重试限制
- 连续 3 次同类操作返回相同失败结果时，必须停下来如实报告
- 不允许通过微调参数、换编译选项、换工具路径等方式绕过去
- 这些不算"新方案"，算重试
- 比如编译退出码 0 但不生成文件，换 cc 或 g++ 或加 save-temps 都算同类重试

## Git 标准流程
- 每次 MEMORY.md 更新后，执行：git pull --rebase → git add -A → git commit（附简短描述）→ git push
- push 前必须先 pull --rebase，rebase 有冲突停下来报告，禁止 force push
- 不允许只 commit 不 push
- 每次更新后，VERSION.md 的 Z+1（格式 MnemOS X.Y/Z，X.Y 用户手动升，助手只动 Z）
- 涉及 git 操作时合并到同一 commit，不拆成两个

## 定期蒸馏
- 每累计 20 轮对话或每天（取先到），自动扫描 MnemOS 中 memory_type=general/空的记忆
- LLM 判断归类 W/K/I/D/E/R/S，删除重复/无价值内容
- 将高质量碎片提炼合并入 MEMORY.md 对应章节

## 启动同步
- 每次会话启动时，git status --porcelain 检查未提交变更
- 有变更 → 执行 Git 标准流程
- 无变更 → 跳过

## 测试清理
- 验证产生的临时文件（test_*.txt、hermes-verify-*.sh 等）通过验证后立即删除
- 再执行 Git 标准流程
- 禁止将测试文件混入正常 commit

## 主动精简
- 每次新增规则后，检查 MEMORY.md 是否有：
  - 功能重叠（多条规则操作同一件事）
  - 已被新规则覆盖的旧规则
  - 可压缩的冗余表述
- 发现后主动合并或删除
