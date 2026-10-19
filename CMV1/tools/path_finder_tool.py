import os
from langchain.tools import tool

def _compact_filename(value: str) -> str:
    """处理用户在中文文件名中随手加入的空格。"""
    return "".join(str(value).split()).casefold()






@tool("path_finder", parse_docstring=True)
def path_finder(filename: str) -> dict:
    """在用户主目录中搜索指定文件名的 Aspen 文件,返回完整路径。

    Args:
        filename: 要查找的文件名,不区分大小写。
    """
    ...


    # ========================================================
    # 1. 获取当前用户目录
    # ========================================================

    user_home = os.path.expanduser("~")


    # ========================================================
    # 2. 开始搜索
    # ========================================================

    requested = str(filename).casefold()
    compact_requested = _compact_filename(filename)
    compact_match = None

    for root, dirs, files in os.walk(user_home):

        for file in files:

            # 文件名不区分大小写

            if file.casefold() == requested:

                # 拼接完整路径

                file_path = os.path.abspath(
                    os.path.join(root, file)
                )


                # =================================================
                # 找到文件
                # =================================================

                return {

                    "success": True,

                    "filename": filename,

                    "file_path": file_path

                }

            # 精确匹配失败时，允许中文文件名中的空白差异。
            if compact_match is None and _compact_filename(file) == compact_requested:
                compact_match = os.path.abspath(os.path.join(root, file))

    if compact_match:
        return {
            "success": True,
            "filename": filename,
            "file_path": compact_match,
        }


    # ========================================================
    # 3. 没找到
    # ========================================================

    return {

        "success": False,

        "filename": filename,

        "file_path": None,

        "error": "没有找到指定的 Aspen 文件"

    }
