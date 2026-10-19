# 01 · analyze 模块

> 覆盖 `CMV1/tools/analyze/` 全部 7 个文件
> 对外只暴露两个名字：`analyze`、`analyze_process`（见 `__init__.py`）

---

## 一、定位

**它做的事**：拿到 `data_get_process` 返回的流程数据（一个大 dict），做三件事——体检、追组分、比前后变化，产出给模型读的结构化结论。

**它不碰**：Aspen COM（数据已经读好了）、MATLAB、文件系统。纯内存数据变换。这就是它排改造顺序第一的原因：**喂一个 dict 就能测，出错成本最低**。

**调用链**：

```
tools_register.analyze_process(component, change_threshold)
        │  data = get_cached_process_data()
        ▼
analyze_main.analyze_process(process_data, component, change_threshold)   ← 薄封装，一行转发
        ▼
analyze_main.analyze(...)                                                 ← 主函数，6 步
        ├── _coerce_process_data(...)     输入规整
        ├── basic_checks.check_process()  体检
        ├── component_track.find_component()   可选，传了 component 才跑
        └── change_analysis.detect_stream_changes()
                └── change_analysis.compare_streams()   每个进×出组合调一次
```

**文件职责表**：

| 文件 | 行数 | 职责 | 对外函数 |
|---|---:|---|---|
| `__init__.py` | 1 | 包导出 | `analyze`、`analyze_process` |
| `analyze_main.py` | 521* | 入口 + 编排 | `analyze_process`（`analyze` 供内部/测试） |
| `basic_checks.py` | 711* | 单流股 + 全流程体检 | `check_stream`、`check_process` |
| `change_analysis.py` | 489* | 塔/反应器前后流股对比 | `compare_streams`、`detect_stream_changes` |
| `component_track.py` | 305* | 某组分沿全部流股的分布 | `find_component` |
| `utils.py` | 82 | 取值 / 转数 / 找键 | 全部私有（`_` 开头） |
| `component_dicts.py` | 62 | 中文名 → Aspen ID 别名表（**已上移到 `tools/component_dicts.py`**，见 5.6） | `COMPONENT_ALIASES` |

\* 行数含已插入的 `[qoder 指导]` 注释；重写完成后应回落到 60% 左右。

---

## 二、改造清单

| # | 文件 | 问题 | 动作 | 风险 |
|---|---|---|---|---|
| 1 | `utils.py` | 已重写完成（199 → 82 行） | **保持现状**，当范本 | — |
| 2 | `analyze_main.py` | `from .utils import _number, _value, _unit, _numeric_value, _find_key` 五个符号**一个都没用** | 整行删除 | 低 |
| 3 | `analyze_main.py` | `compare_streams` 本文件未使用 | import 行只留 `detect_stream_changes` | 低 |
| 4 | `basic_checks.py` | `_find_key` / `_number` / `_unit` / `_value` 四个都是死导入（实测只用 `_numeric_value`，6 处） | import 行只留 `_numeric_value` | 低 |
| 5 | `basic_checks.py` | `import json` 未使用 | 删除 | 低 |
| 6 | `change_analysis.py` | `_find_key` / `_number` / `_value` 死导入（实测用 `_numeric_value` 4 处、`_unit` 2 处） | import 行只留这两个 | 低 |
| 7 | `change_analysis.py` | `import json` 未使用 | 删除 | 低 |
| 8 | `component_track.py` | `_number` / `_value` 死导入（实测用 `_find_key` 3 处、`_numeric_value` 3 处、`_unit` 3 处） | import 行只留这三个 | 低 |
| 9 | `component_track.py` | `import json` 未使用 | 删除 | 低 |
| 10 | `basic_checks.py` | `check_process` 步骤 8：检查"block 缺 details"却报成 `missing_output_stream`，且 `stream` 用上一步循环的残留变量 | 二选一：保留（行为一致）/ 修正（对拍标差异） | 中 |
| 11 | 全部 4 个文件 | "一参数一行"格式膨胀 | 按 `draw_mat` 密度压缩 | 低 |
| 12 | `analyze_main.py` | `_coerce_process_data` **定义了两次**：L43 是施工残留的空壳（只有 `if isinstance(dict): return None`），L90 才是正确版 | 删掉 L43–88 整段（含空壳 + 指导注释） | **高** |

> 第 10 条是本次唯一涉及**行为**的改动点，详见第五节 `check_process`。
> 第 12 条是**当前代码里实际存在的坑**：靠"后定义覆盖先定义"才能跑，重写时别把顺序弄反。

---

## 三、为什么这么改

### 3.1 为什么先删 `_stream_summary`

证据链（已用 AST 扫全仓库，跳过 `.venv`）：

| 验证方式 | 结果 |
|---|---|
| 字符串搜索 `_stream_summary` | 15 处命中，全是 import / 注释 / `def` 本身 |
| AST 统计 `Name` + `Attribute` 引用 | **0** |
| 动态路径排查 | 无 `getattr`、无 `import *`、`__init__.py` 不 re-export、4 处 import 均无 `as` 别名 |

它是历史遗留：本想把一条流股的 T/P/汽化率包成摘要，但最终没人用。删除时连带清了 4 个文件的 import 名——**当时先删函数后没清 import，包直接 `ImportError`**，这就是"删函数必须同步清 import"的现场证据。

### 3.2 为什么 `analyze_main` 的 utils 导入要整行删

AST 实测：`analyze_main.py` 对 `_number` / `_value` / `_unit` / `_numeric_value` / `_find_key` 的引用数为 **0**。

原因是 `analyze` 只做编排：规整数据（自己实现）、调 `check_process`、调 `find_component`、调 `detect_stream_changes`、拼 summary。它自己一个数值都不拆。

留着这行 import 的代价不是性能（只多传几个名字），而是**误导**：下一个读代码的人会以为 `analyze` 里藏着取值逻辑，翻遍全文找不到，浪费十分钟。

### 3.3 为什么 `compare_streams` 不能删

它在 `change_analysis.py` 内部被 `detect_stream_changes` 调用（每个"进流股 × 出流股"组合一次）。虽然外部没人直接调它，但它是 `detect_stream_changes` 的实现依赖。

**判定死代码时，"没人从外部 import" 不等于 "没人用"**——必须看本文件内是否调用。这也是为什么 `analyze_main` 里 `from .change_analysis import compare_streams` 是死导入，但 `change_analysis.compare_streams` 函数本身是活的。

### 3.4 为什么格式要压缩

现状（`analyze_main.py` 的 `_coerce_process_data` 片段）：

```
    if isinstance(process_data, str):

        text = process_data.strip()

        if not text:

            return (
                None,
                "process_data 是空字符串",
            )
```

同样的逻辑，正常密度是：

```
    if isinstance(process_data, str):
        text = process_data.strip()
        if not text:
            return None, "process_data 是空字符串"
```

**代价不是行数，是阅读节奏**：每读一个判断要跳 2 个空行，10 个判断就是 20 次无效眼动。压缩后函数结构和分支层次一眼可见。

---

## 四、操作步骤

按这个顺序，每步都能单独验证：

1. **删 utils 的 `_stream_summary`**（已完成）→ `cd CMV1` 后跑 `python -c 'import tools.analyze'`，确认无 ImportError。
2. **清 4 个文件的 import 行**（已完成）→ 再跑一次导入检查。
3. **逐文件改 `analyze_main.py`**：删死导入 → **先删 L43–88 的重复空壳** → 压 `_coerce_process_data` → 压 `analyze` → 压 `analyze_process`。
4. **改 `basic_checks.py`**：删 `import json` + 死导入 → 压 `check_stream` 的"三步曲" → 压 `check_process` 的 10 步。
5. **改 `change_analysis.py`**：删死导入 → 压 `compare_streams` → 压 `detect_stream_changes`。
6. **改 `component_track.py`**：删死导入 → 压 `find_component`。
7. **对拍**：用同一份 dict 跑旧版（`git stash` 前保存的返回值）和新版，比 JSON。

---

## 五、逐块原子拆解

> 每块统一四问：**为什么需要它 → 输入输出 → 一条条写什么 → 坑在哪**

### 5.1 `utils.py`（已完成，当范本看）

#### `_number(value) -> float | None`

**为什么需要**：Aspen 读出来的数字，经过 COM → Python → JSON 字符串 → 模型，类型会漂移。上游给 `250`（int）、`"250.0"`（str）、`None`（没读到）、甚至 `True`（COM 布尔）都可能。后面的算术（求和、相减、比阈值）要求统一成 float。

**输入输出**：任意值进，`float` 或 `None` 出，**永不抛异常**。

**原子步骤**：

1. `if value is None: return None` —— None 没得转，先挡。
2. `if isinstance(value, bool): return None` —— **必须挡在 int 之前**。
3. `if isinstance(value, (int, float)): return float(value)` —— 本来就是数字，统一类型。
4. `try: return float(value) except (TypeError, ValueError): return None` —— 剩下的以字符串为主。

**坑**：Python 里 `True == 1`，`float(True)` 得 `1.0`。不挡 bool 的话，一个开关量会被当成"数值 1"混进统计。只接 `TypeError` / `ValueError` 两个异常——`float()` 只会抛这两个，其它异常真出现就该炸出来暴露 bug。

#### `_value(data) -> Any`

**为什么需要**：data_get 的字段有两种形态——标准 `{"value": 250, "unit": "C"}` 和老数据/裸值 `250`。调用方不该关心是哪种。

**原子步骤**：

1. `if isinstance(data, dict): return data.get("value")`
2. `return data` —— 不是字典，默认它本身就是值。

**坑**：只取值，**不做 float 转换**。转换是 `_number` 的活。混在一起会导致"想看原文的时候拿到被转过型的数"。

#### `_unit(data) -> str`

**为什么需要**：下游拼 ylabel / 图注要单位（`"Temperature / C"`）。

**原子步骤**：

1. `if isinstance(data, dict): return str(data.get("unit", ""))`
2. `return ""`

**坑**：返回 `""` 而不是 `None`。下游到处做字符串拼接，`""` 能直接拼，`None` 会 `TypeError`。

#### `_numeric_value(data) -> float | None`

**为什么需要**：90% 的场景既要取值又要转 float，这一行解决。

**写法**：`return _number(_value(data))`。

**坑**：注意执行顺序——先 `_value` 剥壳，再 `_number` 转型。写反了 `_number` 会拿到整个 dict。

#### `_find_key(query, keys) -> str | None`

**为什么需要**：同一个组分有至少三种写法——Aspen ID（`CYCLO-01`）、英文名（`CYCLOHEXANE`）、中文名（`环己烷`），还有大小写差异。用户和模型不会统一。

**原子步骤**：

1. `q = str(query).strip().lower()` —— 统一成去空白小写。
2. `if not q: return None` —— 空串直接放弃。
3. **一级·精确**：`for key in keys: if str(key).lower() == q: return key`
4. **二级·别名**：`for alias in COMPONENT_ALIASES.get(q, []):` 再逐个比 `keys`
5. **三级·子串**：双向包含 `q in key_lower or key_lower in q`
6. `return None`

**坑**：子串匹配会误命中（`"甲烷"` 是 `"十甲烷"` 的子串），**必须放最后**，前两级找不到才轮到它。

---

### 5.2 `analyze_main.py`

#### `_coerce_process_data(process_data) -> (dict | None, str | None)`

> ⚠️ **本文件里这个函数被定义了两遍**：L43 一个空壳（只有 `if isinstance(process_data, dict): return None`），L90 才是正确实现。模块加载时后者覆盖前者，所以现在能跑。重写时**只保留一份**，把 L43–88 整段（空壳 + `[qoder 指导]` 注释）删干净。

**为什么需要**：这个函数存在的唯一理由是**容错**。调用方可能给：

- `dict`（正常，`tools_register` 走的路径）；
- `bytes`（某些 RPC / 文件读取路径）；
- `str`（**JSON 字符串**——LangChain 的某些链路会把 dict 序列化后传）；
- 其它（`None`、`int`……出错）。

函数返回**元组**：`(数据, 错误信息)`。第一项有值就第二项是 `None`；反之第一项 `None`。

> 易错点：不是"返回 null"。Python 没有 null，这里的第二项 `None` 才相当于"没有错误"。

**原子步骤**：

1. `if isinstance(process_data, dict): return process_data, None` —— 最快路径，先处理。
2. `if isinstance(process_data, (bytes, bytearray)):` → `try: text = process_data.decode("utf-8") except UnicodeDecodeError: return None, "..."` → 然后**递归** `return _coerce_process_data(text)`。递归是为了复用下面的字符串分支，不用写两遍 JSON 解析。
3. `if isinstance(process_data, str):`
   - `text = process_data.strip()`
   - `if not text: return None, "process_data 是空字符串"`
   - `try: data = json.loads(text) except Exception: return None, "process_data 不是合法 JSON：" + str(e)`
   - `if not isinstance(data, dict): return None, "process_data JSON 不是对象（dict）"`
   - `return data, None`
4. 兜底：`return None, "process_data 类型不支持：" + type(process_data).__name__`

**坑**：`json.loads` 接 `Exception` 是合理的（JSONDecodeError 之外还可能有编码问题）；但**不要**在 decode 那里也接 `Exception`——只接 `UnicodeDecodeError`，其它异常该暴露。

#### `analyze(process_data, component=None, change_threshold=0.05) -> dict`

**为什么需要**：编排层。把"体检、追踪、对比"三个独立能力拼成一份结论。

**返回结构（契约，键名不可改）**：

```
成功: {"success": True, "summary": {...}, "findings": [...],
       "component_tracking": [...], "stream_changes": [...]}
失败: {"success": False, "error": "...", "findings": [一条 error 记录]}
```

**原子步骤**：

1. **规整**：`data, coerce_error = _coerce_process_data(process_data)`（元组解包）。
   `if coerce_error is not None:` → 返回失败 dict，`findings` 里塞一条 `{"level":"error","type":"invalid_process_data","message":coerce_error}`。
2. **短路**：`if not data.get("success", False):` → 上游 data_get 自己失败，往下分析没意义。失败 `error` 取 `data.get("error", "未知错误")`，findings 的 type 用 `"data_get_failed"`。
3. **体检**：`findings = check_process(data)`。
4. **统计 summary**（5 个 int）：

   ```
   streams = data.get("streams", {})
   blocks = data.get("blocks", [])
   connections = data.get("connections", [])
   stream_count = len(streams) if isinstance(streams, dict) else 0
   block_count = len(blocks) if isinstance(blocks, list) else 0
   connection_count = len(connections) if isinstance(connections, list) else 0
   error_count = sum(1 for x in findings if x.get("level") == "error")
   warning_count = sum(1 for x in findings if x.get("level") == "warning")
   ```

   为什么每个 `len()` 前都判类型：字段可能缺失或类型不对（上游半失败时），不判会 `TypeError`。
5. **组分追踪（可跳过）**：`component_tracking = []`；`if component: component_tracking = find_component(data, component)`。
6. **前后变化**：`stream_changes = detect_stream_changes(data, threshold=change_threshold)`。
   **注意关键字**：函数参数名是 `threshold`，调用方的参数名是 `change_threshold`，别写混。
7. **组装返回**：5 个键原样拼回去。

**坑**：第 4 步的 `summary` 键名（`stream_count` / `block_count` / `connection_count` / `error_count` / `warning_count`）是模型和报告模板在读，一个都不能改。

#### `analyze_process(process_data, component=None, change_threshold=0.05)`

**为什么需要**：`tools_register` 按这个名字 import；它和 `analyze` 的区别只是"对外名字"。保留两层是为了让 `analyze` 可以随手加调试参数而不影响契约。

> 注意两层签名不同：这里的 `analyze_process` 首参是 `process_data`（内部实现）；`tools_register.py` 里的 `@tool` 包装不带它（数据从缓存取），模型只看到 `component` / `change_threshold` 两个参数。

**写法**：一行 `return analyze(process_data, component=component, change_threshold=change_threshold)`。

---

### 5.3 `basic_checks.py`

#### `check_stream(stream_name, stream) -> list[dict]`

**为什么需要**：把"一条流股长得对不对"的判断集中在一个函数里，`check_process` 才能只负责遍历。

**输入输出**：流股名 + 流股 dict 进，`findings` 列表出（可能为空）。

**核心模板——三步曲**，10 项检查全是这个形状：

1. **取值**：`value = _numeric_value(stream.get("temperature"))`
2. **判条件**：`if value is None:` / `if value < 0:` / ……
3. **append 一条**：

   ```
   findings.append({
       "level": "error" | "warning" | "info",
       "type": "missing_temperature",
       "message": "……",
       "stream": stream_name,
   })
   ```

**10 项检查清单**（按原实现顺序，`level` 别改）：

| # | type | 触发条件 | level | 附加字段 |
|---|---|---|---|---|
| 1 | `invalid_stream` | stream 不是 dict（**直接 return**，后面 9 项不再跑） | error | `stream` |
| 2 | `missing_temperature` | `temperature` 取不到数 | warning | `stream` |
| 3 | `missing_pressure` | `pressure` 取不到数 | warning | `stream` |
| 4 | `invalid_pressure` | `pressure <= 0`（**elif**，第 3 项不成立才查） | error | `stream` `value` |
| 5 | `invalid_vapor_fraction` | 汽化率非 None 且 `< 0` 或 `> 1` | **error** | `stream` `value` |
| 6 | `negative_mass_flow` | `mass_flow` 里**某个组分**的流量 < 0 | error | `stream` `component` `value` |
| 7 | `negative_mole_flow` | `mole_flow` 里**某个组分**的流量 < 0 | error | `stream` `component` `value` |
| 8 | `invalid_mole_fraction` | `mole_fraction` 里**某个组分**的分率 < 0 或 > 1 | **error** | `stream` `component` `value` |
| 9 | `fraction_sum_abnormal` | `abs(Σ分率 - 1) > 0.01` | warning | `stream` `value` |
| 10 | `empty_stream_data` | `mole_fraction` / `mole_flow` / `mass_flow` **三个 dict 全为空** | warning | `stream` |

**坑**：

- 第 6/7 项是**逐组分**判断，不是"总流量求和后判断"。`mass_flow` 本身就是 `{组分: {value, unit}}`，代码直接遍历，**不做求和**——改代码时别"优化"成 `sum`，那会把一个组分的负值平均掉。
- 分率总和只在**有效值个数 > 0** 时才算（`valid_fraction_count > 0`），容差写死 **0.01**。
- 第 10 项只看三个组分字段，**不看** temperature / pressure。一条只有 T/P、没有组分的流股会同时报 `empty_stream_data`。
- `level` 有三种取值，`"info"` 只出现在 `check_process` 的 `simulation_ok`。`analyze` 的 summary 只统计 error / warning，别把 info 算进去。

#### `check_process(process_data) -> list[dict]`

**为什么需要**：全流程体检的入口，遍历所有流股 + 校验 block / connection 一致性 + 读模拟状态。

**原子步骤（10 步，顺序不可调换）**：

1. `findings = []`。
2. **入参不是 dict** → 直接 `return [{level: error, type: invalid_process_data}]`。
3. **`success` 为假** → 直接 `return [{level: error, type: data_get_failed, message: "data_get 执行失败：" + error}]`。**这是"上游失败"的唯一出口**，模型看到它就别再往下分析。
4. 取 `streams`；不是 dict → append 一条 `invalid_streams` 后**立即 return**（后面所有检查都依赖 streams）。
5. `for name, stream in streams.items(): findings.extend(check_stream(name, stream))` —— **`extend` 不是 `append`**（`append` 会把整个列表塞成一个元素）。
6. 取 `blocks` / `block_details` / `connections`。
7. **归一化 `block_details`**：list → 每条取 `"block"` 字段；dict → 取 keys。得到 `detail_names` 集合。
8. **检查 block 是否都有 details**：遍历 `blocks`，`detail_names` 非空且 `block_name not in detail_names` → append 一条 `missing_output_stream`。
   - ⚠️ **这里是历史瑕疵点，两个问题叠在一起**：
     - `type` 写成 `missing_output_stream`，实际检查的是"block 缺 details"——语义标错；
     - `"stream": str(stream_name)` 用的是**第 5 步循环残留的变量**，不是任何有意义的流股名。
   - 触发概率很低：`detail_names` 为空时整个检查跳过，而正常 data_get 一定产出 `block_details`。
9. **检查 connections 引用的流股**：
   - `stream_names = {str(n) for n in streams}`
   - `inputs` 里的名字不在 → `missing_input_stream`（warning，带 `block` / `stream`）
   - `outputs` 里的名字不在 → `missing_output_stream`（warning，带 `block` / `stream`）
   - **两个 for 分开写**，不要合并——type 名不同。
10. **模拟状态**（`simulation_status` 是 dict 时）：
    - `status == "error" or error_count` → `simulation_error`（error 级，带 `error_count`，消息里拼 errors）
    - `elif status == "ok"` → `simulation_ok`（**info 级**，不进 summary 的 error/warning 计数）
    - `"unknown"` → 什么都不记。

**findings 类型总表**（这些 type 是模型读的消息协议，改名 = 改契约）：

| type | level | 来源 |
|---|---|---|
| `invalid_process_data` | error | 入参不是 dict（步骤 2） |
| `data_get_failed` | error | 上游 `success=False`（步骤 3） |
| `invalid_streams` | error | `streams` 不是 dict（步骤 4） |
| `missing_output_stream` | warning | ① block 缺 details（步骤 8，语义错标）② connection 的 output 流股不存在（步骤 9） |
| `missing_input_stream` | warning | connection 的 input 流股不存在（步骤 9） |
| `simulation_error` | error | Aspen 报错（步骤 10） |
| `simulation_ok` | info | Aspen 正常（步骤 10） |

**坑**：

- 步骤 8 和步骤 9 产出**同名** `missing_output_stream`，含义完全不同。如果以后要拆，必须同时改读 `type` 的下游分支，否则报告归类会错。
- `"unknown"` 不产出任何 finding——有意为之，"没读到状态"不等于"没问题"。
- 改步骤 8 是**唯一**会改变输出的地方。改之前先想清楚下游：报告/文本若读 `f.get("stream")` 拼 bullet，修正后文字会变。

---

### 5.4 `change_analysis.py`

#### `compare_streams(process_data, stream_a, stream_b) -> dict`

**为什么需要**：设备前后的物料组成变化，是"这个塔/反应器到底干了什么"的直接证据。

**返回结构**：

```
成功: {"success": True, "stream_a": ..., "stream_b": ..., "components": [
          {"component": "CYCLO-01", "from": 0.47, "to": 0.02, "absolute_change": 0.45},
          ...
       ]}
失败: {"success": False, "error": "..."}
```

**原子步骤（8 步）**：

1. 校验两条流股都存在，否则 `{"success": False, "error": ...}`。
2. 各取 `mole_fraction`，不是 dict 就失败。
3. 建**大小写不敏感的映射**：
   `a_map = {str(n).lower(): n for n in a_fraction}` —— 键是小写，值是原始名。
4. 取并集：`component_keys = set(a_map) | set(b_map)`。
5. `for key in sorted(component_keys):` 保证输出顺序稳定（对拍时很重要）。
6. 两边取值：`a_val = _numeric_value(a_fraction.get(a_map.get(key, ""), {}))`，**缺失的组分按 0.0 处理**（"从无到有"是真实变化）。
7. 算 `absolute_change = abs(to - from)`。
8. append 一条 `{"component": 原始名, "from": a_val, "to": b_val, "absolute_change": ...}`。

**坑**：

- 并集遍历，不是只遍历 A —— 只遍历 A 会漏掉"B 里新出现的组分"。
- `sorted()` 不能省：`set` 的遍历顺序在 Python 里不稳定，不排序会导致每次运行输出顺序不同，对拍必失败。
- 某一边取不到值时给 `0.0` 还是 `None`？原实现是 0.0，保持。

#### `detect_stream_changes(process_data, threshold=0.05) -> list[dict]`

**为什么需要**：一个流程有几十个设备，逐个手比不现实。这个函数自动找"进出差异明显"的组合。

**原子步骤（7 步）**：

1. `results = []`。
2. 取 `connections`，不是 list 就返回空列表。
3. `for connection in connections:` 跳过非 dict。
4. 取 `block` / `inputs` / `outputs`，类型不对就置空。
5. `for input_stream in inputs: for output_stream in outputs:` —— **双重循环**，一个设备 N 进 M 出就是 N×M 次比较。
6. `comparison = compare_streams(process_data, 输入, 输出)`；失败就 `continue`。
7. 过滤：`significant_components = [item for item in comparison["components"] if item["absolute_change"] >= threshold]`；非空才 append 一条 `{"block", "from_stream", "to_stream", "significant_components"}`。

**坑**：

- 阈值比较用 `>=` 不是 `>`（原实现），改了对拍会有边界差异。
- 只有"进"没有"出"（或反之）的设备会跳过，这是对的——没有对比对象。

---

### 5.5 `component_track.py`

#### `find_component(process_data, component) -> list[dict]`

**为什么需要**：回答"这个组分在流程里怎么流动"——每条流股里它占多少、流量多少。

**返回**：按某个字段降序排好的列表，每条 8 个键：

```
{"component": "CYCLO-01", "stream": "S5",
 "mole_fraction": 0.47, "mole_fraction_unit": "...",
 "mole_flow": 47.3, "mole_flow_unit": "kmol/h",
 "mass_flow": 3980.0, "mass_flow_unit": "kg/h"}
```

**原子步骤（7 步）**：

1. `if not component: return []`。
2. 取 `streams`，不是 dict 返回 `[]`。
3. `for stream_name, stream in streams.items():` 跳过非 dict。
4. **三级匹配找键**：`key = _find_key(component, list(stream.get("mole_fraction") or {}))`。
   为什么 `list(字段.keys())`：`_find_key` 收的是"键名列表"，不是字典。
5. 找不到就 `continue`（这条流股里没有该组分）。
6. 三个字段各取一次：分率 / 摩尔流 / 质量流，`_numeric_value` + `_unit` 配套。
7. 排序：`results.sort(key=lambda x: x["mole_fraction"] if x["mole_fraction"] is not None else -float("inf"), reverse=True)`。

**坑**：

- 排序时 `None` 要用 `-float("inf")` 垫底，不能直接比——`None < 0.5` 会 `TypeError`。
- `"component"` 字段填的是**匹配到的原始键名**（`CYCLO-01`），不是用户输入的 `环己烷`。下游报告靠这个显示真实 ID。

---

### 5.6 `component_dicts.py`

**为什么存在**：中文名 → 英文名 / Aspen ID 的映射表，`utils._find_key` 的二级匹配数据源。

**结构**：

```
COMPONENT_ALIASES = {
    "环己烷": ["cyclohexane", "cyclo-01", "c6h12"],
    ...
}
```

**改造动作**：**内容不动，但位置会变**。见 [02-draw_mat.md](02-draw_mat.md) 操作步骤第 3 步：为了让 `draw_mat` 也能用同一份别名表，这个文件会被上移到 `tools/component_dicts.py`（工具层公共数据）。届时本包 `utils.py` 的 `from .component_dicts` 要同步改成 `from ..component_dicts`。

**内容**不动：这是业务数据，不是代码逻辑。唯一注意——新增组分时保持"键=中文名，值=小写别名列表"，因为 `_find_key` 查表前已经 `lower()` 过。

---

## 六、自检清单

改完逐项打勾：

- [ ] `cd CMV1` 后 `python -c 'import tools.analyze'` 无报错
- [ ] 4 个文件的 import 行只剩真正用到的符号（对照本文第二节清单）
- [ ] `analyze` 对 4 种输入行为正确：正常 dict / JSON 字符串 / 坏 JSON / 上游失败 dict
- [ ] `analyze` 返回的 5 个键名没变
- [ ] `check_process` 的 findings 条数与旧版一致（步骤 8 若顺手修语义，单独记差异）
- [ ] `find_component` 用中文名和 Aspen ID 传参，结果一致
- [ ] `detect_stream_changes` 输出顺序稳定（连跑两次 JSON 完全相同）
- [ ] `utils._find_key` 三级匹配各有一个用例（精确 / 别名 / 子串）
- [x] 02 的别名表迁移已执行：`component_dicts.py` 在 `tools/` 下，本包 `from ..component_dicts` 已生效，`import tools.analyze` 正常
