"""
为整个工程提供统一的绝对路径
"""
import os


def get_project_root():
    """
    获取项目根目录
    :return:
    """
    current_file = os.path.abspath(__file__)        # 当前文件的绝对路径
    current_dir = os.path.dirname(os.path.dirname(current_file))  # 当前文件的上一级目录
    return current_dir

def get_abs_path(relative_path: str) -> str:
    """
    传递相对路径，得到绝对路径
    :param relative_path: 相对路径
    :return: 绝对路径
    """
    project_root = get_project_root()
    return os.path.join(project_root, relative_path)

