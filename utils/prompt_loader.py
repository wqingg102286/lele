"""
用于加载不同类型的系统提示词（Prompt）。

实现逻辑：
1. 从配置模块 (config_handler) 中读取提示词文件的路径配置。
2. 利用路径工具 (path_tool) 将相对路径转换为绝对路径。
3. 尝试打开并读取指定编码 (utf-8) 的文件内容。
4. 在配置缺失或文件读取失败时，通过日志模块 (logger_handler) 记录错误信息并抛出异常。
主要提供了加载系统提示词、rag 总结提示词和报告生成提示词的三个函数。
"""
from .config_handler import prompts_conf
from .path_tool import get_abs_path
from .logger_handler import logger

def load_system_prompt():
    try:
        system_prompt_path = get_abs_path(prompts_conf["main_prompt_path"])
    except KeyError as e:
        logger.error("[load_system_prompt] 在 yaml 配置中没有 main_prompt_path 配置项")
        raise e     # 记录完后，把错误重新抛出去

    try:
        return open(system_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_system_prompt] 解析系统提示词出错，{str(e)}")
        raise e


def load_rag_prompt():
    try:
        rag_prompt_path = get_abs_path(prompts_conf["rag_summarize_prompt_path"])
    except KeyError as e:
        logger.error("[load_rag_prompt] 在 yaml 配置中没有 rag_summarize_prompt_path 配置项")
        raise e

    try:
        return open(rag_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_rag_prompt] 解析 rag 提示词出错，{str(e)}")
        raise e


def load_report_prompt():
    try:
        report_prompt_path = get_abs_path(prompts_conf["report_prompt_path"])
    except KeyError as e:
        logger.error("[load_report_prompt] 在 yaml 配置中没有 report_prompt_path 配置项")
        raise e

    try:
        return open(report_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_report_prompt] 解析报告提示词出错，{str(e)}")
        raise e

if __name__ == '__main__':
    print(load_report_prompt())