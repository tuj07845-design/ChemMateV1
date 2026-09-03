# Git 使用说明手册（小白版）

> 对象：代码小白（你本人）
> 目的：理解 Git 是什么、怎么装、怎么写、怎么用，**日后随时回来查**。
> 你的工作台已经初始化好 git 仓库（第 3 节），本手册从零讲起，同样适用于你以后新建的任何项目。

## 目录

- 1　Git 是什么（用生活类比讲清楚）
- 2　安装 Git（Windows）
- 3　第一次使用前的配置（必做！）
- 4　三个核心概念：工作区 / 暂存区 / 仓库
- 5　日常四步流程（每天都是这四步）
- 6　命令详解表（查字典用）
- 7　撤销与回滚（改坏了怎么救）
- 8　分支（平行世界）
- 9　远程仓库（备份到云端：GitHub / Gitee）
- 10　常见问题 FAQ
- 11　10 分钟上手练习
- 12　速查卡（贴墙版）

---

## 1　Git 是什么

**一句话：Git 是文件的"游戏存档系统"。**

玩游戏时你会存盘——打 Boss 前存一个档，打输了读档重来，永远不怕玩坏。
Git 对文件夹做同样的事：

- 每完成一个阶段，`git commit` = **存一个档**；
- 改坏了，`git checkout` = **读档还原**；
- `git log` = **看有哪些存档**（每个存档带时间和说明）；
- 分支 = **开一条平行世界线**，试验新想法，不满意就删掉，不影响主世界。

你的工作台现在有两个"存档"：
`76895e8`（V1 基线快照）和 `b556ead`（新增操作说明书）。

**Git 和 GitHub 的区别**（新手常混淆）：

| | Git | GitHub / Gitee |
|---|---|---|
| 是什么 | 装在你电脑上的**软件**，管理本地版本 | **网站**，帮你存一份副本到云端 |
| 要不要联网 | 不要，纯本地 | 要，push/pull 时联网 |
| 干什么 | 存盘、回滚、看历史 | 备份、分享、多人协作 |

先学会 Git（本地），再学 GitHub（云端）。两者命令一样。

---

## 2　安装 Git（Windows）

你的电脑其实**已经装好了**（在 `C:/Program Files/Git`，版本 2.54），只是终端里直接敲 `git` 有时找不到。两种处理：

**方法 A（推荐，一劳永逸）**：在 PyCharm 里设置
`File → Settings → Version Control → Git`，把 `Path to Git executable` 填成：

~~~text
C:/Program Files/Git/cmd/git.exe
~~~

以后 PyCharm 的 Terminal 和图形界面都能直接用 `git` 命令了。

**方法 B（如果以后换电脑/重装）**：
1. 打开官网 `https://git-scm.com/download/win`，下载 Windows 版；
2. 双击安装包，**一路"Next"**（安装向导的默认选项就是对的）；
3. 装完打开"开始菜单 → Git Bash"或任意终端，输入 `git --version`，能显示版本号就成功了。

> 小知识：安装向导里有个 "Adjusting your PATH" 页面，默认选 `Git from the command line and also from 3rd-party software`，保持默认即可——这样 Git 命令对所有终端可见。

---

## 3　第一次使用前的配置（必做！）

Git 每次存档都要记"谁存的"，所以要先报上姓名和邮箱。打开终端（PyCharm Terminal 或 Git Bash），运行：

~~~bash
git config --global user.name "你的名字"          # 比如 "Fool"
git config --global user.email "你的邮箱@xx.com"   # 建议用 GitHub 注册邮箱
~~~

再配两条让中文体验更好的（重要！）：

~~~bash
git config --global core.quotepath false     # 中文文件名/中文提交说明正常显示（不会变成反斜杠数字乱码）
git config --global core.autocrlf true       # Windows 换行符自动转换（避免"明明没改却显示全文件变了"）
~~~

> `--global` 表示"对我这台电脑的所有项目生效"，只需设置一次。
> 你工作台的仓库里我已经设过局部用户名（ChemMate / chemmate@local），你自己设的全局配置会覆盖它。

验证配置：

~~~bash
git config --global --list
~~~

---

## 4　三个核心概念：工作区 / 暂存区 / 仓库

Git 把文件分成三个区域，理解了这个一切都不难：

~~~text
你在编辑器里改文件
        |
        v
【工作区】          <- 你眼睛看到、手在改的地方（文件夹本身）
        |  git add 把改动装进"暂存区"
        v
【暂存区】          <- 打包好的"待提交清单"（stage）
        |  git commit 把清单变成"存档"
        v
【仓库 .git】       <- 永久存档（历史记录全在这里）
~~~

- **工作区**：就是你的文件夹，随便改，不影响存档。
- **暂存区**：`git add` 把你想存档的改动挑出来放进去（可以只挑一部分文件）。
- **仓库**：`git commit` 把暂存区的内容正式存成一个快照。**从此它永远可恢复。**

新手最常见的坑：只 `git add` 忘了 `git commit`，或者只改了文件忘了 `git add`——所以记住口诀：**"改 → add → commit" 三步缺一不可**。

---

## 5　日常四步流程（每天都是这四步）

~~~bash
# 第 1 步：看现在改了什么
git status

# 第 2 步：把改动放进暂存区（"." 表示所有改动）
git add .

# 第 3 步：存一个档（-m 后面写"这次改了什么"，必须写清楚！）
git commit -m "拆分 analyzer_tool 完成"

# 第 4 步：看存档历史
git log --oneline
~~~

就这么简单。四步循环，一天循环很多次。

**提交说明怎么写**（以后回看历史全靠它）：
- 说"做了什么"，不说"怎么做的"：`修复取数报错` 好 / `改了一堆东西` 不好
- 一个提交只做一件事：拆文件就是拆文件，别顺手改密钥。

---

## 6　命令详解表（查字典用）

| 命令 | 作用 | 什么时候用 |
|---|---|---|
| `git status` | 看工作区/暂存区状态 | 每步操作前必看 |
| `git add .` | 暂存所有改动 | 准备提交时 |
| `git add 文件名` | 只暂存某个文件 | 只想提交部分文件时 |
| `git add -A` | 暂存所有（含删除） | 删了文件也要提交时用 |
| `git commit -m "说明"` | 存一个档 | 完成一个小阶段 |
| `git log --oneline` | 看存档列表（一行一条） | 想回忆干过什么 |
| `git log --oneline -5` | 只看最近 5 条 | 习惯性查看 |
| `git diff` | 看改动内容（未暂存的） | 提交前检查改对了没 |
| `git diff --cached` | 看已暂存的内容 | 提交前最后检查 |
| `git show 提交号` | 看某次存档的完整内容 | 想细看某次改动 |
| `git branch` | 看有哪些分支 | 用分支时 |
| `git branch 名字` | 新建分支 | 开平行世界 |
| `git checkout 分支名` | 切换分支 | 换世界线 |
| `git merge 分支名` | 合并分支 | 把实验成果合回主线 |
| `git remote -v` | 看远程仓库地址 | 接上云端后检查 |
| `git push` | 上传存档到云端 | 备份/分享 |
| `git pull` | 从云端拉最新 | 换电脑后同步 |
| `git clone 地址` | 把云端项目完整复制到本地 | 在新电脑上开工 |
| `git mv 旧路径 新路径` | 移动/改名文件（保留历史） | 整理目录时 |
| `git rm 文件` | 删除文件（并记录） | 删文件时 |

---

## 7　撤销与回滚（改坏了怎么救）

按"后悔程度"从小到大排列：

**一、只是改了文件，还没 add —— 想放弃这个文件的改动**

~~~bash
git checkout -- 文件名      # 恢复某个文件
git checkout -- .           # 恢复所有文件
~~~

> 注意：这会把改动**永久丢弃**（不是放进回收站）。确定不要了再用。

**二、已经 add 了，还没 commit —— 想取消暂存**

~~~bash
git restore --staged 文件名      # 取消暂存（文件内容不动）
~~~

**三、已经 commit 了 —— 想修改刚才那个存档的说明 / 漏了文件**

~~~bash
git commit --amend -m "新的说明"        # 改最近一次提交的说明
git add 漏掉的文件 && git commit --amend  # 把漏掉的文件补进最近一次提交
~~~

**四、已经 commit 了，想回到更早的存档**

~~~bash
git log --oneline          # 先找到想回去的存档号（比如 76895e8）
git reset --hard 76895e8   # 整个项目回到那个存档（后面所有改动消失！）
~~~

> `reset --hard` 是"时光倒流"，会丢掉之后的所有提交，**慎用**。

**五、手头改到一半，突然要先干别的 —— 先藏起来**

~~~bash
git stash          # 把所有未提交改动藏起来，工作区恢复干净
...先干别的事...
git stash pop       # 把藏起来的改动取回来
~~~

**救命口诀**：
- 没提交 → `checkout`
- 提交了 → `reset --hard 存档号`（先 `log` 找存档号）
- 不确定 → 先 `git status` 看清楚再动手

---

## 8　分支（平行世界）

**分支 = 平行世界线**。默认你一直在 `main`（主世界）上。想实验一个大胆的想法（比如"重构目录"），开一条新分支去折腾，成功了合并回主世界，失败了直接删除分支，主世界毫发无损。

~~~bash
git branch 实验名          # 创建分支（比如 git branch try-refactor）
git checkout 实验名        # 切换到该分支
...在分支上改代码、提交...
git checkout main          # 回主世界
git merge 实验名           # 把分支的成果合并回 main
git branch -d 实验名       # 合并完删除分支
~~~

新手可以先不用分支，**一直在 main 上 + 勤提交**就够安全了。等熟练了再用分支玩。

---

## 9　远程仓库（备份到云端：GitHub / Gitee）

本地 Git 只有你自己能看到，电脑坏了就全没了。**把仓库备份到云端**（GitHub 国外、Gitee 国内），顺便实现"换电脑接着干"。

### 9.1 注册 + 建一个空仓库（以 Gitee 为例，GitHub 步骤一样）

1. 打开 gitee.com 注册登录（GitHub 用 github.com）；
2. 点"新建仓库"（New repository）；
3. 仓库名随便起，比如 `ChemMateV1`；
4. **不要勾选**"初始化仓库/添加 README"（你本地已经有仓库了，要空的）；
5. 创建后页面上会显示一个地址，形如：
   `https://gitee.com/你的用户名/ChemMateV1.git`

### 9.2 把本地仓库连上云端（只需做一次）

在你工作台根目录的终端里：

~~~bash
git remote add origin https://gitee.com/你的用户名/ChemMateV1.git
git push -u origin main
~~~

- `remote` = 给云端地址起个名字（习惯叫 `origin`）；
- `push -u origin main` = 把本地 main 分支推上去，`-u` 记住对应关系（以后直接 `git push` 即可）。

> 第一次 push 会让你输入 Gitee/GitHub 的用户名和密码（GitHub 现在要用 Personal Access Token，在网站 Settings → Developer settings → Tokens 里生成）。

### 9.3 换电脑 / 换地方继续干

新电脑上只需要：

~~~bash
git clone https://gitee.com/你的用户名/ChemMateV1.git   # 完整复制到本地
cd ChemMateV1
git pull                     # 以后每次开工前拉最新（同步别人/别的电脑的改动）
~~~

### 9.4 日常同步节奏

~~~bash
git add . && git commit -m "干了啥"    # 本地存一个档（随时做）
git push                               # 做完一个阶段推到云端备份
~~~

**一句话习惯：本地勤提交，阶段勤推送。**

> 注意：.env 密钥文件已经被 .gitignore 排除，**永远不会被推上云端**——这正是它的意义。推代码前用 `git status` 扫一眼，确认没有意外文件。

---

## 10　常见问题 FAQ

**Q1：提示"git 不是内部或外部命令"**
A：按第 2 节方法 A 在 PyCharm 里配置路径；或者用完整路径 `C:/Program Files/Git/cmd/git.exe` 代替 `git`。

**Q2：git status 里中文文件名显示成一串反斜杠数字**
A：运行 `git config --global core.quotepath false`，以后就正常了。

**Q3：不小心把 .env（密钥）提交了怎么办？**
A：立即处理：
~~~bash
git rm --cached .env      # 从仓库移除（本地文件保留）
echo ".env" >> .gitignore # 确保以后不再被提交
git commit -m "移除误提交的 .env"
git push
~~~
但注意：密钥已经进了 git 历史，历史里删不干净（需要 filter-repo 等高级工具）。**最稳妥的做法：去平台吊销旧密钥换新的**，只让新密钥进 .env。

**Q4：commit 说明写错了 / 忘了提交某个文件**
A：`git commit --amend -m "新说明"`，或 `git add 遗漏文件 && git commit --amend`。前提是还没 push；push 过就用 `git commit --amend` + `git push --force`（慎用 force）。

**Q5：改了文件，发现 git status 里显示"整个文件都变了"**
A：多半是换行符问题，运行 `git config --global core.autocrlf true` 后重新 add。

**Q6：commit 后后悔，想回到上个存档**
A：`git log --oneline` 找到上一个存档号 → `git reset --hard 存档号`。

**Q7：git push 被拒绝（rejected）**
A：云端有本地没有的新提交，先 `git pull` 拉下来合并，再 push。

**Q8：操作界面（图形化）有吗？**
A：PyCharm 自带图形界面：右侧边栏 `Git` 标签，能看历史/提交/回滚，不用记命令也能用；也可以装 GitKraken、SourceTree 等可视化工具。命令是根本，图形是辅助，两边都会最稳。

---

## 11　10 分钟上手练习（建议现在就做）

在任意地方建一个练习文件夹，把下面的命令敲一遍，比看十遍手册都管用：

~~~bash
# 1. 建练习文件夹并进入
mkdir C:/Users/Fool/Desktop/git练习
cd C:/Users/Fool/Desktop/git练习

# 2. 初始化仓库
git init

# 3. 写个文件
echo 你好Git > hello.txt

# 4. 存第一个档
git add hello.txt
git commit -m "第一个存档"

# 5. 改文件，看区别
echo 第二行内容 >> hello.txt
git status          # 看到 hello.txt 被修改
git diff            # 看到具体改了哪行

# 6. 再存一个档
git add .
git commit -m "加了第二行"

# 7. 看历史
git log --oneline   # 两个存档

# 8. 试一次回滚
git checkout -- hello.txt   # 改乱后恢复
# 或 git reset --hard 存档号 回到更早

# 9. 试一次分支
git branch 实验
git checkout 实验
...随便改点东西提交...
git checkout main
git merge 实验
git branch -d 实验

# 练习完可以删掉这个文件夹：rmdir /s 路径（在 Windows 资源管理器删更省事）
~~~

---

## 12　速查卡（贴墙版）

~~~text
查看状态：    git status
暂存改动：    git add .              （单个文件：git add 文件名）
存个档：      git commit -m "说明"
看历史：      git log --oneline
看差异：      git diff
放弃改动：    git checkout -- 文件名   （全部：git checkout -- .）
临时藏起：    git stash / git stash pop
改说明：      git commit --amend -m "新说明"
回旧存档：    git reset --hard 存档号
分支：        git branch 名 / git checkout 名 / git merge 名 / git branch -d 名
远程：        git remote add origin 地址 / git push -u origin main
同步：        git push（上传） / git pull（下载）
复制项目：    git clone 地址
移动文件：    git mv 旧 新
删文件：      git rm 文件

口诀：先 status，再 add，后 commit；改坏了 checkout；勤存档，阶段推送。
~~~

> 手册完。配合你工作台里的《ChemMateV1重构操作说明书》第 2、9 节一起用效果更佳。

