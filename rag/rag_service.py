
"""
总结服务类： 用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复
"""
from rag.vector_store import VectorStoreService     # 向量数据库服务（搜资料的）
from utils.prompt_loader import load_rag_prompt     # 加载话术
from model.factory import chat_model                 # AI 模型
from langchain_core.prompts import PromptTemplate   # 提示词模板工具
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document


def print_prompt(prompt: str):
    print("="*50)
    print(prompt.to_string())
    print("="*50)
    return prompt

class RagSummarizeService(object):
    def __init__(self):
        self.vector_store = VectorStoreService()            # 准备好图书馆
        self.has_knowledge = self.vector_store.has_documents
        self.collection_count = self.vector_store.collection_count
        self.rag_prompt = load_rag_prompt()                 # 准备好话术本
        self.retriever = self.vector_store.get_retriever()  # 准备好“找书管理员”
        self.model = chat_model                             # 准备好 AI 老师
        self.prompt_template = PromptTemplate.from_template(self.rag_prompt)        # 定义一个带占位符的模板，比如：“根据资料 {context}，回答问题 {input}”
        self.chain = self._init_chain()                     # 把这些串成一条流水线

    def _init_chain(self):
        chain = self.prompt_template | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        # 调用管理员，去数据库里搜索和 query（问题）最相关的文档片段
        docs = self.retriever.invoke(query)
        return docs

    def rag_summarize(self, query: str) -> str:
        # 第一步：搜资料。根据用户的问题，先从图书馆抓取相关片段。
        context_docs = self.retriever_docs(query)

        # 如果没有检索到任何参考资料，直接返回提示，避免模型在没依据时胡编。
        if not context_docs:
            if self.collection_count == 0:
                return "当前知识库为空：请先把资料入库（运行 `rag/vector_store.py` 的 load_document() 或按项目 README 操作）。"
            return "知识库中未检索到与该问题高度相关的资料，无法根据已有资料给出可靠回答。"

        # 第二步：拼凑上下文。
        context = ""
        counter = 0
        for doc in context_docs:
            # 把搜到的每一块资料都加上编号和元数据，拼成一个巨大的“背景资料”字符串
            context += f"参考资料{counter}. 参考资料：{doc.page_content} |参考元数据：{doc.metadata}\n"
            counter += 1

        # 第三步：运行流水线。
        return self.chain.invoke(
            {
                "input": query,  # 将用户问题填入模板的 {input}
                "context": context,  # 将拼好的背景资料填入模板的 {context}
            }
        )

if __name__ == '__main__':
    rag_service = RagSummarizeService()
    print(rag_service.rag_summarize("如何使用扫地机器人"))