"""
yaml
k: v
相当于写一个从yaml文件中读取数据的函数
为什么配置项要用yaml文件去写：
    天生懂数据类型：它不仅能存文字，还能存数字、真假值、列表，甚至“字典套字典”。
    层级结构清晰：它像 Python 代码一样，通过“缩进（空格）”来表示层级关系，人眼看着非常舒服、一目了然。
    业界标准：几乎所有现代的软件开发（包括 Docker、各种大模型 AI 框架、服务器配置）都约定俗成使用 YAML 或 JSON 来做配置文件。
"""

import yaml
from .path_tool import get_abs_path


def _load_yaml_config(config_path: str, encoding: str = "utf-8") -> dict:
    """
    通用 YAML 加载函数：
    - 保证返回 dict，而不是 None 或其他类型
    - 当配置结构异常时抛出可读错误，便于排查
    """
    with open(config_path, "r", encoding=encoding) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    if data is None:
        # 空文件或只包含注释，统一视为“空配置”
        return {}

    if not isinstance(data, dict):
        raise ValueError(f"配置文件格式错误：{config_path} 的顶层结构应为字典 (mapping)，当前为 {type(data).__name__}")

    return data


def load_rag_config(config_path: str = get_abs_path("config/rag.yml"), encoding: str = "utf-8"):
    """
    加载 rag (Retrieval-Augmented Generation) 配置文件。
    """
    return _load_yaml_config(config_path, encoding)


def load_chroma_config(config_path: str = get_abs_path("config/chroma.yml"), encoding: str = "utf-8"):
    """
    加载 Chroma 向量数据库配置文件。
    """
    return _load_yaml_config(config_path, encoding)


def load_prompts_config(config_path: str = get_abs_path("config/prompts.yml"), encoding: str = "utf-8"):
    """
    加载提示词 (Prompts) 配置文件。
    """
    return _load_yaml_config(config_path, encoding)


def load_agent_config(config_path: str = get_abs_path("config/agent.yml"), encoding: str = "utf-8"):
    """
    加载 Agent 智能体配置文件。
    """
    return _load_yaml_config(config_path, encoding)

rag_conf = load_rag_config()
chroma_conf = load_chroma_config()
prompts_conf = load_prompts_config()
agent_conf = load_agent_config()

if __name__ == '__main__':
    print(rag_conf["chat_model_name"])