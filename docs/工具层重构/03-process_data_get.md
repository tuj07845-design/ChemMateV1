# 03 · process_data_get 模块

> 覆盖 `CMV1/tools/process_data_get/` 全部 4 个文件
> 对外只暴露一个名字：`data_get_process`（`reader.py` 里的同名函数）

---

## 一、定位

**它做的事**：用 Windows COM 打开 Aspen Plus 文件，把整张流程图读成一个 dict——流股、设备、连接关系、设备类型、设备参数、模拟报错状态。

**它是整条链路的源头**：后面 analyze、draw_mat、report 全部吃它吐出来的 dict。**它读错一个字段，下游全错**。

**它是唯一碰外部进程的模块**：Aspen OLE 服务。这意味着：

- 不能像 analyze 那样"喂个 dict 就测"；
- 任何改动都必须用真实的 `.bkp` 验证；
- 改造原则只有一条：**机械变换可以，逻辑重构免谈**。

**调用链**：

```
tools_register.data_get_process(file_path)
        │  成功后 remember_process_data(result) 写缓存
        ▼
reader.data_get_process(file_path)                       ← 主流程，11 段
        ├── _extract_from_apwz()         .apwz → 解包出 .bkp
        ├── pythoncom.CoInitialize()     COM 初始化（线程要求）
        ├── win32.gencache.EnsureDispatch("Apwn.Document")
        ├── AspenSimulation.InitFromArchive2(路径)
        ├── 遍历 Streams → read_value / read_component_data
        ├── 遍历 Blocks  → get_block_type_data
        │       ├── get_block_real_type()        设备真实类型
        │       ├── collect_block_parameters()   递归收集参数
        │       └── pick_key_parameters()        挑招牌参数
        ├── 读 Connections（进出流股）
        ├── read_simulation_status()             模拟报错
        └── finally: Close() + CoUninitialize()
```

**文件职责表**：

| 文件 | 行数 | 职责 | 改造强度 |
|---|---:|---|---|
| `reader.py` | 536 | 主流程 + apwz 解包 + `_safe_print` | **格式压缩** |
| `small_tool.py` | 243 | 三个节点读取函数 | 格式压缩 + 删死导入 |
| `block_type.py` | 422 | 设备类型识别 + 参数收集 + 参数挑选 | 格式压缩 + 删死导入 |
| `knowledge_base.py` | 196 | 设备类型知识库（纯数据） | **只删 3 行死导入** |

---

## 二、改造清单

| # | 文件 | 问题 | 动作 | 风险 |
|---|---|---|---|---|
| 1 | `knowledge_base.py` | `import os` / `import json` / `import win32com.client as win32` 三个全是死导入 | 删 3 行 | 无 |
| 2 | `small_tool.py` | 同样三个死导入 | 删 3 行 | 无 |
| 3 | `block_type.py` | 同样三个死导入 | 删 3 行 | 无 |
| 4 | `reader.py` | `shutil` / `tempfile` / `zipfile` 是 apwz 用的（活）；`json` 只在最后打印时用（活）；`os` 活 | **不动** | — |
| 5 | `reader.py` | "一参数一行"，536 行里有 200+ 行是空行 | 压缩到 **250–280** 行 | 低 |
| 6 | `small_tool.py` | 同上 | 压缩到 **110–130** 行 | 低 |
| 7 | `block_type.py` | 同上 | 压缩到 **200–230** 行 | 低 |
| 8 | 全部 | `try/except` 的**粒度** | **一行都不能合并** | **高** |
| 9 | 全部 | COM 节点路径字符串（`"Data"` / `"Streams"` / `"MIXED"` …） | **一个字符都不能改** | **高** |
| 10 | `reader.py` | `_extract_from_apwz` 里 `n[:-7] + ".bkp"` 会把 `xxx.bkp.backup` 拼成 `xxx.bkp.bkp` | 改成 `n[:-7]` | 低 |

> 第 8、9 条是硬约束，见第三节；第 10 条是已知 bug，见 5.1。
>
> 第 5–7 条的行数是**区间**，不是硬指标：这些文件的代码行（去空行去注释）分别是 300 / 146 / 249，
> 压缩只能来自排版，不可能低于代码行本身。为了凑整数字把 `try/except` 合并、把 dict 写成一长行，只会让 COM 代码更难排查。

---

## 三、为什么这么改（以及什么绝对不能改）

### 3.1 死导入的证据

用 AST 扫三个文件（`block_type.py` / `small_tool.py` / `knowledge_base.py`）的 `Name` 节点：

| 文件 | `os` | `json` | `win32` |
|---|---|---|---|
| `knowledge_base.py` | 0 次 | 0 次 | 0 次 |
| `small_tool.py` | 0 次 | 0 次 | 0 次 |
| `block_type.py` | 0 次 | 0 次 | 0 次 |

`knowledge_base.py` 只有 `TYPE_KNOWLEDGE` 和 `DEFAULT_CATEGORY`，`import win32com` 这种要拉起 COM 类型库的导入，纯属浪费启动时间。

`reader.py` 不同：`json.dumps` 在最后打印结果时用了一次，`os` 用于 `path.exists` / `path.join` / `makedirs`，`shutil` / `tempfile` / `zipfile` 都在 apwz 解包里用。**一个都不能删**。

### 3.2 为什么 `try/except` 的粒度不能合并

看这段：

```
for code_name in ("TOTSTAT", "UOSSTAT", ...):
    try:
        code_node = run_status_output.Elements(code_name)
        result["status_codes"][code_name] = code_node.Value
    except Exception:
        pass
```

为什么每个状态码单独 try，而不是整段一个 try？

因为**这些节点在不同 Aspen 版本 / 不同模型里存在性不同**。`TOTSTAT` 有、`RSTAT` 可能没有。整段包一个 try，第一个读不到就跳出循环，后面的全部丢失。

同理 `collect_block_parameters` 里，每个子节点的 `child.Value` / `child.UnitString` / `child.Elements` 各自有 try——**有些节点没有 Value，有些没有 UnitString，有些没有子节点**，这是 Aspen 的常态。

**压缩格式时**：可以删空行、可以把 `try:` 和 `except:` 之间的单行语句合到一行，但**不能把相邻的两个 try 合并成一个**。

### 3.3 为什么节点路径字符串不能改

```
Data.Elements("Streams")
Data.Elements("Blocks")
Stream.Elements("Output")
Output.Elements("TEMP_OUT").Elements("MIXED")
Data.Elements("Flowsheet").Elements("Section").Elements("GLOBAL").Elements("Input")
```

这些是 Aspen 内部变量树的**常量名**，大小写敏感、拼写固定。改错一个字母不会报错——`Elements()` 会返回一个空集合或抛异常，最终表现是"某个字段全空"，非常难排查。

**改造时把这些字符串当黑盒**，一个字都别动。

### 3.4 为什么这个模块排最后改

前三个模块（analyze / draw_mat / report）错了，你立刻能看到错误数据或报错。这个模块错了，表现为"数据看起来是对的，但某个字段永远是 0"——**沉默的错误**。

所以：**先把前三块改稳、对拍通过，再来动这里**。动的时候一次只改一个文件，改完立刻用 `10万吨环己烷.bkp` 跑一遍全链路。

---

## 四、操作步骤

1. **先跑一次基线**：`data_get_process("10万吨环己烷.bkp")`，把返回 JSON 存成 `baseline_data_get.json`。**这一步必须在改任何代码之前做**。
2. **删三个文件的死导入** → 导入检查（不需要 Aspen）。
3. **压缩 `knowledge_base.py`**（只删 3 行，字典不动）→ 检查文件能被 import。
4. **压缩 `small_tool.py`** → 用真实 bkp 跑一次，对拍 `streams` 部分。
5. **压缩 `block_type.py`** → 对拍 `block_details` 部分。
6. **压缩 `reader.py`** → 对拍完整 JSON。
7. **对比脚本**：写个 10 行的 `json.dumps(..., sort_keys=True)` 逐键 diff，不要肉眼看。

---

## 五、逐块原子拆解

### 5.1 `reader.py`

#### `_safe_print(*args)`

**为什么需要**：这是一个踩过坑的函数。

常驻 UI 服务里，stdout 句柄可能在两次任务之间失效。此时裸 `print` 会抛：

```
OSError [Errno 22] Invalid argument        —— 句柄被关闭 / 管道断开
ValueError I/O operation on closed file    —— 流对象已 close()
```

这两个异常一路上抛，最后变成"任务失败"——**但业务逻辑其实完全正常**，只是打印不出来。

**原子步骤**：

1. `try: print(*args)`
2. `except (OSError, ValueError): pass`

**坑**：只接这两个异常。其它异常该炸出来——比如参数写错导致的 `TypeError`，被吞掉就永远查不到了。

**改造时**：函数本身不动；但**所有 `print` 调用都要改成 `_safe_print`**，不要图省事用 `print`。

#### `_fix_zip_name(raw) -> str`

**为什么需要**：`.apwz` 是 zip 格式，但里面的条目名是 **GBK** 编码，而 `zipfile` 按 cp437 解码，直接读会得到乱码文件名。

**写法**：`raw.encode("cp437").decode("gbk")`，失败就原样返回。

**坑**：这个 `cp437 → gbk` 的转换是处理中文 Windows 下 zip 文件名乱码的标准做法。看起来怪，但必须这么写。

#### `_extract_from_apwz(apwz_path) -> str | None`

**为什么需要**：Aspen 的 OLE 服务**打不开 `.apwz` 归档格式**，只能打开 `.bkp` / `.apw`。用户给的是 `.apwz` 时，必须先解包。

**原子步骤**：

1. `zipfile.ZipFile(apwz_path)` 打开。
2. 缓存目录：`<系统临时目录>/chemmate_apwz/`，`makedirs(exist_ok=True)`。
3. **按优先级收集候选**（三轮独立循环）：
   - 第一轮：所有 `.bkp`（排除 `.bkp.backup`）
   - 第二轮：所有 `.bkp.backup`，改名为 `.bkp`
   - 第三轮：所有 `.apw`
4. 一个都没有 → `return None`。
5. 取第一个，`shutil.copyfileobj` 解到缓存目录。
6. 返回解包后的路径。

**坑**：

- 三轮循环的顺序就是优先级，**不能合并成一个循环**——否则 `.apw` 可能排在 `.bkp` 前面。
- **`n[:-7] + ".bkp"` 是个 bug**：`xxx.bkp.backup` 去掉末尾 7 个字符（`.backup`）已经得到 `xxx.bkp`，再拼一个 `.bkp` 就变成 **`xxx.bkp.bkp`**。解包出的文件带这个怪名，Aspen 的 `InitFromArchive2` 打开会失败。正确写法是 `n[:-7]`。
- 这个 bug 平时不触发：第一轮优先命中真正的 `.bkp`，只有归档里**仅有** `.bkp.backup` 时才会走到第二轮。
- 解包文件放在系统 temp，**不会自动清理**。多次读不同 apwz 会堆积。这是已知的取舍（避免动用户目录），如果要改，加一个"按源文件 hash 命名"即可。

#### `data_get_process(file_path) -> dict`

**为什么需要**：唯一对外入口。

**返回契约**（键名不可改）：

```
成功: {"success": True, "file_path", "stream_count", "block_count", "connection_count",
       "streams": {...}, "blocks": [...], "connections": [...],
       "block_details": [...], "simulation_status": {...}}
      （apwz 来源时多一个 "requested_path"）
失败: {"success": False, "file_path", "error"}
      （注意：前两种失败——空路径 / 文件不存在——**不带 `file_path` 键**，只返回 success + error）
```

**11 段流程，逐段说明**（顺序不可调换）：

| 段 | 做什么 | 关键点 |
|---|---|---|
| 1 | 检查路径 | 空 → `success=False`；不存在 → `success=False` |
| 1.5 | apwz 解包 | 解包失败 → 返回明确错误；成功则把 `file_path` 换成解包后的 bkp |
| — | `pythoncom.CoInitialize()` | **必须在 COM 调用前**。LangGraph 可能在线程池里执行工具，线程没初始化 COM 会报 `(-2147221008, '尚未调用 CoInitialize。')` |
| 2 | `EnsureDispatch("Apwn.Document")` | 启动 Aspen |
| 3 | `InitFromArchive2(os.path.abspath(file_path))` | 加载模型；`Visible = True` |
| 4 | `Data = Tree.Elements("Data")` | 拿数据根节点 |
| 5 | 遍历 `Streams` | 每条流股读 7 个字段：T / P / 汽化率 / 质量流量 / 摩尔流量 / 摩尔分率 / 质量分率 |
| 6 | 遍历 `Blocks` | 每台设备：类型识别 + 参数收集 + Connections |
| 7 | 组装 `result` | 8 个键 + `simulation_status` |
| 8 | 打印总结 | 只用于人看，不影响返回 |
| 9 | `return result` | |
| 10 | `except Exception` | 返回 `success=False` + `str(e)`，**不抛** |
| 11 | `finally` | `Close()` + `CoUninitialize()` |

**坑（每条都踩过）**：

1. **`CoInitialize` 与 `CoUninitialize` 必须配对**。缺 `CoUninitialize` 会泄漏 COM 引用，跑几次后 Aspen 进程杀不掉。
2. **`Close()` 也要 try**。Aspen 已经崩了的时候 `Close()` 会抛，不能让 finally 里的异常盖住真正的错误。
3. **`Output` 拿不到时 `continue`**，不是 `return`。某条流股没有输出（比如未收敛）不该让整个读取失败。
4. **`connections` 的判定是 `"IN" in connection_type` / `"OUT" in connection_type`**，不是 `==`。Aspen 的值可能是 `"IN"`、`"MATERIAL_IN"` 等。
5. **`blocks` 里存的是名字列表**（`["B1", "B2", ...]`），`block_details` 里才是完整信息。两个都要留——`check_process` 用 `blocks` × `block_details` 做覆盖性检查（见 01 分册步骤 8）。
6. **`read_simulation_status` 要在 `Close()` 之前调用**，它读的是 `Data` 节点。

---

### 5.2 `small_tool.py`

#### `read_value(output, variable_name) -> dict`

**为什么需要**：读 Aspen 的标量节点（T / P / 汽化率），统一成 `{"value", "unit"}`。

**原子步骤**：

1. `node = output.Elements(variable_name).Elements("MIXED")` —— **`MIXED` 这一层不能省**，Aspen 的混合相数据在这一层下面。
2. `value = node.Value`
3. `try: unit = node.UnitString except: unit = ""`
4. 返回 `{"value": value, "unit": unit}`
5. 外层任何异常 → `{"value": None, "unit": ""}`

**坑**：失败返回 `None` 而不是抛异常。下游 `_numeric_value(None)` 会得到 `None`，`check_stream` 会记 `missing_temperature`——**错误被转化成一条 finding**，这是设计意图。

#### `read_component_data(output, variable_name) -> dict`

**为什么需要**：读按组分拆开的数据（`MOLEFLOW` / `MOLEFRAC`），返回 `{组分名: {value, unit}}`。

**原子步骤**：

1. `node = output.Elements(variable_name).Elements("MIXED")`
2. `for component in node.Elements:` 逐个取 `Name` / `Value` / `UnitString`
3. 组装 `data[name] = {"value": value, "unit": unit}`
4. 任何异常 → 返回已收集到的部分（可能是空 dict）

**坑**：`except: pass` 之后 `return data`——**部分成功也要返回**。某一条流股里某个组分读失败，不该丢掉整条流股的其它组分。

#### `read_simulation_status(Data) -> dict`

**为什么需要**：这是"流程有没有报错"的唯一数据源。`tools_register` 的 docstring 明确告诉模型看 `simulation_status.status`。

**返回**：

```
{"status": "error"|"ok"|"unknown", "error_count": int,
 "errors": ["..."], "status_codes": {"TOTSTAT": 1, ...}}
```

**原子步骤**：

1. 初始化 `status="unknown"`、`error_count=0`、`errors=[]`、`status_codes={}`。
2. 定位 `Data/Results Summary/Run-Status/Output`。
3. 遍历 6 个状态码名（`TOTSTAT` / `UOSSTAT` / `UOSSTAT2` / `ITSTAT` / `RSTAT` / `SSTAT`），**每个单独 try**，读到就存。
4. 读 `PER_ERROR` 的 `Value` → `error_count`。
5. **连续枚举** `PER_ERROR\1`、`PER_ERROR\2`…… 直到读不到（`break`），上限 50。收集非空文本。
6. 判定：`error_count > 0` → `"error"`；否则有 `status_codes` → `"ok"`；都没有 → 保持 `"unknown"`。

**坑**：

- **`PER_ERROR` 的值是"组数"，不是"行数"**。一组错误文本可能跨多行，所以要用"连续读直到失败"的方式枚举，不能用 `range(1, error_count+1)`。
- 上限 50 是防死循环的保险。错误超过 50 条的场景基本不存在。
- 状态码**只收集不解释**。`TOTSTAT=1` 是什么意思交给模型判断，这里不做映射——做映射就等于把 Aspen 的语义写死在这个函数里，升级版本就错。

---

### 5.3 `block_type.py`

#### `get_block_real_type(flowsheet_input, block_name) -> {"real_type", "type_code"}`

**为什么需要**：`Data/Blocks/<名字>` 节点只告诉你设备叫 `B5`，不告诉你它是反应器还是塔。真实类型在 `Flowsheet/Section/GLOBAL/Input` 下的 `MDLTYPE` 和 `BLKTYPE` 里。

**原子步骤**：

1. `try: result["real_type"] = str(flowsheet_input.Elements("MDLTYPE").Elements(block_name).Value) except: pass`
2. `try: result["type_code"] = str(flowsheet_input.Elements("BLKTYPE").Elements(block_name).Value) except: pass`
3. 返回

**坑**：**两个 try 必须分开**。有的模型只有 `MDLTYPE`，有的只有 `BLKTYPE`。合成一个 try，第一个失败就两个都拿不到。

#### `collect_block_parameters(node, path="", result=None, depth=0, max_depth=8) -> dict`

**为什么需要**：不同设备类型的参数完全不同（反应器有 `STOIC`，塔有 `NSTAGE`），没法写死，只能**递归把 `Input` 下面所有有值的节点抓出来**。

**返回**：`{"参数路径": {"value", "unit"}}`，路径用 `\` 拼接（如 `"Reactions\\R-1\\STOIC\\1"`）。

**原子步骤**：

1. `if result is None: result = {}` —— **可变默认参数的标准坑**，不能写成 `result={}`。
2. `children = node.Elements`；`count = children.Count`。
3. **探测索引起点**：
   ```
   try:
       children.Item(0)
       start = 0
   except:
       start = 1
   ```
   为什么：Aspen 的集合有的从 0 开始，有的从 1 开始。**试一次**比查文档可靠。
4. `for i in range(start, start + count):` 取 `child = children.Item(i)`。
5. 取 `name`，失败 `continue`。
6. 拼 `child_path = path + "\\" + name if path else name`。
7. 尝试 `child.Value`，**过滤三类无意义值**：
   - `None`
   - `str(value).strip() == ""`
   - `"COMObject" in str(value)` —— COM 对象转字符串后是 `<COMObject ...>`，不是真值
8. 有值 → 存 `{"value": value, "unit": unit}`，unit 读不到给 `""`。
9. **`if depth < max_depth:`** 再递归（`sub.Count > 0` 才进）。
10. 返回 `result`。

**坑**：

- **第 3 步的探测不能省**。写死 0 或 1，在某些 Aspen 版本上会漏掉第一个子节点或抛索引错误。
- **递归深度 8** 是性能与完整性的折中。Aspen 的 `Input` 树可能很深（反应动力学），但不限制会读上千个节点，返回 JSON 撑到几 MB。
- **第 9 步的 `depth < max_depth` 判断放在递归调用前**，不是函数开头。写成开头会导致 max_depth 层完全不收集。

#### `pick_key_parameters(real_type, all_parameters) -> dict`

**为什么需要**：`all_parameters` 可能有几十上百条，全给模型是噪音。这个函数挑"这个设备类型最该看的几个参数"。

**原子步骤**：

1. `knowledge = TYPE_KNOWLEDGE.get(real_type, {})`；`wanted = knowledge.get("key_parameters", {})`。
2. **知识库精确匹配**：`for param_name, description in wanted.items():` 遍历 `all_parameters`，取路径最后一段 `short_name = full_path.split("\\")[-1]`，相等就收，`break`（每个参数名只收第一个）。
3. **自动特征匹配**（知识库没覆盖的类型也能用）：
   - 关键字表：`TEMP` / `PRES` / `DUTY` / `FLOW` / `EFF` / `AREA` / `RR` / `NSTAGE` / `VFRAC` / `PDROP` / `POWER`
   - 跳过已收的
   - **噪音过滤**：名字含 `TOL` / `CHK` / `CORR` 的跳过；值是小写后 `"YES"` / `"NO"` 的跳过
   - 命中任一关键字就收，`description` 标 `"自动识别（含关键字 X）"`
4. 返回

**坑**：

- `break` 在"知识库匹配"里是必须的——一个参数名可能出现在多条路径下，只取第一条，否则重复。
- 关键字是**子串匹配**（`keyword in upper_name`），所以 `"TEMP"` 会命中 `"TEMP_OUT"` 和 `"TEMPERATURE"`。这是有意的。
- 噪音过滤为什么在自动匹配里做、不在知识库匹配里做：知识库点名要的参数，即使名字含 TOL 也要收（那是人明确要的）。

#### `get_block_type_data(block_node, block_name, flowsheet_input) -> dict`

**为什么需要**：把上面三个函数串起来，产出 `block_details` 里的一条。

**返回 7 个键**：`block` / `real_type` / `type_code` / `category` / `key_parameters` / `all_parameters_count` / `all_parameters`。

**原子步骤**：

1. `type_info = get_block_real_type(...)` → `real_type` / `type_code`。
2. **中文类别**：`category = DEFAULT_CATEGORY`；`if real_type in TYPE_KNOWLEDGE` 取它的；`elif type_code in TYPE_KNOWLEDGE` 取它的。
   为什么两级：`MDLTYPE` 给的是 `"RStoic"`（驼峰），`BLKTYPE` 给的是 `"RSTOIC"`（全大写），知识库的键是驼峰。有的模型只有后者。
3. `input_node = block_node.Elements("Input")`，`collect_block_parameters(input_node)`（整段 try）。
4. `pick_key_parameters(real_type, all_parameters)`。
5. 组装返回，`all_parameters_count = len(all_parameters)`。

**坑**：第 3 步的 `collect_block_parameters` 整段 try 是合理的——某台设备的 `Input` 读不了，不该让整个 `block_details` 失败，返回空参数即可。

---

### 5.4 `knowledge_base.py`

**为什么存在**：设备类型 → 中文类别 + 招牌参数名。纯业务数据。

**结构**：

```
TYPE_KNOWLEDGE = {
    "RStoic": {
        "category": "化学计量反应器",
        "key_parameters": {"TEMP": "反应温度", "PRES": "反应压力", ...},
    },
    ...
}
DEFAULT_CATEGORY = "其他"
```

**改造动作**：只删顶部 3 行死导入，字典内容**一个字都不动**。

**坑**：新增设备类型时，键必须与 `MDLTYPE` 的返回值**大小写完全一致**（驼峰，如 `"RadFrac"`、`"DSTWU"`、`"RCSTR"`）。全大写的 `BLKTYPE` 只有在 `real_type` 查不到时才会兜底。

---

## 六、自检清单

- [ ] 三个文件的死导入已删（`os` / `json` / `win32`），`reader.py` 的**没删**
- [ ] `cd CMV1` 后 `python -c 'import tools.process_data_get.reader'` 无报错（注意导入根是 `CMV1/`，不是项目根）
- [ ] 用 `10万吨环己烷.bkp` 跑一次，与 `baseline_data_get.json` 逐键 diff 为空
- [ ] `stream_count` / `block_count` / `connection_count` 与基线一致
- [ ] `simulation_status.status` 与基线一致
- [ ] 跑完后任务管理器里**没有残留的 Aspen 进程**
- [ ] 连续跑两次，结果一致（排除 COM 状态污染）
- [ ] `.apwz` 文件也能读（如果手头有）
