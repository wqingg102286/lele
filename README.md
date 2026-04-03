# Agent 项目跟练（天津生活智能助手）

本项目是一个“本地生活智能助手”类应用的练习实现：把 **ReAct 智能体**、**工具调用**、**RAG（检索增强生成）**、**Chroma 向量库**、以及 **Streamlit 前端**组合在一起，让模型能够在问答中：
- 自动判断是否需要调用工具（天气、定位、知识检索等）
- 需要查“天津办事/生活知识”时，自动去本地向量库检索并基于参考资料回答
- 在多轮对话中保持上下文连续性（只保留最近 N 轮，并对更早内容做摘要压缩）
- 在知识库文档发生变化时，自动做向量库 **增量更新**（避免每次都全量重建）

---

## 一、你需要准备

### 1) 运行环境
- 推荐 Python `3.10+`
- 需要能访问模型与 embedding 服务（通义/DashScope）

### 2) 环境变量
- `GAODE_KEY`  
  高德地图 API Key（用于天气查询/定位识别工具）

- 通义相关（用于模型与向量/embedding）
  - `DASHSCOPE_API_KEY` 或
  - `DASHSCOPE_API_TOKEN`

> 如果 `GAODE_KEY` 未配置，天气与定位工具会直接给出明确的可读报错信息，而不是把 `key=None` 塞进请求导致难排查。

---

## 二、安装与启动

### 1) 安装依赖
在项目 `agent项目跟练` 目录下执行：
```bash
pip install -r requirements.txt
```

### 2) 启动 Web 服务
```bash
streamlit run app.py
```

启动后页面即为“天津生活智能助手”，输入问题后将以**流式**方式显示回答内容。

---

## 三、项目核心能力说明

### 1) ReAct 智能体决策与工具调用
项目采用 LangChain 的 `create_agent` 生成 ReAct 智能体：
- 模型在对话中判断下一步要“思考/行动”
- 根据工具描述，选择是否调用工具：
  - `rag_summarize(query)`：检索天津本地文档并总结回答
  - `get_weather(city)`：查询天气
  - `get_user_location()`：根据公网 IP 获取用户所在城市
  - `fill_context_for_report()`：触发“报告模式”，从而切换到报告写作提示词

### 2) Middleware：工具调用监控 + 动态提示词切换
中间件 `middleware.py` 做两件事：
- `monitor_tool`：拦截工具调用，记录工具名与参数，并在触发 `fill_context_for_report` 时把 `runtime.context["report"] = True`
- `dynamic_prompt`：在模型生成前根据 `runtime.context["report"]` 选择：
  - 普通系统提示词
  - 或“报告模式”提示词

这样你可以在同一个智能体里实现不同输出风格（咨询式 vs 报告式）。

### 3) 多轮上下文记忆（最近 N 轮 + 早期摘要）
客户端使用 `st.session_state["message"]` 保存用户与助手历史对话（用于 UI 展示）。
在 `react_agent.py` 中，真正传给模型的是：
- **最近 N 轮**（默认实现里 `memory_rounds = 6`，即最近 `12` 条 user/assistant 消息）
- 超出最近部分的内容会被压缩为一段中文摘要（不超过 300 字）
- 摘要会被插入到“最新用户消息”中，作为本轮参考上下文

该策略的目标是：既减少上下文长度，又保证连续问答不丢关键信息。

---

## 四、RAG 体系（Chroma + 检索增强生成）

RAG 分为两个阶段：**入库（向量化）** 与 **推理（检索 + 生成）**。

---

### A) 入库阶段：`rag/vector_store.py`

入口类：`VectorStoreService`

#### 1) 扫描知识库文件
程序读取 `config/chroma.yml`：
- `data_path`：知识文件目录（支持递归扫描）
- `allow_knowledge_file_type`：允许的后缀类型，如 `pdf/docx/txt`

系统会遍历目录下所有允许类型文件，准备对每个文件进行 MD5 指纹计算和后续向量化。

#### 2) 文件级 MD5 指纹（增量更新的关键）
项目在本地维护 `md5.text`（v2 格式），用来记录“每个文件相对路径 -> MD5”。

v2 格式说明：
- 第一行：`#v2`
- 后续每行：`relative_path<TAB>md5`

这样就能判断：
- 文件是否新增
- 文件是否修改（同一路径 MD5 变化）
- 文件是否删除（md5.text 中存在但当前目录中消失）

#### 3) 文档加载与切分
对每个需要入库的文件：
- `txt`：用 `TextLoader`
- `pdf`：用 `PyPDFLoader`
- `docx`：用 `Docx2txtLoader`

然后使用 `RecursiveCharacterTextSplitter` 做分块：
- `chunk_size`
- `chunk_overlap`
- `separators`

每个 chunk 会带上 metadata（用于精确删除/更新）：
- `file_path`：文件相对路径
- `file_md5`：文件 MD5
- `chunk_index`：该文件内的分块序号

#### 4) 增量更新策略（避免重复与重建耗时）
当检测到某个文件发生变化时，系统会采取以下顺序：
1. 先按 `file_path` 从 Chroma 中删除该文件旧的 chunk（`delete(where={"file_path": rel_path})`）
2. 再重新切分并把该文件的 chunk 写入向量库（`add_documents`）

对于“未变化”的文件：直接跳过向量更新。

对于“删除”的文件：只执行删除动作，不做写入。

#### 5) 历史遗留兼容：非 v2 的 md5.text 会触发一次全量迁移
如果你之前的 `md5.text` 没有 v2 的结构，系统会触发一次清库全量重建来完成格式迁移；之后就会进入增量更新模式。

---

### B) 推理阶段：`rag/rag_service.py`

入口类：`RagSummarizeService`

#### 1) 检索（retriever）
使用 `VectorStoreService.get_retriever()`：
- `k`：返回候选片段数
- 可选 `score_threshold`：基于相似度分数做过滤

`score_threshold` 的意义：
- 分数低于阈值的 chunk 会被过滤掉
- 这样能减少“看似相关但实际上依据不充分”的资料进入上下文

`config/chroma.yml` 中可配置：
- `score_threshold: 0.2`（示例）

#### 2) 空检索兜底（避免模型胡编）
当过滤/召回后 `context_docs` 为空，系统会直接返回明确提示：
- 若知识库确实为空：提示先入库
- 若知识库非空但无法检索到高度相关资料：提示无法基于已有资料给出可靠回答

这与 `prompts/rag_summarize.txt` 的严格要求形成双保险：  
即模型被约束必须基于参考资料，并在资料不足时做出受限输出。

#### 3) 汇总与生成
把检索到的文档片段拼接为 `context`，再把：
- `input`：用户问题
- `context`：参考资料

填入 `prompts/rag_summarize.txt` 模板，交给模型链进行生成解析输出。

---

## 五、知识检索后如何回答：RAG 与工具链的协同

智能体在回答一个问题时，会根据用户意图自动决定是否调用 `rag_summarize`：
- 如果问题是“天津本地办事/政策/生活知识”，智能体会优先调用 RAG 获取依据
- 如果问题涉及天气/出行环境，智能体会调用天气与定位工具补齐实时信息
- 当触发“报告模式”工具时，会切换到报告写作提示词，提高输出格式与内容组织能力

因此这个项目的回答不是“纯聊天”，而是“工具增强 + 资料依据”的组合式智能体流程。

---

## 六、配置文件说明（config）

### 1) `config/agent.yml`
用于配置外部工具相关参数，例如：
- 高德基础 URL
- 超时设置
- 公网 IP 获取来源列表

### 2) `config/rag.yml`
用于配置模型与 embedding，例如：
- `chat_model_name`
- `embedding_model_name`

### 3) `config/chroma.yml`
用于配置 Chroma 向量库与切分策略，例如：
- `collection_name`
- `persist_directory`
- `data_path`（知识库文件目录）
- `chunk_size` / `chunk_overlap` / `separators`
- `k`（检索返回数量）
- `score_threshold`（可选过滤阈值）
- `md5_hex_store`（指纹文件路径）

### 4) `config/prompts.yml`
用于配置系统提示词模板文件路径，例如：
- `main_prompt_path`
- `rag_summarize_prompt_path`
- `report_prompt_path`

---

## 七、如何验证项目效果（建议顺序）

1. 启动服务并打开页面
```bash
streamlit run app.py
```

2. 输入一个天津本地生活问题（例如“如何办理社保卡？”）
观察：
- 系统是否调用 `rag_summarize`
- 最终回答是否基于“参考资料”内容约束

3. 随后再测试天气/定位类问题
例如：
- “我在天津今天适合户外吗？”
观察：
- 是否调用 `get_user_location` 或 `get_weather`
- 输出是否包含关键天气字段与时间

4. 修改知识库文档后再问相同问题
观察：
- 系统是否自动进行向量库增量更新（文件级 MD5 检测）
- 是否避免旧内容造成的重复或混淆

---

## 八、最后的致谢

感谢黑马课程的系统教学与实践指导，让我能把 ReAct 智能体、RAG 检索、工具调用与工程化流程串成一个可运行的项目，并在不断迭代中真正理解这些模块之间的协作关系。

