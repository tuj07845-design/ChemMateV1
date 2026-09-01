# -*- coding: utf-8 -*-
"""
============================================================
 aspen_tree_finder.py —— 教学注释版（Python 小白友好）
============================================================
 功能：用 Python 启动 Aspen Plus，打开 .bkp 模型，把整个
       Tree（流程树，即左侧那个数据浏览器）递归打印出来。

 这份代码是在你原来“报 2002 错误”的版本上修改的。
 所有改动都做了标注：
   ❌  = 原来的错误写法
   ✅  = 修改后的正确写法
   【学习点】 = 配套的 Python / COM 小知识

 运行方式（在你自己的命令行里）：
   python aspen_tree_finder.py

 注意：运行时会真的启动 Aspen Plus 图形界面，请稍等片刻。
"""

# ============================================================
# 第一步：导入要用到的库
# ============================================================
import os
import win32com.client as win32

# 【学习点】这两行 import 是什么意思？
#   import os  → 引入 Python 自带的 os 模块，用来检查文件是否存在
#   import win32com.client as win32
#      → 引入 pywin32 这个第三方库。win32com.client 是“COM 自动化”客户端，
#        用它就能像 VBA 一样操控 Aspen Plus、Excel、Word 等 Windows 软件。
#     “as win32” 是起别名，以后写 win32.xxx 代替一长串 win32com.client.xxx

# ============================================================
# 第二步：模型文件路径（唯一需要你改的地方）
# ============================================================
aspen_file_path = r"C:\Users\Fool\Desktop\ChemMateV1\10万吨环己烷.bkp"
# ↑ 改成你自己的 .bkp 文件完整路径

# 【学习点】路径前面那个小写 r 是什么？
#   r"..." 叫“原始字符串”(raw string)：里面的反斜杠 \ 不被当成转义符，
#   原样保留。因为 Windows 路径用反斜杠，所以必须加 r，
#   否则 "\t" 会被误认成 Tab 制表符。
#   另外：\t 在普通字符串里是 Tab，在原始字符串里就是字面意义上的 	。

# ============================================================
# 第三步：写一个“递归打印”函数
# ============================================================
def print_tree(node, path="", level=0):
    """递归打印 Aspen Tree 中的节点路径。

    【学习点】什么是递归？
      递归 = 函数调用自己。Aspen 的树是一层套一层的：
      根节点 → 子节点 → 孙节点……每一层结构都一样，
      所以处理“自己”和处理“子节点”用同一段代码就行：
      print_tree 打印完自己之后，再对每一个子节点调用一次 print_tree。

    参数说明：
      node  : 当前要打印的节点（Aspen 的 INode 对象）
      path  : 一路走下来的路径字符串，比如 \\Data\\Setup
      level : 当前在第几层，用来控制缩进，输出更美观
    """

    # ---------- 第 1 步：读取节点名字 ----------
    # 每个节点都有一个 Name（比如 "Setup"、"Main"、"Unit Table"）
    try:
        name = node.Name
    except Exception:
        name = ""

    # 【学习点】为什么访问 Name 还要用 try/except？
    #   Aspen 里不是所有节点都有 Name / Value / Elements 这些属性，
    #   访问不存在的属性会“抛异常”(raise exception)。
    #   try 先试着执行；一旦出错立刻跳到 except，程序不会崩溃，
    #   而是用空字符串顶替。这就是 Python 的“异常处理”。

    # 拼出当前节点的完整路径：父路径 + "\" + 名字
    #   【学习点】三目运算符： 条件 if 真 else 假
    #   这里的意思是：如果有名字就拼 path+"\"+name，没名字就保持 path
    current_path = path + "\\" + name if name else path

    # 缩进：level 是几，前面就空几个“两个空格”，层次一目了然
    indent = "  " * level

    # ---------- 第 2 步：尝试读取节点的值 ----------
    # 有的节点有数值（比如某个参数 = 3），有的没有。
    # 先试着读 Value，读不到就只打印路径。
    try:
        value = node.Value
        print(f"{indent}[VALUE] {current_path} = {value}")
    except Exception:
        print(f"{indent}[NODE ]  {current_path}")

    # 【学习点】f 字符串是什么？
    #   f"..." 表示“格式化字符串”，里面的 {变量名} 会被替换成变量的值。
    #   比如 indent="  "、current_path="\\Data" 时，
    #   就会打印出：  [NODE ]  \Data

    # ---------- 第 3 步：继续找子节点（递归的核心） ----------
    # node.Elements 是当前节点的“子节点集合”
    try:
        children = node.Elements
        count = children.Count   # 子节点一共有几个

        # ❌ 原代码的写法（隐藏 bug）：
        #       for i in range(count):
        #           child = children.Item(i)   # 从 0 开始取
        #   问题：Aspen 的集合索引从 1 开始！Item(0) 一取就抛异常，
        #   而异常又被下面的 except 静默吞掉 → 所有子节点都打不出来，
        #   只打印一个根节点，还看不出报错。这就是“静默失败”。

        # ✅ 修复：先探测集合到底从 0 还是 1 开始编号
        #   试着取 Item(0)：能取到说明是 0 起始，取不到说明是 1 起始
        try:
            children.Item(0)
            start = 0
        except Exception:
            start = 1

        # 然后从正确的起点开始遍历
        # 【学习点】range(start, start+count) 生成 start 到 start+count-1
        #   的整数序列，配合集合下标正好取完所有子节点。
        for i in range(start, start + count):
            child = children.Item(i)
            # ★ 递归：自己调用自己，去打印这个子节点的子树
            print_tree(child, current_path, level + 1)

    except Exception:
        pass   # 【学习点】pass 就是“什么都不做”。叶子节点没有子节点，
               # 走到这里就安静地结束，不报错。

    # 【学习点】这个函数整体为什么安全？
    #   每一步都可能失败（节点没名字、没值、没子节点），
    #   但每一处都用 try/except 兜底了 → 整棵树无论多奇怪都能打完。


# ============================================================
# 第四步：主流程（入口）
# ============================================================
def main():
    """程序真正开始执行的地方。"""

    # ---------- 0. 先检查文件在不在 ----------
    # 【学习点】与其启动 Aspen 后才发现路径错了，不如一开始就检查。
    # os.path.exists(路径) 返回 True/False。不在就直接退出，省时间。
    if not os.path.exists(aspen_file_path):
        print("找不到模型文件：", aspen_file_path)
        print("请检查路径是否写对（注意盘符、大小写、中文）。")
        return

    aspen = None
    # 【学习点】aspen = None 是“先占个位”。
    # 后面 try 里如果中途出错，aspen 可能没创建成功；
    # finally 里要判断“aspen 到底创建了没”，有值才去关闭。
    # 如果这里不先给 None，而创建又失败了，finally 里访问 aspen
    # 会报“变量未定义”的新错误。

    try:
        # ====================================================
        # ★★★ 原来报错的地方就在这里 ★★★
        # ====================================================
        # ❌ 原代码：
        #     aspen = win32.Dispatch("Apwn.Document")
        #     aspen.Visible = True          ← 错误 2002 就出在这一行！
        #     aspen.InitFromArchive2(path)  ← 初始化放得太晚
        #
        # 你看到的报错：
        #   2002, 'Aspen Plus 41.0 OLE 服务',
        #   '未初始化应用程序或自上次初始化以来未关闭。
        #    必须先调用 InitNew 或 InitFromFile……'
        #
        # 翻译成人话：这个 Aspen 对象还没“准备好”，你就去动它了。
        #
        # 原因有两点：
        #  ① win32.Dispatch 会优先“挂”到电脑上已经打开的 Aspen 实例上。
        #    如果上次运行脚本崩溃/被强杀，残留的 aspenplus.exe 进程
        #    就是一个“没初始化”的空壳，挂上去之后怎么调都报 2002。
        #  ② 就算电脑上没有残留进程，Aspen Plus V15 的 COM 对象
        #    创建出来之后，也必须先调用“初始化”方法
        #    （InitNew / InitFromArchive2 等），才能访问其它
        #    属性或方法。原代码一上来就设 Visible，属于“没初始化就用”。
        # ====================================================

        print("正在启动 Aspen Plus...")

        # ✅ 修复 1：Dispatch → DispatchEx
        #   区别就在最后一个字母：
        #   Dispatch    = 尽量“捡”现成的（可能捡到残留的空壳实例）
        #   DispatchEx  = 强制新建一个全新的、干净的实例
        #   “Ex” 是英文 "create a new instance" 的缩写含义。
        aspen = win32.DispatchEx("Apwn.Document")

        # ✅ 修复 2：调整顺序 —— 先初始化，再干别的
        #   “Apwn.Document” 就是 Aspen Plus 的文档对象（ProgID），
        #   InitFromArchive2(路径) 把 .bkp 模型文件读进来，
        #   这一步同时完成了“初始化 + 加载模型”。
        #   之后再去设置 Visible（是否显示窗口）就不会报错了。
        print("正在加载模型：")
        print(aspen_file_path)
        aspen.InitFromArchive2(aspen_file_path)

        aspen.Visible = True   # ✅ 现在这行放在初始化之后，就安全了

        # ---------- 开始打印整棵树 ----------
        print("\n开始读取 Aspen Tree...")
        print("=" * 80)
        # aspen.Tree 就是整棵树的“根节点”，从它开始递归
        print_tree(aspen.Tree)
        print("=" * 80)
        print("Tree 读取结束。")

    except Exception as e:
        # 【学习点】try 块里任何一行出错，都会跳到这里的 except。
        # 变量 e 里装着错误信息，print 出来你就能看到。
        print("发生错误：", e)

        # 如果又是 2002（初始化错误），多半是电脑上还残留着
        # 上次没退干净的 Aspen 进程，给用户一个明确提示。
        if "2002" in str(e):
            print("提示：请先关闭所有 Aspen Plus 窗口，")
            print("      或在任务管理器中结束 aspenplus.exe 进程，")
            print("      然后重新运行本脚本。")

    finally:
        # 【学习点】finally 是什么？
        #   try 无论成功还是失败，finally 里的代码“一定”会执行。
        #   适合放“清理工作”：把启动的 Aspen Plus 关掉，
        #   免得留下残留进程（残留进程正是 2002 错误的元凶之一）。
        if aspen is not None:
            try:
                print("正在关闭 Aspen Plus...")
                aspen.Quit()
            except Exception:
                pass   # 关闭失败也不重要了，别让清理本身再报错

        # 【学习点】del 是“删除引用”。把 aspen 这个变量删掉，
        # 让 Python 和 COM 尽快释放资源。（可有可无，养成习惯）
        del aspen


# ============================================================
# 第五步：程序的真正入口
# ============================================================
if __name__ == "__main__":
    # 【学习点】if __name__ == "__main__" 是什么意思？
    #   每个 .py 文件被运行时，Python 会给它一个内置变量 __name__，
    #   值为 "__main__"；被别的文件 import 时，__name__ 则是文件名。
    #   这样写的作用：直接运行本文件 → 执行 main()；
    #   被别人 import 当工具用 → 不自动执行，避免副作用。
    #   这是所有 Python 脚本的标准写法，先记住“照抄即可”。
    main()


# ============================================================
# 学习小结（复习一遍，对照上面代码）
# ============================================================
# 1. COM 对象“先初始化、后使用”：
#      创建对象 → InitFromArchive2(文件) → 才能访问 Visible / Tree 等
#      顺序错了就报 2002“未初始化应用程序”。
#
# 2. Dispatch 会捡现成实例（可能捡到坏的），DispatchEx 总是新建。
#      自动化脚本里优先用 DispatchEx。
#
# 3. 残留的 aspenplus.exe 进程 = 未初始化的空壳实例 = 2002 的元凶。
#      出问题先到任务管理器结束它。
#
# 4. try/except = 出错不崩溃，兜底处理；finally = 无论如何都执行，
#      用来做清理（关 Aspen、关文件）。
#
# 5. Aspen 的集合索引从 1 开始（不是 Python 的 0），
#      取子节点前先探测一下更稳妥。
#
# 6. 路径用 r"..." 原始字符串；递归就是函数调用自己；
#     if __name__ == "__main__" 是标准入口写法。
# ============================================================
