# ChemMate V1 后补说明（补丁文档）

> 对象：代码小白（你本人）
> 性质：对《ChemMateV1重构操作说明书》的事后补充，记录重构收尾时发现并修复的两个问题。
> 关联文档：《ChemMateV1重构操作说明书.md》《记忆模块构建指南.md》《Git使用说明手册.md》

## 目录

- 0　这两个补丁是修什么的
- 1　补丁一：修复 `NameError: name 'remember_process_data' is not defined`
- 2　补丁二：把写死的 DEFAULT_PROMPT 改成命令行实时输入
- 3　以后遇到 `NameError: name 'xxx' is not defined` 的通用自查三步法
- 4　改完提交

---

## 0　这两个补丁是修什么的

| # | 现象 | 原因 | 文档节 |
|---|---|---|---|
| 1 | 运行报 `NameError: name 'remember_process_data' is not defined` | 重构时 draw_mat 搬进了 `tools/draw_mat/` 包，但主程序漏了一行 import | 第 1 节 |
| 2 | 主程序一运行就自动执行写死的默认任务 | `__main__` 里写死了 `DEFAULT_PROMPT`，想改成"每次运行时手动输入任务" | 第 2 节 |

---

## 1　补丁一：修复 remember_process_data 未定义

### 1.1 为什么会报错（根因）

旧代码里，主程序从平铺的 `draw_mat.py` 同时导入了两个东西：

~~~python
from draw_mat import draw_mat, remember_process_data
~~~

重构后：
- `draw_mat.py` 搬进了 `tools/draw_mat/` 包；
- `remember_process_data`（缓存"最近一次取数结果"的函数）**还留在** `tools/draw_mat/draw_mat.py` 第 59 行，没有搬走；
- 但 `tools/draw_mat/__init__.py` 只导出了 `draw_mat` 一个名字；
- 主程序 `agent_main.py` 顶部也只写了 `from tools.draw_mat import draw_mat`——**把 `remember_process_data` 漏掉了**。

于是程序跑到第 176 行 `remember_process_data(observation)`（data_get 成功后把结果存进缓存）时，Python 找不到这个名字 → `NameError`。

### 1.2 快速修复（一行，立刻能跑）

打开 `CMV1/agent_main.py`，在第 11 行 `from tools.draw_mat import draw_mat` 下面加一行：

~~~python
from tools.draw_mat.draw_mat import remember_process_data
~~~

说明：`from tools.draw_mat.draw_mat import xxx` 表示"从 draw_mat 包里的 draw_mat 子模块导入 xxx"（绕过了只导出 draw_mat 的 `__init__.py`）。

### 1.3 规范修复（以后做 memory 模块时一起做，现在可以不做）

按《记忆模块构建指南》的架构，"最近一次取数结果"的缓存**本来就不该住在 draw_mat 里**，它属于第一层记忆。到时候：
1. 建 `CMV1/memory/process_cache.py`，把 `remember_process_data` / `get_cached_process_data` 的函数体搬进去（指南里有现成代码）；
2. `tools/draw_mat/draw_mat.py` 里删掉这两个函数，改为 `from memory.process_cache import remember_process_data, get_cached_process_data`；
3. `agent_main.py` 也改成 `from memory.process_cache import remember_process_data`；
4. 第 1.2 节加的那行临时 import 删掉。

> 结论：现在先用 1.2 的一行修复让程序跑起来；等做 memory 时按 1.3 收编，两处都指向 memory，全项目只此一份缓存代码。

### 1.4 验证

~~~bash
cd CMV1
python -c "from tools.draw_mat.draw_mat import remember_process_data; print('remember_process_data 导入 OK')"
~~~

再运行主程序，报错消失（会接着执行真实任务，需要 Aspen，耐心等待）。

---

## 2　补丁二：把写死的 DEFAULT_PROMPT 改成命令行实时输入

### 2.1 现状

`agent_main.py` 最后两行（第 189–191 行）是写死的：

~~~python
DEFAULT_PROMPT = "你好，10万吨环己烷.bkp 检查整个流程有无报错，如有报错，生成一份带有可视化数据图的报告给我,并附上保存路径"
if __name__ == "__main__":
    run_agent(DEFAULT_PROMPT)
~~~

一运行就自动执行这一条任务，想换个任务就得改代码。

### 2.2 改成"每次运行时手动输入"

把上面两行（第 189–191 行）**整个替换成**：

~~~python
if __name__ == "__main__":
    print("ChemMate V1 Agent 已启动。")
    print("输入任务后回车执行；直接回车重输；输入 q 退出。")
    while True:
        task = input("任务 > ").strip()
        if not task:
            continue
        if task.lower() in ("q", "quit", "exit"):
            print("再见！")
            break
        run_agent(task)
~~~

### 2.3 小白语法讲解（这段代码在干什么）

- `input("任务 > ")`：在终端等你打字，回车后把你输入的内容作为字符串返回。`"任务 > "` 只是提示文字。
- `.strip()`：去掉输入内容首尾的空格（防止误触空格导致任务为空）。
- `while True:`：无限循环 = "一直问下去"，每次任务跑完自动回来再问一次，不用重启程序。
- `if not task: continue`：如果回车没输入内容，`continue` = "跳过这次，重新问"。
- `if task.lower() in ("q", "quit", "exit"): break`：输入 q / quit / exit（不区分大小写）就 `break` 退出循环，程序结束。
- `run_agent(task)`：把你输入的任务交给 Agent 主循环执行。

> `input()` 是 Python 内置函数（不需要 import）。注意：只能在"终端里运行"时用，如果以后接入 Web 界面，就要换成界面传任务的方式（`run_agent(task)` 本身是通用入口，UI 也能直接调用，互不影响）。

### 2.4 运行效果

~~~text
ChemMate V1 Agent 已启动。
输入任务后回车执行；直接回车重输；输入 q 退出。
任务 > 检查 10万吨环己烷.bkp 有没有报错
...（Agent 开始干活，打印每一轮思考与工具结果）...
任务 > 把刚才的结果生成一份 PDF 报告        ← 跑完自动回来，可以连续问
任务 > q
再见！
~~~

### 2.5 验证

~~~bash
cd CMV1
python agent_main.py
~~~

能出现 `任务 >` 提示并等你输入，就成功了。不想真跑任务时输入 q 退出即可（不会启动 Aspen）。

---

## 3　以后遇到 NameError 的通用自查三步法

`NameError: name 'xxx' is not defined` = "Python 不认识 xxx 这个名字"。九成是漏了 import，按下面三步查：

1. **搜 xxx 定义在哪**：在 PyCharm 里 `Ctrl+Shift+F` 搜 `def xxx` 或 `xxx =`，找到它住在哪个文件；
2. **看调用文件顶部有没有 import 它**：如果定义在别的文件/包里，调用文件就必须有对应的 import 语句；
3. **按关系补 import**：
   - 定义在**同一个包**的其他文件（如 analyze 包内互调）→ 写 `from .文件名 import xxx`
   - 定义在**其他包**（如 tools.draw_mat 包）→ 写 `from tools.包名 import xxx`，若 `__init__.py` 没导出 → `from tools.包名.模块名 import xxx`
   - 定义在**旧平铺位置** → 说明重构后路径变了，import 要跟着新路径改

> 记住：import 失败会在"导入那一刻"报错（ModuleNotFoundError/ImportError）；而**名字在函数体内才用、又没导入**的，要到"运行时执行到那一行"才报 NameError——所以拆完包一定要真实跑一遍全流程，光 import 成功不算数。

---

## 4　改完提交

~~~bash
cd CMV1
git add agent_main.py
git commit -m "补丁：修复 remember_process_data 漏导入；主程序改为实时输入任务"
~~~

> 本文件也建议一起提交，留个记录：
> `git add ChemMateV1后补说明.md` 然后一起 commit。
