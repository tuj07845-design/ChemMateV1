import os




def path_finder(filename: str):


    # ========================================================
    # 1. 获取当前用户目录
    # ========================================================

    user_home = os.path.expanduser("~")


    # ========================================================
    # 2. 开始搜索
    # ========================================================

    for root, dirs, files in os.walk(user_home):

        for file in files:

            # 文件名不区分大小写

            if file.lower() == filename.lower():

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


    # ========================================================
    # 3. 没找到
    # ========================================================

    return {

        "success": False,

        "filename": filename,

        "file_path": None,

        "error": "没有找到指定的 Aspen 文件"

    }