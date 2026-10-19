# 02 · draw_mat 模块

> 覆盖 `CMV1/tools/draw_mat/` 全部 6 个文件 + `matlab/` 目录
> 对外只暴露一个名字：`draw_mat`（`draw_mat.py` 里的同名函数）

---

## 一、定位

**它做的事**：把流程数据拆成 MATLAB 认识的二维表，落成 job 目录，喊 MATLAB 画图，再把图片路径捞回来。

**它不碰**：不读 Aspen（数据来自缓存）、不生成报告（图交给 `report_create` 引用）。

**调用链**：

```
tools_register.draw_mat(plot_type, stream=..., component=..., ...)
        │  不传 process_data，从缓存取
        ▼
draw_mat.draw_mat(...)                    ← 主函数，10 步
        ├── _resolve_process_data()       取缓存 / 用显式传入
        ├── tables.split_for_plot()       按图种拆表
        │       ├── split_stream_tp
        │       ├── split_stream_composition
        │       ├── split_component_track
        │       └── split_balance_check
        ├── jobs.create_job_dir()         建 jobs/<模型名>_xxxxxxxx/
        ├── jobs.write_job()              写 data.csv + request.json
        ├── matlab_backend.run_draw_dispatch()   调 MATLAB
        │       ├── _try_engine()         MATLAB Engine（优先）
        │       └── _run_batch()          matlab -batch（回退）
        └── jobs.read_result()            读 result.json
```

**文件职责表**：

| 文件 | 行数 | 职责 | 处置 |
|---|---:|---|---|
| `draw_mat.py` | 273 | 主入口 + 10 步编排 | 删死代码，压格式 |
| `tables.py` | 315 | 四种图的数据拆分（纯逻辑） | **修 1 个 bug** |
| `jobs.py` | 125 | job 目录的建/写/读 | 基本不动 |
| `matlab_backend.py` | 185 | MATLAB 调用（Engine / batch） | 基本不动 |
| `process_store.py` | 19 | 历史包装层 | **整个删除** |
| `test_draw_mat.py` | 143 | 单元测试 | **修 3 处** |
| `matlab/` | — | `.m` 绘图脚本 | 不动 |

---

## 二、改造清单

| # | 文件 | 问题 | 动作 | 风险 |
|---|---|---|---|---|
| 1 | `process_store.py` | 整个文件死代码 | **删除** | 无 |
| 2 | `draw_mat.py` | `tool_spec()` + `TOOL_DESCRIPTION` + `TOOL_PARAMETERS` 无调用者 | 删除（约 35 行） | 无 |
| 3 | `draw_mat.py` | `_default_draw_path` 三个候选路径里两个无效、fallback 也无效 | 简化成一个路径 | 低 |
| 4 | `tables.py` | `_lookup_component` 不支持中文别名，与 docstring 不符 | 修复（复用别名表） | **中** |
| 5 | `tables.py` | `_number` / `_vu` 与 `analyze/utils.py` 重复实现 | 二选一：保持独立 / 抽公共 | 低 |
| 6 | `test_draw_mat.py` | 相对导入 + 未定义名 + 缓存重置失效 | 修 3 处 | 低 |
| 7 | `matlab_backend.py` | `_discover_matlab_bin` 写死 `E:\AM1` 等本机路径 | 保留但加注释，或移到配置 | 低 |
| 8 | `draw_mat.py` | `wrap_data_get` 只有测试在用 | 保留（测试依赖）或随测试一起删 | 低 |

---

## 三、为什么这么改

### 3.1 为什么 `process_store.py` 整个可以删

这个文件只做两件事：

```
wrap_data_get   —— 从 draw_mat 转手再导出一遍
wrap_draw_mat   —— return fn or _draw_mat，纯透传
```

证据：

| 检查 | 结果 |
|---|---|
| `wrap_draw_mat` 全仓库调用 | **0 处**（只有定义和 docstring） |
| `wrap_data_get` 调用 | 只有 `test_draw_mat.py` 的一处测试 |
| 生产链路 | `tools_register.py` 直接 `from tools.draw_mat.draw_mat import draw_mat`，**根本不经过 process_store** |
| 缓存 | 真正干活的是 `CMV1/memory/process_cache.py`，`process_store` 只是把名字转手一次 |

它诞生在"还没有 `memory/` 模块"的年代，现在职责已经被 `memory.process_cache` 接管。保留它只会让后来者困惑：到底该从 `draw_mat` 还是 `process_store` 导缓存函数？

**删除后要检查**：`test_draw_mat.py` 若用到 `wrap_data_get`，改成从 `draw_mat` 导入。

### 3.2 为什么 `tool_spec` 三件套要删

`tools_register.py` 用 LangChain 的 `@tool(parse_docstring=True)`，工具说明书来自**函数 docstring**。`TOOL_DESCRIPTION` / `TOOL_PARAMETERS` / `tool_spec()` 是旧的手写 JSON Schema 时代的产物。

全仓库搜索 `tool_spec`：只有 `draw_mat.py` 和 `sections.py` 里的定义本身，**零调用**。`TOOL_DESCRIPTION` / `TOOL_PARAMETERS` 只被 `tool_spec()` 引用，属于"死代码引用死代码"。

### 3.3 为什么 `_lookup_component` 要修

`split_component_track` 的 docstring 写着：

> component 必填（**中文名或 Aspen ID 均可**，大小写不敏感）

**修复前**，`_lookup_component` 只有大小写不敏感的精确匹配：

```
target = str(component).lower()
for name in mapping:
    if str(name).lower() == target:
        return str(name), mapping[name]
return None, None
```

用户传 `"环己烷"`，而数据里的键是 `"CYCLO-01"` → 直接 `data_not_found`。

对比 `analyze/utils.py` 的 `_find_key`：人家有三级匹配（精确 → 别名表 → 子串）。同一个产品，两个工具对"组分名"的支持程度不一样，这是**行为不一致 bug**。

**✅ 已修复**：别名表从 `analyze/component_dicts.py` 上移到 `tools/component_dicts.py`，`tables.py` 按三级匹配重写，新增 `test_track_chinese_alias` 并通过。代码见 5.3。

### 3.4 为什么 `_default_draw_path` 要简化

当前实现：

```
here = Path(__file__).resolve()            # CMV1/tools/draw_mat/draw_mat.py
for cand in (
    here.parents[0] / "draw_mat" / "matlab",   # → draw_mat/draw_mat/matlab   ❌ 不存在
    here.parents[1] / "draw_mat" / "matlab",   # → tools/draw_mat/matlab      ✅ 唯一有效
    here.parents[2] / "tools" / "draw_mat",    # → tools/draw_mat             ❌ 没有 draw_dispatch.m
):
    ...
return here.parents[0] / "matlab" / "draw"     # → draw_mat/matlab/draw       ❌ 不存在
```

三个候选 + 一个 fallback，**只有第二个能命中**。这是历史上文件被搬过几次留下的痕迹。

正确写法一行：

```
return Path(__file__).resolve().parent / "matlab"
```

保留环境变量 `CHEMMATE_MATLAB_DRAW` 覆盖能力。

顺带：函数顶部的 `# ds: 重组后 draw_mat.py 位于 CMV1/，matlab/draw 就在同级的 CMV1/matlab/draw，即 parents[0]` 这段注释也是**过期**的（描述的是旧目录结构），一起删掉或改正。

### 3.5 为什么 `_number` / `_vu` 的重复可以先不处理

`tables.py` 有一套 `_number` + `_vu`，`analyze/utils.py` 有一套 `_number` + `_value` + `_unit` + `_numeric_value`。逻辑几乎一样。

三种处置：

| 方案 | 优点 | 缺点 | 建议 |
|---|---|---|---|
| 各自保留 | 模块自治，互不依赖 | 改逻辑要改两处 | ✅ 本次推荐 |
| draw_mat 从 analyze 导入 | 一处维护 | `draw_mat` 依赖 `analyze`，包边界变糊 | 不推荐 |
| 抽到 `tools/common/` | 最干净 | 多一层目录，迁移成本 | 下次重构再做 |

理由：`draw_mat` 和 `analyze` 是两个独立工具，未来可能拆成两个服务。为了省 10 行代码把它们的 import 图连起来不值得。**但别名表例外**——别名表是业务数据（新组分要加），必须只有一份，见 3.3。

---

## 四、操作步骤

1. ✅ **删 `process_store.py`** → 全局搜 `process_store` 确认零引用 → 删文件。
2. ✅ **修 `test_draw_mat.py`** → 已改成包内测试，跑法变了（详见 5.6）：
   `cd CMV1` 后执行 `python -m tools.draw_mat.test_draw_mat`，9 个用例全绿。
3. ✅ **先搬别名表**：`git mv tools/analyze/component_dicts.py tools/component_dicts.py`，再把 `analyze/utils.py` 的 `from .component_dicts` 改成 `from ..component_dicts`。
   为什么必须先搬：`tables.py` 要写的 `from ..component_dicts import COMPONENT_ALIASES` 里，`..` 从 `draw_mat/` 指向 `tools/`——不搬就是 ImportError。
4. ✅ **修 `tables.py` 的 `_lookup_component`** → 三级匹配已实现，`test_track`（传 `"cyclo-01"`）仍走一级匹配命中，结果不变。
5. ✅ **加别名测试**：`test_track_chinese_alias` 传 `"环己烷"`，断言 `matched_component == "CYCLO-01"`，已通过。
6. **删 `draw_mat.py` 的 `tool_spec` 三件套** → 导入检查。
7. **简化 `_default_draw_path`** → 跑一次真实 `dry_run=False` 或至少确认路径存在。
8. **压格式**（可选）→ 对拍 `dry_run=True` 的返回 JSON。

---

## 五、逐块原子拆解

### 5.1 `draw_mat.py` · 主函数 `draw_mat`

**为什么需要**：它是 Python 侧的总调度。所有"图能不能画出来"的判断都在这 10 步里。

**输入**：`plot_type` + 若干筛选参数 + 内部参数（`process_data` / `matlab_draw_path` / `jobs_root` / `dry_run`）。

**输出**：统一 dict，成功带 `image_path`，失败带 `error` + `message`，两种都带 `warnings`。

**10 步**：

1. **规整参数**
   `pt = (plot_type or "").strip().lower()`
   `export_fmt = (export or "png").strip().lower()`
   `if export_fmt not in ("png", "svg"): return _fail(pt, "spec_invalid", "export 必须是 png 或 svg")`
   为什么先校验 export：白名单外的格式传给 MATLAB 会变成"MATLAB 报错"，错误信息很难读；在这里拦掉，模型能立刻看懂。

2. **取数据**
   `data = _resolve_process_data(process_data)` —— 可能抛 `DrawError`。

3. **拆表**
   `rows, warnings, labels = split_for_plot(pt, data, streams=..., stream=..., component=..., block=..., value_field=...)`
   2、3 步包在同一个 `try` 里，`except DrawError as exc: return _fail(pt, exc.code, exc.message)`。

4. **推模型名**（用于 job 目录命名）
   `fp = data.get("file_path")`；`model_name = Path(str(fp)).stem if fp else None`
   目的：job 目录叫 `10万吨环己烷_ab12cd34`，一眼看出属于哪个任务。

5. **建 job 目录**
   `job_dir = create_job_dir(jobs_root or _default_jobs_root(), name=model_name)`

6. **定标题**
   `auto_title = title or _caption(pt, title, labels)`
   这里的 `title or` 是**冗余**的——`_caption` 内部第一句就是 `if title: return title`。两个都可以，但只留一处才干净（推荐保留 `_caption` 内部的，外面直接 `auto_title = _caption(pt, title, labels)`）。

7. **写 job**
   `write_job(job_dir, pt, rows, title=auto_title, export=export_fmt, ylabel=..., ylabel_left=..., ylabel_right=...)`
   产出 `data.csv` + `request.json`。

8. **调试分支**
   `if dry_run: return {...}` —— 不调 MATLAB，只回报"拆了几行、命中哪个组分"。**这是你本地验证拆表逻辑的唯一入口**。

9. **调 MATLAB**
   `draw_path = Path(matlab_draw_path) if matlab_draw_path else _default_draw_path()`
   `try: run_draw_dispatch(job_dir, draw_path) except MatlabFailed as exc: return _fail(pt, "matlab_failed", exc.message, warnings)`

10. **读结果**
    `matlab_res = read_result(job_dir)`
    `if not matlab_res.get("ok"): return _fail(...)`
    成功：`image_path = str(matlab_res.get("image_path") or (job_dir / f"figure.{export_fmt}"))`，返回完整成功 dict。

**坑**：

- 第 8 步的 `dry_run` 分支必须保留。删了就没法在不装 MATLAB 的机器上验证拆表。
- 成功返回里的 `meta` 来自 MATLAB 的 `result.json`，不是 `labels`。别搞混。
- 失败返回也要带 `warnings`（第三参数），否则"部分流股被跳过"的信息会丢。

### 5.2 `draw_mat.py` · 四个辅助

| 函数 | 为什么需要 | 实现要点 | 坑 |
|---|---|---|---|
| `_fail(plot_type, code, message, warnings=None)` | 失败返回体有 9 个固定键，散着写容易漏 | 直接 `return {...}`，`warnings or []` | 键名必须与成功返回对齐（模型按统一结构读） |
| `_caption(plot_type, title, extra)` | 模型不传 title 时也得有图注 | 有 title 用它；否则按四种图种给中文默认值 | `component_track` 要读 `extra["matched_component"]` |
| `_resolve_process_data(process_data)` | 统一"显式传入"和"缓存"两条路 | 有 dict 就 `remember_process_data` 并返回；否则取缓存；都没有抛 `DrawError("missing_process_data", …)` | 显式传入时**要顺手写缓存**，保持后续调用一致 |
| `wrap_data_get(fn)` | 装饰器：包一层后返回值自动进缓存 | `@wraps(fn)` + `return remember_process_data(fn(*args, **kwargs))` | 现在只有测试在用；若删 `process_store`，记得改测试的导入 |

`_default_jobs_root()`：环境变量 `CHEMMATE_JOBS_DIR` 优先，否则 `Path(__file__).resolve().parents[2] / "jobs"`（= `CMV1/jobs`）。
**不能用 `Path.cwd()`**——历史事故：UI 曾从 `CMV1/ui` 启动，cwd 是 `ui/`，图会落到前端放行目录之外，浏览器 403（`ui/` 目录现已移除，但"cwd 不可信"的约束仍然成立）。

`_default_draw_path()`：见 3.4，简化成 `Path(__file__).resolve().parent / "matlab"`。

---

### 5.3 `tables.py`

#### `_number(value) -> float | None`

与 `analyze/utils._number` 同构：`None` → None、`bool` → None、`int/float` → float、其它 `try float()`。
**坑**：bool 必须挡，`True` 会变成 `1.0`。

#### `_vu(data) -> (float | None, str)`

**为什么需要**：一行同时拿"数值 + 单位"，因为画图两个都要（值用于画，单位用于轴标签）。

**写法**（下面这段是 `_vu` 的**函数体**（缩进 4 空格），**不是** `_lookup_component`；上一个坑就是把这段误粘到它里）：

```
    if isinstance(data, dict):
        return _number(data.get("value")), str(data.get("unit") or "")
    return _number(data), ""
```

**坑**：`str(data.get("unit") or "")` 里的 `or ""` 不能省——`unit` 可能是 `None`，`str(None)` 会得到 `"None"` 这个字符串，轴标签会变成 `"Temperature / None"`。

#### `_streams(process_data) -> dict`

**为什么需要**：四种图都要取 `streams`，取不到要报同一个错。

**写法**：不是 dict 或为空 → `raise DrawError("missing_process_data", "process_data.streams 无效或为空")`。

#### `_lookup_component(mapping, component) -> (str | None, Any)`

**为什么需要**：在"组分名 → {value, unit}"的映射里找到用户说的那个组分。

**✅ 已实现**（下面是 `tables.py` 里的真实代码，可直接对照；不要往 `for` 循环里插行）：

```python
from ..component_dicts import COMPONENT_ALIASES


def _lookup_component(mapping: Any, component: str) -> tuple[str | None, Any]:
    """在组分映射里找组分：精确 → 别名 → 子串，返回 (实际键名, 数据)。"""
    if not isinstance(mapping, dict):
        return None, None

    target = str(component).strip().lower()
    if not target:
        return None, None

    # 1. 精确
    for name in mapping:
        if str(name).lower() == target:
            return str(name), mapping[name]

    # 2. 别名（中文名 → Aspen ID / 英文名）
    for alias in COMPONENT_ALIASES.get(target, []):
        for name in mapping:
            if str(name).lower() == alias.lower():
                return str(name), mapping[name]

    # 3. 子串兜底（可能误命中，放最后）
    for name in mapping:
        name_lower = str(name).lower()
        if target in name_lower or name_lower in target:
            return str(name), mapping[name]

    return None, None
```

⚠️ 三个 `for` 循环必须**并列**，不能套在一起：套成一个大循环会让第一级没命中的键提前进入子串匹配，结果随字典顺序变化。

返回 `(实际键名, mapping[实际键名])`，找不到 `(None, None)`。

**为什么要复用别名表而不是各写一份**：用户说"环己烷"，数据里是 `CYCLO-01`。这个映射关系会随新组分增加，必须只有一份数据源。

**推荐做法**：把 `analyze/component_dicts.py` 上移到 `tools/component_dicts.py`（工具层公共数据），然后：

- `analyze/utils.py`：`from .component_dicts` → `from ..component_dicts`
- `draw_mat/tables.py`：新增 `from ..component_dicts import COMPONENT_ALIASES`

**坑**：别名表的键是中文名且已小写；查表前必须 `target = str(component).strip().lower()`。

#### `_stream_total_mole_flow(stream) -> float | None`

**为什么需要**：`balance_check` 要的是"这条流股总共流了多少摩尔"，而数据里是按组分拆开的。

**原子步骤**：

1. 取 `mole_flow`，不是 dict 或为空 → `return None`。
2. `total = 0.0`；`seen = False`。
3. 遍历每个组分的 `{value, unit}`，`_vu` 取值，`None` 跳过，否则 `total += v; seen = True`。
4. `return total if seen else None`。

**坑**：`seen` 标志不能省。如果所有组分都取不到值，`total` 还是 `0.0`——直接返回 0.0 会让衡算图画出"零流量"，看起来像真数据。必须返回 `None` 表示"没有数据"。

#### `split_stream_tp(process_data, streams) -> (rows, warnings, labels)`

**为什么需要**：图 1「流股温度-压力」的数据表，每行一条流股。

**原子步骤**：

1. `all_streams = _streams(process_data)`
2. `names = list(streams) if streams else list(all_streams.keys())`
3. 逐条：不存在 → warning 跳过；取 T/P，任一 `None` → warning 跳过；记录单位。
4. 一行 `{"stream": key, "T": t, "P": p}`。
5. 一行都没有 → `raise DrawError("data_not_found", "没有可画的流股 T/P 数据")`
6. labels：`{"ylabel_left": "Temperature / C", "ylabel_right": "Pressure / bar"}`（无单位时退化成 `"Temperature"`）。

**坑**：单位取的是**最后一条有效流股**的单位，不是第一条。混合单位的数据会画出错误标签——原实现就这样，保持。

#### `split_stream_composition(process_data, stream)`

**为什么需要**：图 2「单条物流的组成」。

1. `stream` 必填，否则 `spec_invalid`。
2. 流股不存在 → `data_not_found`。
3. `mole_fraction` 不是 dict 或为空 → `data_not_found`。
4. 逐组分 `_vu`，`None` 跳过；`{"component": name, "fraction": v}`。
5. 空表 → `data_not_found`。
6. labels：`{"ylabel": "Mole fraction / -"}`。

**坑**：这里**不做别名匹配**（画的是"这条流股的全部组分"，不需要指名道姓），别好心加进去。

#### `split_component_track(process_data, component, value_field)`

**为什么需要**：图 3「某组分沿流股的分布」，用户最常要的图。

1. `component` 必填。
2. 校验 `value_field ∈ {mole_fraction, mole_flow, mass_flow}`。
3. 遍历**全部流股**（不是指定的），每条的 `stream[field]` 里找该组分。
4. `_lookup_component` 命中 → 记录 `matched_name`（只在第一次命中时记，后续保持同一个键名）。
5. 取不到值 → warning，跳过。
6. 空表 → `data_not_found`，错误信息提示"用 Aspen ID，如 CYCLO-01"。
7. labels：`{"ylabel": "CYCLO-01 mole_fraction / -", "matched_component": "CYCLO-01"}`。

**坑**：

- `matched_name` 决定图注，必须回传。
- 某条流股没有该组分（比如新生成的杂质）时跳过是**正确**的，不要补 0——补 0 会在图上画出"该组分突然归零"的假象。

#### `split_balance_check(process_data, block)`

**为什么需要**：图 4「设备进出衡算」，判断物料守不守恒。

1. `block` 必填。
2. 在 `connections` 里找该设备，找不到 → `data_not_found`。
3. `inputs` / `outputs` 必须都是非空 list。
4. 内部函数 `add_side(side, names)`：逐条流股取 `_stream_total_mole_flow`，缺失 → warning 跳过；`{"side": "in"|"out", "name": key, "value": total}`。
5. `add_side("in", inputs)`、`add_side("out", outputs)`。
6. 必须同时有 in 和 out 的行，否则 `data_not_found`（只有一边没法对比）。
7. labels：`{"ylabel": "Mole flow / kmol/h"}`。

**坑**：`nonlocal unit`——`add_side` 要修改外层的 `unit`，忘了 `nonlocal` 会 `UnboundLocalError`。

#### `split_for_plot(...)`

**为什么需要**：唯一的分发入口，把"图种校验"和"数据校验"集中在一处。

1. `pt = (plot_type or "").strip().lower()`，不在 `PLOT_TYPES` → `unknown_plot_type`。
2. `process_data` 不是 dict → `missing_process_data`。
3. `process_data["success"] is False` → `missing_process_data`，错误信息带上游 error。
4. 四个 `if` 分发（最后一个直接 return，不用 if）。

**坑**：`success` 判断用 `is False` 而不是 `not process_data.get("success")`。因为老数据可能没有 `success` 键，缺失应当**放行**，只有明确的 `False` 才拦。

---

### 5.4 `jobs.py`

三个函数，写得很干净，**基本不动**。理解它们是为了出问题时能定位。

| 函数 | 为什么需要 | 要点 |
|---|---|---|
| `create_job_dir(jobs_root, name=None)` | 每次画图一个独立目录，避免覆盖 | `name` 清洗后 + `uuid4().hex[:8]`；`mkdir(parents=True, exist_ok=True)` |
| `write_job(job_dir, plot_type, rows, *, title, export, ylabel…)` | 把 Python 的 rows 落成 MATLAB 能读的格式 | CSV 列名取 `rows[0].keys()`；`request.json` 用 `ensure_ascii=False` 保证中文可读 |
| `read_result(job_dir)` | MATLAB 的结果不可信（可能没写、可能写坏） | 三层兜底：文件不存在 / JSON 解析失败 / 不是 dict → 全部返回 `ok=False` 的标准结构；成功时 `setdefault` 补齐 5 个键 |

**坑**：

- `write_job` 里 `if not rows: raise ValueError("rows is empty")` —— 这个异常**不是** `DrawError`，会穿透 `draw_mat` 的 `except DrawError`。理论上 `split_for_plot` 保证 rows 非空，但改代码时要记得这条隐式约定。
- `read_result` 里 `data.setdefault("meta", {})` 不能省，否则调用方 `matlab_res.get("meta") or {}` 之外的地方会拿到 `None`。

### 5.5 `matlab_backend.py`

四个函数，核心是"**优先 Engine，失败回退 batch**"。

| 函数 | 为什么需要 | 要点 |
|---|---|---|
| `run_draw_dispatch(job_dir, matlab_draw_path, timeout=180)` | 唯一入口，按 `CHEMMATE_MATLAB_MODE` 分派 | `engine` / `batch` / `auto`；先校验 `draw_dispatch.m` 存在 |
| `_try_engine(job_dir, draw_path)` | 进程内调用，速度快 | 未装 Engine → 返回 `False`；装了但调用失败 → 抛 `MatlabFailed` |
| `_discover_matlab_bin()` | 找 `matlab.exe`：环境变量 > PATH > 常见安装位置 | 硬编码 `E:\AM1` 等候选（本机绿色安装），换机器时靠 `CHEMMATE_MATLAB_BIN` |
| `_run_batch(job_dir, draw_path, timeout)` | 子进程调用，不需要 Engine 包 | `matlab -batch "addpath('...'); draw_dispatch('...')"` |

**关键设计（不要改）**：

1. **`auto` 模式的错误合并**：Engine 失败 + batch 也失败时，抛出的 `MatlabFailed` 里同时带两边的错误信息。只报 batch 的错，会让人误以为"MATLAB 没装"。
2. **`OSError` 单独接**：`subprocess.run` 可能抛 `[Errno 22] Invalid argument` 这类 `OSError`（不是 `FileNotFoundError`），不接会穿透 `draw_mat` 直接崩整个任务。
3. **路径转 POSIX**：`_posix(path)` 把 `\` 换成 `/`，MATLAB 命令里反斜杠是转义符。
4. **超时**：默认 180 秒。MATLAB 冷启动就要 30~60 秒，别调太小。

**坑**：`_try_engine` 里 `eng.quit()` 放在 `finally`——MATLAB 进程不退出会一直占内存，多画几次图机器就卡死。

---

### 5.6 `test_draw_mat.py` 的三个 bug（✅ 已全部修复）

**修复前：这个文件根本跑不起来。**

| # | 位置 | 现象 | 原因 | 修法 |
|---|---|---|---|---|
| 1 | 第 22 行 `import draw_mat as dm` | `ImportError: attempted relative import with no known parent package` | `draw_mat.py` 内部是相对导入（`from .jobs import ...`），被当顶层模块导入时没有父包 | 删掉 `sys.path.insert`，改 `importlib.import_module(".draw_mat", __package__)`，跑法改为在 `CMV1/` 下 `python -m tools.draw_mat.test_draw_mat` |
| 2 | 第 112 行 `draw_mat(plot_type=..., dry_run=True)` | `NameError: name 'draw_mat' is not defined` | 只导了模块 `dm`，没有叫 `draw_mat` 的名字 | 改成 `dm.draw_mat(...)` |
| 3 | 第 108 行 `dm._LAST_PROCESS_DATA = None` | 静默无效 | `draw_mat.py` 里**没有**这个全局变量；缓存在 `memory.process_cache._cached` | `setUp` 里直接置 `process_cache._cached = None` |

**第 1 条为什么不能改成 `from tables import ...`**：那样只解决 `tables` 这一行，`draw_mat.py` 自身的 `from .jobs import ...` 仍然会炸。必须整体改成包内运行。

**第 3 条为什么必须修**：`unittest` 按方法名字母序跑，`test_cache_then_draw_without_json` 在 `test_missing_without_cache` 之前。前一个测试写入缓存后，后一个测试的"没有数据应该报错"会拿到脏缓存 → 假失败（实测就是这个现象：`success` 为 `True`）。

---

## 六、自检清单

- [x] `python -m tools.draw_mat.test_draw_mat` 全绿（9 个用例，在 `CMV1/` 下跑）
- [x] 新增 `"环己烷"` 的别名测试，`matched_component == "CYCLO-01"`
- [ ] `process_store.py` 已删，全局搜 `process_store` 无引用
- [ ] `tool_spec` / `TOOL_DESCRIPTION` / `TOOL_PARAMETERS` 已删，全局搜无引用
- [ ] `dry_run=True` 四种图各跑一次，`meta.n_rows` 与旧版一致
- [ ] 真实画图一次（`dry_run=False`），`image_path` 文件存在且非 0 字节
- [ ] `_default_draw_path()` 返回的目录里确有 `draw_dispatch.m`
- [ ] `job_dir` 落在 `CMV1/jobs/` 下（不是当前工作目录）
- [ ] `ylabel` 输出里中文正常（`ensure_ascii=False` 生效）
