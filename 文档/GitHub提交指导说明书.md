# GitHub 提交指导说明书（小白版）

> 对象：你本人（第一次上传项目到 GitHub）
> 目标：把 ChemMate V1 完整上传到 GitHub（云端备份 + 可展示 + 换电脑可克隆）
> 前置：git 已装（C:/Program Files/Git）、本地仓库已有 15 个提交

## 目录

- 1　上传前准备（10 分钟，重要！）
- 2　注册 GitHub 账号 + 建远程仓库
- 3　把本地仓库连上 GitHub 并推送
- 4　以后每次更新怎么推（三句口诀）
- 5　换电脑/换地方怎么拿回来
- 6　常见问题 FAQ

---

## 1　上传前准备（10 分钟，重要！）

### 1.1 检查敏感信息（必须做）

在项目根目录终端执行：

```bash
git ls-files | findstr /I "sk- tvly- .env"
```

- 应该**没有任何输出**（说明密钥没被跟踪）；
- 如果列出了 .env 或含密钥的文件：先 `git rm --cached .env` 再提交一次，**并去平台吊销旧密钥换新**；
- 检查 .gitignore 里已有：.env、*.dmp、__pycache__/、.idea/（已配好，放心）。

### 1.2 补一个根目录 README.md（GitHub 门面，建议做）

在项目根目录新建 README.md，内容参考（复制改改即可）：

```markdown
# ChemMate V1 · AI 化工流程助手

基于大型语言模型 Agent 的 Aspen Plus 化工流程智能助手：
输入自然语言任务 → Agent 自动调度工具 → 读取 Aspen 模拟数据 →
MATLAB 专业绘图 → 生成 Word/PPT 诊断报告。

## 功能
- 用户任务 → Agent 自主决策（无硬编码流程）
- Aspen Plus COM 数据读取：流股 / 设备 / 拓扑 / 模拟状态
- MATLAB 四种专业图：物流组成、温度压力、组分追踪、衡算校核
- 中文 Word/PPT 报告自动生成
- 三层记忆：进程缓存 / 会话记录(JSONL) /（V2：Obsidian 知识库）
- Web 展示页：真实驱动 Agent，实时查看推理与工具调用

## 项目结构

```text
CMV1/
├── agent_main.py      # 主程序（Agent 循环）
├── config.py          # 配置（.env 环境变量）
├── tools/             # 工具：取数 / 诊断 / 绘图 / 报告
├── agents/            # LLM 客户端 / Action 解析 / 提示词
├── memory/            # 进程缓存 / 会话记忆
└── ui/                # Web 展示页（真实引擎）
```

## 快速开始

```bash
pip install -r CMV1/requirements.txt
cp .env.example .env   # 填入你的 LLM_API_KEY
cd CMV1 && python agent_main.py   # 命令行对话
cd CMV1/ui && python Chem_Mate_V1.py   # Web 展示页(需 Aspen+MATLAB)
```

> 依赖：Windows + Python 3.13 + Aspen Plus（COM）+ MATLAB R2025b
> 密钥通过 .env 管理，不入库。
```

### 1.3 提交 README

```bash
git add README.md
git commit -m "docs: 根目录 README（GitHub 展示）"
```

---

## 2　注册 GitHub 账号 + 建远程仓库

1. 打开 https://github.com 注册账号（邮箱验证）；
2. 右上角 + → **New repository**；
3. Repository name 填：`ChemMateV1`；
4. **保持 Public**（展示用）或选 Private（仅自己看）；
5. 不要勾选 Add a README / .gitignore / license（本地已有仓库，要空的）；
6. 点 Create repository。

创建后页面会显示仓库地址，形如：

```text
https://github.com/你的用户名/ChemMateV1.git
```

---

## 3　把本地仓库连上 GitHub 并推送（只需做一次）

在项目根目录打开终端（PyCharm Terminal 或 Git Bash），依次执行：

```bash
git remote add origin https://github.com/你的用户名/ChemMateV1.git
git branch -M main
git push -u origin main
```

**第一次 push 会弹窗让你登录**，两种方式任选：

- 方式 A（推荐）：浏览器弹窗 → 点 Authorize → 自动完成（GitHub Desktop 登录过的话最顺）；
- 方式 B（手动）：会要求用户名 + 密码，注意密码处填的不是账号密码，而是 **Personal Access Token**：
  1. GitHub 右上角头像 → Settings → Developer settings → Personal access tokens → Tokens (classic)
  2. Generate new token → 勾选 `repo` 权限 → Generate → **复制 token（只显示一次！）**
  3. 密码框粘贴 token 即可。

push 成功后，刷新 GitHub 页面就能看到全部代码和提交历史了。

---

## 4　以后每次更新怎么推（三句口诀）

```bash
git add .                # 1. 收集改动
git commit -m "这次干了什么"   # 2. 本地存档
git push                 # 3. 推到 GitHub（-u 记住后就不用写 origin main 了）
```

> 想省事可以直接用 PyCharm：右上角绿色对勾 Commit → 然后 Push（Ctrl+Shift+K）。

---

## 5　换电脑/换地方怎么拿回来

```bash
git clone https://github.com/你的用户名/ChemMateV1.git
cd ChemMateV1
pip install -r CMV1/requirements.txt
# 自己另建 .env（从 .env.example 复制并填密钥）——.env 永远不会在仓库里
```

以后开工前 `git pull` 同步最新。

---

## 6　常见问题 FAQ

**Q1：push 报错 rejected（被拒绝）**
A：远程有你本地没有的提交（比如在网页上改过 README）。先 `git pull --rebase` 再 `git push`。

**Q2：提示 remote origin already exists**
A：说明之前连过，先 `git remote remove origin` 再重新 add。

**Q3：.env 会不会被传上去？**
A：不会。.gitignore 已排除；push 前可执行第 1.1 节命令自查。密钥只在你本地。

**Q4：仓库里有 300KB 的 .bkp 和几十 MB 的报告，GitHub 能放吗？**
A：GitHub 单文件上限 100MB（超 50MB 会警告）。本项目 .bkp 311KB、docx 250KB，完全没问题。若以后产物多了，把 CMV1/jobs、runs、reports 加进 .gitignore 只留代码。

**Q5：push 很慢 / 卡住？**
A：国内网络访问 GitHub 不稳定。重试几次，或用 Gitee（gitee.com，国内快）替代——流程一模一样，只把地址换成 gitee 的。

**Q6：提交后想改 commit 说明？**
A：没 push 前 `git commit --amend -m "新说明"`；已 push 则不要改（影响历史）。

**Q7：想在 GitHub 上补一张效果图？**
A：把 UI 展示页的截图或 MATLAB 样图放进仓库（如 docs/screenshot.png），然后在 README 里加一行：`![效果](docs/screenshot.png)`，GitHub 会自动展示图片。

---

## 附：上传前自查清单（对着打勾）

- [ ] git ls-files 搜不到密钥（第 1.1 节）
- [ ] 根目录 README.md 已建并提交
- [ ] GitHub 仓库已建（空的，未勾 README）
- [ ] remote add + push 成功，网页能看到代码
- [ ] 浏览器打开 https://github.com/你的用户名/ChemMateV1 检查展示效果
