from typing import Callable
from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model, after_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from utils.logger_handler import logger
from langgraph.runtime import Runtime
from utils.prompt_loader import load_system_prompt,load_report_prompt

@wrap_tool_call()           # 工具执行前的日志记录，工具执行后的日志记录，工具执行失败的日志记录
def monitor_tool(
        request: ToolCallRequest,            # 请求的数据封装
        handler: Callable[[ToolCallRequest], ToolMessage | Command]                   # 执行的函数本身
) -> ToolMessage | Command:                     # 工具执行的监控
    logger.info(f"[tool monitor]执行工具：{request.tool_call['name']}")
    logger.info(f"[tool monitor]传入参数：{request.tool_call['args']}")

    try:
        result = handler(request)
        logger.info(f"[tool monitor]工具执行结果：{result}，调用成功")
        if request.tool_call['name'] == "fill_context_for_report":
            request.runtime.context["report"]=True

        return  result
    except Exception as e:
        logger.exception(f"工具{request.tool_call['name']}调用失败")
        raise  # 让上层感知并保留原始堆栈

@before_model()
def log_before_model(
        state: AgentState,          # 整个Agent智能体中的状态记录
        runtime: Runtime,           # 记录了整个执行过程中的上下文信息
):
    logger.info(f"[log_before_model]即将调用模型，带有{len(state['messages'])}条消息。")

    messages = state.get("messages", [])
    if not messages:
        logger.warning("[log_before_model]messages为空，跳过最后一条消息内容日志。")
        return None

    last_msg = messages[-1]
    content = getattr(last_msg, "content", "") or ""
    logger.debug(f"[log_before_model]{type(last_msg).__name__}当前消息：{content.strip()}")
    return None


@dynamic_prompt()                   # 每一次在生成提示词之前，调用此函数
def report_propmt_switch(requests: ModelRequest):
    is_report = requests.runtime.context.get("report", False)
    if is_report:                   # 判断是否是报告，是报告生成场景就生成报告提示词，否则返回系统提示词
       return load_report_prompt()
    return load_system_prompt()
