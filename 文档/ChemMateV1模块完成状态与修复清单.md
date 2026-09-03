# ChemMate V1 模块完成状态与修复清单

> 生成日期：2026-09（重构收尾盘点）
> 对象：代码小白（你本人），按步骤操作即可
> 关联文档：《ChemMateV1重构操作说明书》《记忆模块构建指南》《ChemMateV1后补说明》《Git使用说明手册》

## 一、全部模块完成状态（盘点日实测）

验证方式：cd CMV1 后 python -c "from 模块 import 函数"。盘点日结果：**语法错误 0，13/13 模块全部导入通过**。

| 模块 | 文件 | 状态 | 说明 |
|---|---|---|---|
| 配置 | CMV1/config.py | 完成 | 读 .env（键名 LLM_*，路径已指向项目根） |
| 主程序 | CMV1/agent_main.py | 基本完成 | 实时输入已改；遗留 1 处临时 import（见问题 1） |
| Agent 层 | agents/llm_client.py | 完成 | 大模型客户端 |
| | agents/action_parser.py | 完成 | 5 个解析函数齐全 |
| | agents/system_prompt.py | 完成 | 系统提示词 |
| | agents/__init__.py | 完成 | 已清空为包说明（不再误加载工具链） |
| 取数工具 | tools/process_data_get/ | 完成 | reader/block_type/small_tool/knowledge_base 相对导入齐全 |
| 诊断工具 | tools/analyze/ | 完成 | utils import 已补齐 |
| 绘图工具 | tools/draw_mat/ | 可用 | 路径探测已修；遗留双份缓存（见问题 2） |
| 报告工具 | tools/report_create/ | 完成 | render_docx/render_pptx/report_core/sections 齐全 |
| 小工具 | tools/path_finder_tool.py、tools/bash_tool.py | 完成 | |
| 记忆第一层 | memory/process_cache.py | 完成 | remember/get_history/clear |
| 记忆第二层 | memory/session_store.py | 模块完成 | 已见 runs/session_*.jsonl 落盘；主程序接线待补（见问题 3） |
| 记忆第三层 | memory/knowledge_base.py | 未建 | 规划为 Obsidian 知识库（见第三部分） |
| Web 演示 | CMV1/ui/ | Mock 层 | mock_word_create.py 仍引用旧 report_tool，接真实工具时处理 |
| 文档 | 文档/ 目录 | 完成 | 各手册已归档于此 |


---

## 二、记忆模块遗留问题与修复步骤（3 个）

### 问题 1：agent_main.py 第 14 行是临时 import，与第 15 行同名冲突

现状（第 14-16 行）：

    from tools.draw_mat.draw_mat import remember_process_data          # 临时修复遗留（要删）
    from memory.process_cache import remember_process_data,get_cached_process_data,get_history,clear
    from memory.session_store import new_session,_log_path,record,load_session,last_answers

第 15 行会覆盖第 14 行（同名函数），第 14 行是死代码。

**修复**：删除第 14 行整行，只保留 15、16 行（缓存统一走 memory 版）。

**验证**：cd CMV1 后运行 python -c "import agent_main; print(agent_main.remember_process_data.__module__)"，应打印 memory.process_cache。

### 问题 2：双份缓存 bug - draw_mat.py 自己还留着一套缓存

现状：tools/draw_mat/draw_mat.py 第 56-79 行自己定义了 _LAST_PROCESS_DATA / remember_process_data / get_cached_process_data，画图时 _resolve_process_data（152 行）读它自己这份；而主程序存的是 memory 那份——两套缓存互不相通。现在靠主程序显式传参没炸，但架构错误，将来忘传参就报 missing_process_data。

**修复步骤**：

1. 打开 tools/draw_mat/draw_mat.py，删除第 56-79 行（_LAST_PROCESS_DATA 全局变量 + remember_process_data + get_cached_process_data 三个函数；wrap_data_get 保留，它内部调用的 remember 会变成 memory 版）
2. 文件顶部（第 20 行附近）加一行：

    from memory.process_cache import remember_process_data, get_cached_process_data

3. 打开 tools/draw_mat/test_draw_mat.py 第 118 行附近，把 dm.remember_process_data(...) 改为从 memory 导入后调用

**验证**：cd CMV1 后运行 python -c "from tools.draw_mat.draw_mat import draw_mat, _resolve_process_data; print('OK')"，通过且无警告。

### 问题 3：第二层会话记忆只 import 了，还没在 run_agent 里接线

现状：agent_main.py 第 16 行导入了 new_session/record/load_session/last_answers，但 run_agent 函数体内没有调用（runs/session_*.jsonl 可能是单独测试生成的，主流程还没记）。

**修复步骤**（在 agent_main.py 的 run_agent 里加 4 处）：

1. 函数开头（_emit 定义后）加：

    session_id = new_session()
    record(session_id, "user", task)
    prev = last_answers(session_id)
    if prev:
        _emit("引用上次任务结论: " + prev[-1])

2. 每轮模型输出后（llm_output 拿到处）加：record(session_id, "thought", llm_output)
3. 每轮工具结果后（observation_str 生成处）加：record(session_id, "observation", observation_str)
4. Finish 时（final_answer 拿到处）加：record(session_id, "result", final_answer)

**验证**：跑一次任务，CMV1/runs/ 下生成 session_日期_时间_xxxxxx.jsonl，记事本打开能看到 user/thought/observation/result 四类记录。


---

## 三、第三层长期知识库：Obsidian 结合 + V2 planner（设计蓝图）

### 3.1 架构总览

    Obsidian Vault（长期知识库，纯 .md 文件夹）
      知识卡/Aspen/B7闪蒸塔压力报警处理.md   <- frontmatter: tags: [Aspen, 报错, 处置]
      知识卡/化工/物性方法选择.md
            |  Python 直接读 .md（不需要开 Obsidian）
            v
    memory/knowledge_base.py（升级版检索层）
      1. vault 路径来自环境变量 OBSIDIAN_VAULT（config 读 .env）
      2. 解析 frontmatter 标签做筛选
      3. 检索：关键词（现在）-> 向量（V2）
            |  top-k 笔记 + 上次会话结论（第二层记忆）
            v
    V2 Planner：任务 -> 检索知识卡 -> 生成结构化 Plan
      = 步骤 x {用哪个工具 + 参考哪张卡} -> 逐步执行
            |  执行完把新经验写回 vault（知识沉淀闭环）
            v
    Obsidian Vault（你又多了一张知识卡）

### 3.2 落地步骤（V2 开工顺序）

1. 建 vault 目录 + 样板卡：在 Obsidian 里建 知识卡/ 文件夹，写 3-5 张样板卡，每张格式：

    ---
    tags: [Aspen, 报错, 处置]
    type: knowledge-card
    ---

    # B7 闪蒸塔压力报警处理

    现象：...
    处置：先人工确认再让 Agent 改参数。

2. config 加 vault 路径：config.py 加 OBSIDIAN_VAULT = os.environ.get("OBSIDIAN_VAULT", "")；.env 填 OBSIDIAN_VAULT=你的vault路径
3. 升级 knowledge_base.py：新建 memory/knowledge_base.py，vault 存在时读 vault/知识卡/**/*.md；解析 frontmatter 拿 tags；search(keywords, tags=None) 按标签+关键词过滤；build_knowledge_context(query) 拼提示词（基础版代码见《记忆模块构建指南》第 5 节）
4. 写 Planner（新文件 agents/planner.py）：输入用户任务 -> 调 knowledge_base 检索 -> 结合 tools 各包的 tool_spec()（report 包已有先例）-> 输出 JSON 格式 Plan（步骤列表）-> run_agent 改为按 Plan 执行或在 Plan 约束下走
5. 经验回写：任务成功后把新结论追加为新卡（约定放 知识卡/经验/ 子目录）

### 3.3 关键提醒

- Vault 就是普通文件夹，Python 读写 .md 与 Obsidian 是否打开无关（Obsidian 关闭时也能写；打开着的话写后它会自动刷新）
- 笔记少（100 篇以内）时关键词检索够用，多了再上向量（chromadb），不用一步到位
- 路径一律走 .env 环境变量，绝不写死在代码里
- Obsidian 双链 [[...]] 暂时不用解析，只当正文文本检索即可

---

## 四、本次收尾建议

全部修复后执行：

    cd C:/Users/Fool/Desktop/ChemMateV1工作台
    git add -A
    git commit -m "重构收尾：记忆模块修复（缓存统一+会话接线）+ 文档归档"
    git log --oneline    # 确认存档成功

> 本清单文件建议随 文档/ 一起入库。
