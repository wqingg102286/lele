"""
扫描文件 ➔ 指纹查重 (MD5) ➔ 读取文本 ➔ 切分段落 ➔ 存入向量库 ➔ 记录指纹
"""
from utils.config_handler import chroma_conf
from langchain_chroma import Chroma
from model.factory import embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import shutil
from utils.path_tool import get_abs_path
from utils.file_handler import pdf_loader,txt_loader,word_worder,listdir_with_allowed_type,get_file_md5_hex
from utils.logger_handler import logger
from langchain_core.documents import Document

class VectorStoreService:
    """
    向量数据库服务
    """
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],         # 集合名称
            embedding_function=embed_model,
            persist_directory=chroma_conf["persist_directory"]      # 持久化目录，存放在硬盘上的具体位置
        )
        self.spliter = RecursiveCharacterTextSplitter(              # 文本分块
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )
        self._collection_count = self._get_collection_count()
        # 自动比较 MD5：检测到文件变更则清空 Chroma 并全量重建。
        self.load_document()

    def _get_collection_count(self) -> int:
        """
        尽量获取当前集合里的向量数量；失败时返回 -1（不阻断启动）。
        """
        try:
            # Chroma 内部集合对象提供 count()，不同版本可能略有差异，所以做异常兜底。
            return int(self.vector_store._collection.count())  # type: ignore[attr-defined]
        except Exception:
            return -1

    @property
    def has_documents(self) -> bool:
        return self._collection_count > 0

    @property
    def collection_count(self) -> int:
        return self._collection_count

    def get_retriever(self):            # 获取向量库的检索器,每次搜索时，帮我找回最相关的 k 条资料
        k = chroma_conf["k"]
        score_threshold = chroma_conf.get("score_threshold")

        # 当设置了 score_threshold 时，低相似度结果会被直接过滤，从而触发 rag 的“空检索兜底”逻辑。
        if score_threshold is not None:
            return self.vector_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"k": k, "score_threshold": float(score_threshold)},
            )

        return self.vector_store.as_retriever(search_kwargs={"k": k})

    def load_document(self):
        """
        增量更新：
        - 维护 `md5.text` 的“文件路径 -> MD5”映射（v2 格式）
        - 仅对“新增/修改”的文件重新切分并写入向量库
        - 对“删除”的文件，从向量库中按 `file_path` 删除对应 chunk
        - 若 md5.text 不是 v2 格式（历史遗留），则执行一次全量清库重建以迁移元数据格式
        """

        def get_file_documents(filepath: str):
            if filepath.endswith("txt"):
                return txt_loader(filepath)
            if filepath.endswith("pdf"):
                return pdf_loader(filepath)
            if filepath.endswith("docx"):
                return word_worder(filepath)
            return []

        def get_rel_path(abs_path: str, base_dir_abs: str) -> str:
            # Chroma metadata 用于 delete/过滤，保持稳定格式（统一斜杠）
            rel = os.path.relpath(abs_path, base_dir_abs)
            return rel.replace("\\", "/")

        def read_saved_md5_map(md5_store_abs_path: str) -> tuple[dict[str, str], bool]:
            """
            v2 格式：第一行 `#v2`，后续每行：`relative_path\\tmd5`
            历史遗留格式：仅 md5 一行（无法知道具体文件路径），返回 v2=False。
            """
            if not os.path.exists(md5_store_abs_path):
                return {}, True
            lines = [line.strip() for line in open(md5_store_abs_path, "r", encoding="utf-8").read().splitlines() if line.strip()]
            if not lines:
                return {}, True

            is_v2 = lines[0].startswith("#v2")
            if not is_v2:
                return {}, False

            mapping: dict[str, str] = {}
            for line in lines[1:]:
                if "\t" not in line:
                    continue
                rel, md5 = line.split("\t", 1)
                rel = rel.strip()
                md5 = md5.strip()
                if rel and md5:
                    mapping[rel] = md5
            return mapping, True

        def write_saved_md5_map(md5_store_abs_path: str, mapping: dict[str, str]) -> None:
            with open(md5_store_abs_path, "w", encoding="utf-8") as f:
                f.write("#v2\n")
                for rel_path in sorted(mapping.keys()):
                    f.write(f"{rel_path}\t{mapping[rel_path]}\n")

        def full_rebuild() -> dict[str, str]:
            """
            清空 Chroma 持久化并全量重建，顺便迁移到 v2 md5.text + metadata(file_path)。
            """
            logger.info("[加载知识库] md5.text 非 v2 格式或元数据不一致，执行一次清库全量重建。")
            if os.path.exists(persist_dir_abs_path):
                shutil.rmtree(persist_dir_abs_path)
            if os.path.exists(md5_store_abs_path):
                os.remove(md5_store_abs_path)

            self.vector_store = Chroma(
                collection_name=chroma_conf["collection_name"],
                embedding_function=embed_model,
                persist_directory=chroma_conf["persist_directory"],
            )
            self._collection_count = self._get_collection_count()

            mapping_out: dict[str, str] = {}
            for abs_path in allow_file_paths:
                rel_path = get_rel_path(abs_path, data_root_abs_path)
                md5_hex = get_file_md5_hex(abs_path)
                if not md5_hex:
                    continue
                _upsert_file(abs_path, rel_path, md5_hex)
                mapping_out[rel_path] = md5_hex

            self._collection_count = self._get_collection_count()
            write_saved_md5_map(md5_store_abs_path, mapping_out)
            return mapping_out

        def _delete_by_file_path(rel_path: str) -> None:
            try:
                # Chroma 内部集合对象支持按 metadata 条件 delete
                self.vector_store._collection.delete(where={"file_path": rel_path})  # type: ignore[attr-defined]
            except Exception:
                # delete 失败不阻断，继续 add；但若失败会导致短期重复，需要一次清库兜底
                logger.warning(f"[加载知识库] 删除失败：file_path={rel_path}")

        def _upsert_file(abs_path: str, rel_path: str, md5_hex: str) -> None:
            try:
                documents: list[Document] = get_file_documents(abs_path)
                if not documents:
                    logger.error(f"[加载知识库]文件{abs_path}无有效文本内容，跳过")
                    return

                split_document: list[Document] = self.spliter.split_documents(documents)
                if not split_document:
                    logger.error(f"[加载知识库]文件{abs_path}分片后无有效内容，跳过")
                    return

                # 给每个 chunk 补充用于增量更新/删除的 metadata
                ids: list[str] = []
                for idx, doc in enumerate(split_document):
                    if doc.metadata is None:
                        doc.metadata = {}
                    doc.metadata["file_path"] = rel_path
                    doc.metadata["file_md5"] = md5_hex
                    doc.metadata["chunk_index"] = idx
                    # ids 用于更稳定的写入；即使边界变化，配合 delete 也能保持“无重复”
                    safe_rel = rel_path.replace(":", "_")
                    ids.append(f"chunk__{safe_rel}__{idx}")

                _delete_by_file_path(rel_path)  # 修改文件前先删旧向量，避免重复
                try:
                    self.vector_store.add_documents(split_document, ids=ids)
                except TypeError:
                    # 兼容不同版本的 Chroma 封装；即使不传 ids，也能依赖 delete(where=file_path) 保持“无重复”
                    self.vector_store.add_documents(split_document)
                logger.info(f"[加载知识库]文件{abs_path}已增量写入向量库")
            except Exception as e:
                logger.error(f"[加载知识库]文件{abs_path}处理失败:{str(e)}", exc_info=True)

        # -------- 入口：准备文件清单与 md5 映射 --------
        md5_store_abs_path = get_abs_path(chroma_conf["md5_hex_store"])
        persist_dir_abs_path = get_abs_path(chroma_conf["persist_directory"])
        data_root_abs_path = get_abs_path(chroma_conf["data_path"])

        allow_file_paths: list[str] = listdir_with_allowed_type(
            data_root_abs_path,
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        # 当前文件集：relative_path -> md5
        current_mapping: dict[str, str] = {}
        for abs_path in allow_file_paths:
            rel_path = get_rel_path(abs_path, data_root_abs_path)
            md5_hex = get_file_md5_hex(abs_path)
            if not md5_hex:
                raise RuntimeError(f"[加载知识库] 文件 MD5 计算失败：{abs_path}")
            current_mapping[rel_path] = md5_hex

        saved_mapping, saved_is_v2 = read_saved_md5_map(md5_store_abs_path)
        if not saved_is_v2:
            # 迁移：第一次运行仍可能耗时，但只发生一次（之后增量更新会很快）
            full_rebuild()
            return

        # 计算新增/修改/删除
        changed_files: list[str] = []
        for rel_path, md5_hex in current_mapping.items():
            if saved_mapping.get(rel_path) != md5_hex:
                changed_files.append(rel_path)

        removed_files: list[str] = [rel for rel in saved_mapping.keys() if rel not in current_mapping]

        if not changed_files and not removed_files:
            logger.info("[加载知识库] 知识库文件未变化，跳过向量更新。")
            return

        # 增量删除：移除已删除文件
        for rel_path in removed_files:
            _delete_by_file_path(rel_path)
            saved_mapping.pop(rel_path, None)

        # 增量更新：对新增/修改文件进行 upsert
        # 需要从 abs_path 找到 rel_path 对应的文件
        abs_path_by_rel: dict[str, str] = {get_rel_path(p, data_root_abs_path): p for p in allow_file_paths}
        for rel_path in changed_files:
            abs_path = abs_path_by_rel.get(rel_path)
            if not abs_path:
                continue
            md5_hex = current_mapping[rel_path]
            _upsert_file(abs_path, rel_path, md5_hex)
            saved_mapping[rel_path] = md5_hex

        self._collection_count = self._get_collection_count()
        write_saved_md5_map(md5_store_abs_path, saved_mapping)

if __name__ == '__main__':
    vector_store = VectorStoreService()
    retriever = vector_store.get_retriever()
    res = retriever.invoke("在天津怎么办理社保卡")
    for r in res:
        print(r.page_content)
        print("-"*20)