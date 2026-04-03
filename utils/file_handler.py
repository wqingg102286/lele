import os
import hashlib
from .logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader,TextLoader,Docx2txtLoader

# 获取文件的MD5的十六进制字符串
def get_file_md5_hex(filepath: str):

    if not os.path.exists(filepath):
        logger.error(f"[md5计算]文件{filepath}不存在")
        return None

    if not os.path.isfile(filepath):
        logger.error(f"[md5计算]文件{filepath}不是文件")
        return None

    md5_obj = hashlib.md5()

    chunk_size = 4096       # 每次读取4KB
    try:
        with open(filepath, "rb") as f:     # 必须二进制读取
            while chunk := f.read(chunk_size):          # 使用:=赋值，避免Python3.8及以下版本报错
                md5_obj.update(chunk)
                """
                chunk = f.read(chunk_size):
                while chunk:
                    md5_obj.update(chunk)
                    chunk = f.read(chunk_size):
                """
                md5_hex = md5_obj.hexdigest()
            return md5_hex
    except Exception as e:
        logger.error(f"[md5计算]文件{filepath}计算失败")
        return None

# 返回文件夹内的文件列表 (允许的文件后缀)
def listdir_with_allowed_type(base_path: str, allowed_types: tuple) -> list[str]:
    """
    递归扫描目录下所有符合指定类型的文件（支持穿透无数层子文件夹）
    :param base_path: 要扫描的根目录
    :param allowed_types: 允许的文件后缀元组，如 ('.txt', '.pdf', '.docx')
    :return: 所有符合条件的文件的绝对路径列表
    """
    result = []
    # os.walk 是 Python 里的“子文件夹杀手”，它会自动往下钻所有的目录
    for root, dirs, files in os.walk(base_path):
        for file in files:
            # 统一转成小写比较，防止出现 .TXT 和 .txt 的大小写问题
            if file.lower().endswith(allowed_types):
                # 拼装出文件的完整绝对路径
                full_path = os.path.join(root, file)
                result.append(full_path)

    return result

def pdf_loader(file_path: str, passwd=None) -> list[Document]:
    return PyPDFLoader(file_path, passwd).load()

def txt_loader(file_path: str, encoding="utf-8") -> list[Document]:
    return TextLoader(file_path, encoding=encoding).load()

def word_worder(file_path: str) -> list[Document]:
    return Docx2txtLoader(file_path).load()