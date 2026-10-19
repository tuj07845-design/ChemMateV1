# 04 · report_create 模块

> 覆盖 `CMV1/tools/report_create/` 全部 5 个文件
> 对外只暴露一个名字：`report_create`（`report_core.py` 里的同名函数）

---

## 一、定位

**它做的事**：把模型组织好的 `sections`（内容块列表）渲染成 Word 或 PPT。

**它不碰**：不分析数据、不画图、不决定写什么内容。**内容全是模型给的**，这里只负责"排版 + 落盘"。

**调用链**：

```
tools_register.report_create(report_type, title, sections)
        ▼
report_core.report_create(...)                    ← 主函数，7 步
        ├── _validate_sections()                  校验五种块类型
        ├── _check_lib()                          检查 python-docx / python-pptx
        ├── _resolve_output_path()                统一收拢到 reports/
        ├── _render_docx()   或  _render_pptx()   渲染
        └── _fail()                               统一失败返回
```

**文件职责表**：

| 文件 | 行数 | 职责 | 改造强度 |
|---|---:|---|---|
| `report_core.py` | 173 | 主流程 + 校验 + 路径 | 小修 |
| `sections.py` | 211 | 便捷构造器 + **一堆死代码** | **大删** |
| `render_docx.py` | 266 | Word 渲染（排版细节） | 只清导入 |
| `render_pptx.py` | 235 | PPT 渲染（排版细节） | 只清导入 |
| `__init__.py` | 2 | 包导出 | 跟着 `sections` 走 |

---

## 二、改造清单

| # | 文件 | 问题 | 动作 | 风险 |
|---|---|---|---|---|
| 1 | `sections.py` | `TOOL_NAME` / `TOOL_DESCRIPTION` / `TOOL_PARAMETERS` / `tool_spec()` 全部无调用者 | 删（约 60 行） | 无 |
| 2 | `sections.py` | `SECTION_TYPES` 与 `report_core.py` 重复定义 | 删，只留 `report_core` 那份 | 低 |
| 3 | `sections.py` | `import os` / `datetime` / `Path` / `Any` 四个全是死导入 | 删 | 无 |
| 4 | `sections.py` | `build_sections_from_results` 无实际调用（只被 `__init__.py` 转手导出） | **二选一**：删 / 保留并补测试 | 中 |
| 5 | `render_docx.py` | `from typing import Any` 未使用 | 删 | 无 |
| 6 | `render_pptx.py` | 同上 | 删 | 无 |
| 7 | `report_core.py` | 排版/校验逻辑本身 | **不动** | — |

---

## 三、为什么这么改

### 3.1 为什么 `sections.py` 要大删

这个文件现在装着三样东西，只有一样可能还有用：

| 内容 | 行范围 | 现状 |
|---|---|---|
| `TOOL_NAME` / `TOOL_DESCRIPTION` / `TOOL_PARAMETERS` | 11–64 | 旧的 JSON Schema 工具描述，LangChain 已改用 docstring → **死** |
| `SECTION_TYPES` | 67 | 与 `report_core.py` 第 11 行重复 |
| `build_sections_from_results` + `_fmt` + `_fmt_unit` | 77–198 | 无实际调用者 |
| `tool_spec()` | 205–211 | 无调用者 |

**证据**：全仓库搜索 `tool_spec` → 只有定义；搜索 `build_sections_from_results` → 只有 `__init__.py` 的一行 re-export，没有任何地方 import 后调用。

### 3.2 `build_sections_from_results` 怎么处理（需要你决策）

它是个**能跑通的参考实现**：把 `data_get` + `analyze` + 图片路径拼成一份完整的 sections。功能上没毛病，问题是没人用——现在的 agent 是让模型自己组织 `sections`（`tools_register` 的 docstring 明确说"报告结论文字由你自己组织，不要照抄工具返回"）。

两个选择：

| 选项 | 理由 | 代价 |
|---|---|---|
| **A. 删**（推荐） | 减少维护面。模型自己组织内容更灵活，这个函数只是限制了它 | 以后想"一键出报告"要重写 |
| B. 保留 | 未来可能做"固定模板报告" | 必须补一个测试，否则它会悄悄腐烂 |

**判断依据**：如果你接下来要做"不经过模型、直接出报告"的功能，选 B；否则选 A。

无论选哪个，`__init__.py` 的导出要同步改。

**如果选 A，`sections.py` 会只剩空壳**：三件套（54 行）+ `build_sections_from_results`（122 行）+ `tool_spec`（7 行）+ 死导入（4 行）删完，就只剩 `SECTION_TYPES` 一行转发。这时候更干净的做法是**整个文件删掉**，`__init__.py` 只导出 `report_create`。

| 方案 | `sections.py` 最终 | `__init__.py` |
|---|---|---|
| **A1 全删（推荐）** | 删文件 | 只 `from .report_core import report_create` |
| A2 保留空壳 | ~10 行转发 | 保持现状 |
| B 保留功能 | 211 行，但必须补测试 | 保持现状 |

> 一个 10 行的转发文件比“没有文件”更糟：后来者会以为这里面还有逻辑，找不到又不敢删。

### 3.3 为什么 `SECTION_TYPES` 不能留两份

```
report_core.py:11   SECTION_TYPES = ("heading", "paragraph", "bullets", "table", "image")
sections.py:67      SECTION_TYPES = ("heading", "paragraph", "bullets", "table", "image")
```

现在两份内容一样，看不出问题。但哪天要加一种 `"code"` 块：

- 只改 `report_core` → `sections` 那份就成了过期数据，谁 import 谁踩坑；
- 两份都改 → 迟早有一次忘掉一份。

**规则**：常量只留定义它的地方（`report_core` 是校验方，它说了算），其它模块 import 使用。

### 3.4 为什么渲染文件基本不动

`render_docx.py` / `render_pptx.py` 里有大量**踩坑换来的细节**，每一处都对应一个真实的排版 bug：

| 代码 | 如果不写会怎样 |
|---|---|
| `_docx_force_theme_font`（改 `theme1.xml` 字节） | 正文宋体、**表头雅黑**——表格样式走的是主题字体 |
| heading 的 run 级 `_docx_run_font` | 标题被渲染成微软雅黑——样式继承在 Word 里不可靠 |
| `firstLineChars` + `firstLine` 双设 | 有的 Word 版本只认其中一个，缩进时有时无 |
| `w:cantSplit` | 表格一行被拆到两页 |
| `w:tblHeader` | 表头跨页后消失 |
| PPT `ensure_space` | 内容超出 7.5 英寸画面，**被裁掉且没有任何提示** |
| 图片缺失插红色提示 | 图和图注错位，或整个 section 静默消失，排查时不知道少了什么 |

这些函数**不要重写**，最多清一下文件头的死导入。

---

## 四、操作步骤

1. **先跑一次基线**：用固定 sections 生成一份 docx 和一份 pptx，打开确认排版正常。
2. **删 `sections.py` 的死代码**（工具描述三件套 + `tool_spec` + 重复常量 + 死导入）。
3. **决定 `build_sections_from_results` 的去留**（见 3.2）。
4. **同步 `__init__.py`**。
5. **清两个渲染文件的 `Any` 导入**。
6. **再生成一份 docx / pptx，与基线肉眼对比**（页数、字体、表格、页码）。

---

## 五、逐块原子拆解

### 5.1 `report_core.py`

#### `report_create(report_type, title, sections, output_path=None, author="ChemMate V1") -> dict`

**为什么需要**：唯一入口。它要保证"不管输入多烂，都返回结构一致的 dict，不抛异常"。

**返回契约**：

```
成功: {"success": True, "error": "", "message": "...", "file_path": "...",
       "report_type": "docx"|"pptx", "section_count": N}
失败: {"success": False, "error": "spec_invalid"|"missing_dependency"|"render_failed",
       "message": "...", "file_path": "", "report_type": "", "section_count": 0}
```

**7 步**：

1. **规范化类型**：`rt = (report_type or "").strip().lower()`；不在 `("docx", "pptx")` → `_fail("spec_invalid", ...)`。
2. **校验标题**：空或全空白 → `_fail("spec_invalid", "title 不能为空")`。
3. **校验 sections**：`try: sections = _validate_sections(sections) except ReportError: return _fail(...)`。
4. **检查依赖库**：`_check_lib(rt)`。缺库返回 `missing_dependency`，消息里带 `pip install` 命令。
5. **定输出路径**：`out = _resolve_output_path(rt, str(title), output_path)`；然后**强制扩展名**：
   `if out.suffix.lower() != f".{rt}": out = out.with_suffix(f".{rt}")`
6. **渲染**：
   ```
   try:
       if rt == "docx": _render_docx(str(title), sections, out, author)
       else:            _render_pptx(str(title), sections, out, author)
   except ReportError as exc:   return _fail(exc.code, exc.message)
   except Exception as exc:     return _fail("render_failed", f"{type(exc).__name__}: {exc}")
   ```
   两层 except 的顺序不能反：`ReportError` 是"已知错误"（带稳定 code），其它异常统一归 `render_failed` 并**带上异常类型名**（排查时要看是 `PermissionError` 还是 `ValueError`）。
7. **成功返回**：6 个键。

**坑**：

- 第 5 步的 `with_suffix` 会**替换**已有后缀。`"报告.v1"` → `"报告.docx"`，`.v1` 丢了。原实现如此，保持。
- 第 6 步的 `except Exception` 不能省。`python-docx` 遇到损坏图片、非法 XML 字符会抛各种奇怪的异常，不接就会穿透到 `tools_register`，模型收到一个 Python traceback。

#### `_validate_sections(sections) -> list`

**为什么需要**：模型生成的 JSON 不可信——可能给 `None`、给字符串、给一个不存在的 `type`。渲染器假设结构正确，所以必须在入口拦住。

**原子步骤**：

1. 不是 list → `raise ReportError("spec_invalid", "sections 必须是列表")`
2. 逐块：不是 dict → 报"第 N 块不是 dict"
3. `stype = sec.get("type")`；不在 `SECTION_TYPES` → 报"第 N 块 type=... 非法，可选 (...)"
4. 通过的原样 append（**不做深拷贝、不补默认值**）

**坑**：错误信息里必须带**块序号**（`i + 1`，从 1 数起）。模型看到"第 3 块"能立刻定位，看到"某一块"只能瞎猜。

#### `_check_lib(report_type)`

**为什么需要**：`python-docx` / `python-pptx` 不是标准库，用户环境可能没装。在渲染前查，能给出可操作的提示；等到 `import docx` 在渲染函数里炸，错误是 `ModuleNotFoundError`，模型和用户都不知道该装什么。

**写法**：`try: import docx except ImportError: raise ReportError("missing_dependency", "……请执行：pip install python-docx")`。

**坑**：`import docx  # noqa: F401` —— 只为检测存在性，不用它，所以要标 noqa 免得 linter 报"未使用"。

#### `_reports_root() -> Path`

**为什么需要**：报告必须落在 `CMV1/reports/`。

**实现**：环境变量 `CHEMMATE_REPORTS_DIR` 优先，否则 `Path(__file__).resolve().parents[2] / "reports"`（本文件在 `CMV1/tools/report_create/` 下，`parents[2]` = `CMV1_langchain_framework`）。

**坑（历史事故）**：**不能用 `Path.cwd()`**。UI 曾从 `CMV1/ui` 启动，cwd 是 `ui/`，报告会落到 `CMV1/ui/reports`，而前端只放行 `CMV1/jobs`、`CMV1/reports`、`CMV1/ui/runs` —— 结果是**报告生成了，但前端看不到、打不开（403）**。（`ui/` 目录现已移除，但这条约束保留。）

#### `_resolve_output_path(report_type, title, output_path) -> Path`

**为什么需要**：保证所有报告都收在统一目录里，UI 的产物登记依赖这个约定。

**原子步骤**：

1. `root = _reports_root()`；`root.mkdir(parents=True, exist_ok=True)`
2. **传了 output_path**：
   - `candidate = Path(output_path)`
   - `try: if candidate.resolve().is_relative_to(root.resolve()): return candidate`
   - 越界或 `OSError` → `return root / candidate.name`（**只取文件名**，落回 reports）
3. **没传**：
   - `safe = "".join(c for c in title if c not in r'\/:*?"<>|')[:20].strip() or "report"`
   - `stamp = datetime.now().strftime("%Y%m%d_%H%M%S")`
   - `return root / f"{safe}_{stamp}.{report_type}"`

**坑**：

- 第 2 步的 `is_relative_to` 要求 Python 3.9+（项目 3.13，没问题）。
- `[:20]` 是**过滤后**截断，不是先截断再过滤——否则一个全是非法字符的长标题会变成空串。
- 越界路径"只取文件名"是有意的**静默收敛**，不报错。因为模型可能瞎传 `C:\Users\...\Desktop\报告.docx`，直接拒绝会让任务失败，收敛到 reports 更稳。

#### `_fail(code, message) -> dict`

统一失败返回体，6 个键与成功返回对齐（`file_path=""` / `report_type=""` / `section_count=0`）。

**为什么失败也要带这些键**：模型按统一结构读，少一个键就要写 `if "file_path" in result` 这类防御代码。

---

### 5.2 `sections.py`（删完剩什么）

按第二节删完后，这个文件要么不存在（选 A），要么只剩 `build_sections_from_results` + `_fmt` + `_fmt_unit`（选 B）。

如果选 B 保留，三个函数的原子拆解：

#### `build_sections_from_results(process_data, analyze_result, image_paths, intro) -> list[dict]`

**为什么需要**：把三个工具的返回值拼成一份现成的报告目录。

**四段结构**：

1. `intro` → 一个 paragraph
2. `process_data` 有 `success` → 一级标题"一、流程概况" + 一句话统计 + 设备表（`block` / `inputs` / `outputs` 三列）
3. `analyze_result` 有 `success` → 一级标题"二、数据分析"：
   - `summary` → bullets
   - `findings` → 二级标题 + bullets（每条格式 `[level] type（stream）：message`）
   - `component_tracking` → 二级标题 + 四列表（流股 / 摩尔分率 / 摩尔流 / 质量流）
   - `stream_changes` → 二级标题 + 四列表（设备 / 从 / 到 / 组分变化）
4. `image_paths` → 一级标题"三、图表" + 每张图一个 image 块

**坑**：

- 每个 `isinstance` 判断都不能省——三个工具的失败返回结构不一样。
- `stream_changes` 的"组分变化"列把多个组分拼成一行：`"CYCLO-01:0.47→0.02; CH4:0.47→0.88"`。

#### `_fmt(v) -> str`

`None` → `""`；能转 float → `f"{float(v):.6g}"`（6 位有效数字，够看又不长）；转不了 → `str(v)`。

#### `_fmt_unit(v, u) -> str`

先 `_fmt(v)`，有值且有单位 → `"值 单位"`，否则只返回值。

---

### 5.3 `render_docx.py`

#### `_render_docx(title, sections, output_path, author) -> Path`

**为什么需要**：Word 渲染器。**结构比细节重要**，下面是它做的事的顺序：

1. **页面**：A4（21 × 29.7 cm），上下 2.54、左右 3.18 cm。
2. **样式**：
   - `Normal`：宋体、12pt（小四）、1.5 倍行距、段后 0
   - `Title` / `Heading 1~3`：宋体、22/16/14/12pt、加粗、黑色、1.5 倍行距、`keep_with_next`
   - `List Bullet`：宋体、12pt、1.5 倍行距
3. **核心属性**：`author` / `title`（整段 try，失败不影响渲染）。
4. **主题字体**：`_docx_force_theme_font(doc, "宋体")`。
5. **封面**：`add_heading(title, level=0)` 居中 + 每个 run 显式设字体；下面一行灰色小字"生成时间 + 作者"。
6. **页脚**：`_docx_add_page_number(sec0.footer.paragraphs[0])`。
7. **遍历 sections**，五种类型各自处理（见下表）。
8. **保存**：`output_path.parent.mkdir(...)` + `doc.save(...)`。

**五种 section 的处理要点**：

| type | 关键处理 | 坑 |
|---|---|---|
| `heading` | `level` 夹到 1~3（`max(1, min(3, level))`）；run 级再设一次字体 | 不设 run 级字体 → 微软雅黑 |
| `paragraph` | 两端对齐 + 首行缩进 2 字符 | 必须用 `firstLineChars` + `firstLine` 双设 |
| `bullets` | 逐条 `add_paragraph(..., style="List Bullet")` | `items` 不是 list 就整个跳过 |
| `table` | 列数 = `len(headers)`，缺 headers 用第一行列数；表头加粗居中；`cantSplit` + `tblHeader` | 行长度不足时补 `""`，否则 `IndexError` |
| `image` | 文件不存在 → 插红色提示；存在 → `add_picture(width=5.5in)`，太大则退化为原尺寸；图注小字灰色居中 | 图片缺失**不能静默跳过**，否则图和图注错位 |

#### `_docx_force_theme_font(doc, font)`

**为什么需要**：Word 内置的标题样式、表格样式（如 `Light Grid Accent 1` 的 firstRow）用的是**主题字体**（`theme1.xml` 里的 `majorEastAsia` / `majorHAnsi`），不是 `styles.xml` 里写死的字体名。

只改 `styles.xml` 的结果是：**正文宋体、表头雅黑**。

**实现要点**：

- `theme1.xml` 在 python-docx 里是普通 `Part`，只有 `_blob`（bytes），**没有解析成 XML 元素**。所以必须直接改字节再写回 `_blob`，只设元素属性会被丢弃。
- 三处正则：`<a:ea typeface="...">`（东亚）、`<a:latin typeface="...">`（西文）、`<a:font script="Hans" typeface="...">`（简体中文实际用字）。
- 整段 try，失败就跳过——run 级字体已经显式设过，主题改写失败不影响主流程。

**坑**：正则里的 `\s+` 不能省，主题 XML 的属性之间可能是多个空格或换行。

---

### 5.4 `render_pptx.py`

#### `_render_pptx(title, sections, output_path, author) -> Path`

**结构**（与 Word 完全不同，PPT 是"一页一页"的）：

1. **16:9**：`13.333 × 7.5` 英寸；用 `slide_layouts[6]`（空白版式）。
2. **封面页**：主标题 40pt 加粗居中 + 时间/作者 14pt 灰色。
3. **内容页规则**：**每个 `heading` 开新页**；连续的 paragraph / bullets / table / image 累积在同一页。
4. **溢出守卫 `ensure_space(needed)`**：当前 y + 需要高度 > 页面底部（7.1 in）→ 开续页（标题加"（续）"）→ 重置 y。
5. **五种类型**：
   - `paragraph`：18pt，行距 1.2，高度按 0.6 in 递增
   - `bullets`：每个 `"• " + 文本`，高度按 `0.2 + 0.4 × 条目数` 估
   - `table`：表头 16pt 加粗、表体 14pt；高度按 `0.4 + 0.35 × 行数` 估
   - `image`：按 96 DPI 换算尺寸，限制最大高 4.6 in、宽 12.1 in，等比缩放；图注 12pt 灰色居中
   - 图片缺失 → 红色提示文本
6. **保存**。

**坑**：

- `new_slide` 里的 `cur_heading = heading_text[:-3] if endswith("（续）")` —— 防"续页的续页"变成"标题（续）（续）"。
- `nonlocal current, cur_heading` / `nonlocal cur_y` 不能漏，否则 `UnboundLocalError`。
- 高度全是**估算值**，不可能精确（字体、换行都影响）。估高了浪费空间，估低了溢出被裁。宁可高估。
- `from PIL import Image` 放在 try 里，PIL 没装就用 `(900, 420)` 兜底尺寸。

#### `_pptx_run_font(run, size, bold, color, font)`

**为什么需要**：PPT 的中文字体要单独设 `a:ea` 节点，只设 `run.font.name`（`a:latin`）中文会走主题默认字体。

**实现要点**：先设 latin → 找 `a:ea` 节点，没有就创建并插在 `a:latin` 后面 → 设 `typeface`。

**坑**：`rpr.makeelement(qn("a:ea"), {})` 创建新节点后必须**手动插到正确位置**（latin 之后），直接 append 可能违反 OOXML 的元素顺序，PowerPoint 打开会提示修复。

---

## 六、自检清单

- [ ] 删完 `sections.py` 后，全局搜 `TOOL_DESCRIPTION` / `TOOL_PARAMETERS` / `tool_spec` 只剩 `draw_mat` 那边（也要删）
- [ ] `SECTION_TYPES` 只剩 `report_core.py` 一份
- [ ] `__init__.py` 与 `sections.py` 的实际内容一致（别导出一个已删除的名字）
- [ ] 生成一份 docx：打开看——全文宋体（尤其**表头**）、正文首行缩进、1.5 倍行距、页码在页脚居中、表格不跨页断行
- [ ] 生成一份 pptx：16:9、每章新页、内容多时自动续页且标题带"（续）"、图片不变形
- [ ] 传一个不存在的图片路径 → docx/pptx 里有红色"图片缺失"提示，**不是**静默跳过
- [ ] 传一个非法 section（`type="code"`）→ 返回 `spec_invalid`，消息里带块序号
- [ ] 传一个 `C:\Windows\xxx.docx` 的 output_path → 实际落到 `CMV1/reports/xxx.docx`
- [ ] 卸载 `python-docx` 后调用 → 返回 `missing_dependency` + pip 命令（不抛异常）
