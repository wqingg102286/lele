from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompt
from agent.tools.agent_tools import (rag_summarize, get_weather, get_user_location, fill_context_for_report)
from agent.tools.middleware import monitor_tool, log_before_model, report_propmt_switch

from langchain_core.messages import HumanMessage, SystemMessage

class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompt(),
            tools=[rag_summarize,get_weather,get_user_location,fill_context_for_report],
            middleware=[monitor_tool,log_before_model,report_propmt_switch],
        )

        # 多轮上下文：只保留最近 N 轮；更早内容会做一个压缩摘要。
        self.memory_rounds = 6  # 最近 N 轮（N=6 表示最近 6 轮“用户/助手”对话）
        self._summary = ""
        self._summary_upto_msg_count = 0

    def _messages_to_text(self, messages: list[dict]) -> str:
        parts: list[str] = []
        for m in messages:
            role = m.get("role")
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                parts.append(f"用户：{content}")
            elif role == "assistant":
                parts.append(f"助手：{content}")
            else:
                parts.append(f"{role or '未知'}：{content}")
        return "\n".join(parts).strip()

    def _summarize_history(self, older_messages: list[dict]) -> str:
        older_text = self._messages_to_text(older_messages)
        if not older_text:
            return ""

        instruction = (
            "请将下面对话总结为一段简短的中文摘要，供后续回答参考。\n"
            "要求：保留用户需求、已确认事实、关键约束/偏好、已做过的工具调用结论（如果有）。\n"
            "限制：不超过 300 字；不要引入未出现的新信息；只输出摘要正文。"
        )
        resp = chat_model.invoke(
            [
                SystemMessage(content="你是对话摘要器。"),
                HumanMessage(content=f"{instruction}\n\n对话如下：\n{older_text}"),
            ]
        )
        return getattr(resp, "content", "") or str(resp)

    def execute_system(self, query: str, history: list[dict]):
        # `history` 已包含本轮当前用户消息（app.py 会先 append 再调用 execute_system）。
        if not history:
            history = [{"role": "user", "content": query}]

        # 最近 N 轮：2N 条消息（用户/助手各 N 次）。超过则对更早部分做摘要。
        recent_message_count = self.memory_rounds * 2
        recent_messages = history[-recent_message_count:]
        older_messages = history[:-len(recent_messages)] if len(history) > len(recent_messages) else []

        if older_messages:
            # 只有当“需要摘要的旧消息数量”发生变化时才重新总结，减少重复调用。
            if len(older_messages) != self._summary_upto_msg_count:
                self._summary = self._summarize_history(older_messages).strip()
                self._summary_upto_msg_count = len(older_messages)
        else:
            self._summary = ""
            self._summary_upto_msg_count = 0

        messages_for_agent = [dict(m) for m in recent_messages]

        # 把摘要前置到“最新用户消息”中，避免引入额外 role 兼容性问题。
        if self._summary:
            for i in range(len(messages_for_agent) - 1, -1, -1):
                if messages_for_agent[i].get("role") == "user":
                    origin = messages_for_agent[i].get("content") or ""
                    messages_for_agent[i]["content"] = (
                        f"对话摘要（供本轮参考）：{self._summary}\n\n{origin}"
                    )
                    break

        input_dict = {"messages": messages_for_agent}

        # 第三个参数context就是上下文runtime中的信息，就是我们做提示词切换的标记
        for chunk in self.agent.stream(input_dict, stream_mode="values", context={"report": False}):
            latest_message = chunk["messages"][-1]
            if latest_message.content:
                yield latest_message.content.strip() + "\n"


if __name__ == '__main__':
    agent = ReactAgent()

    demo_query = "我在天津想办理社保卡应该怎么做？"
    demo_history = [{"role": "user", "content": demo_query}]
    for chunk in agent.execute_system(demo_query, demo_history):
        print(chunk, end="", flush=True)