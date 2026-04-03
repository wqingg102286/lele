import time

import streamlit as st
from agent.react_agent import ReactAgent


# 标题
st.title("天津生活智能助手")
st.divider()

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

if "message" not in st.session_state:
    st.session_state["message"] = []


for message in st.session_state["message"]:
    st.chat_message(message["role"]).write(message["content"])

# 用户输入提示词
prompt = st.chat_input()

if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})

    response_message = []
    with st.spinner("正在思考..."):
        # 将多轮历史一起传给 Agent：模型既能看到最近 N 轮，也会对更早对话做摘要压缩。
        res_stream = st.session_state["agent"].execute_system(prompt, st.session_state["message"])

        def capture_output(generator, cache_list):
            for chunk in generator:
                cache_list.append(chunk)

                for char in chunk:
                    time.sleep(0.01)
                    yield char

        st.chat_message("assistant").write_stream(capture_output(res_stream, response_message))
        full_response = "".join(response_message)
        st.session_state["message"].append({"role": "assistant", "content": full_response})
        st.rerun()