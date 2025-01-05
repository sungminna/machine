from langchain_milvus import Milvus
from langchain_ollama import OllamaEmbeddings
from typing import List

from langchain_core.documents import Document
from langchain_core.runnables import chain

from uuid import uuid4

import asyncio



class Milvus_Chain:
    def __init__(self):
        # self.uri = "http://localhost:19530"
        self.uri = "http://milvus-standalone:19530"

        self.embeddings = OllamaEmbeddings(
            model="snowflake-arctic-embed2",
            base_url="http://ollama:11434"
        )

        self.vector_store = Milvus(
            embedding_function=self.embeddings,
            connection_args={"uri": self.uri},
        )

    async def check_uniqueness(self, query: str) -> bool:
        query = query.page_content if hasattr(query, 'page_content') else query
        res = await self.vector_store.asimilarity_search(
            query,
            k=1,
            filter={"source": query.metadata.get('source')},
        )
        if not res or res[0].page_content != query:
            return True
        return False

    async def has_old(self, query, source):
        query = query.page_content if hasattr(query, 'page_content') else "."
        res = await self.vector_store.asimilarity_search(
            query,
            k=1000,
            filter={"source": source},
        )
        if len(res) != 0:
            return True, res
        else:
            return False, None

    async def save_documents(self, documents, source_list):
        # 모든 유일성 검사를 동시에 실행
        # uniqueness_checks = [self.check_uniqueness(doc) for doc in documents]
        # results = await asyncio.gather(*uniqueness_checks)
        # 유일한 문서만 필터링
        # unique_documents = [doc for doc, is_unique in zip(documents, results) if is_unique]

        # if not unique_documents:
        #     return "No new documents to add"

        # uuids = [str(uuid4()) for _ in range(len(unique_documents))]
        old_list = []
        print("save start")
        for doc in documents:
            break
            has_old, res_list = await self.has_old(doc, source_list[0])
            print(res_list)
            if has_old:
                for res in res_list:
                    old_list.append(res.id)
                if old_list:
                    await self.vector_store.adelete(old_list)
                    old_list = []

        batch_size = 5
        total_results = []
        # UUID 미리 생성
        uuids = [str(uuid4()) for _ in range(len(documents))]
        # 10개씩 배치 처리
        for i in range(0, len(documents), batch_size):
            batch_documents = documents[i:i + batch_size]
            texts = []
            metadatas = []
            for d in batch_documents:
                texts.append(d.page_content)
                metadatas.append(d.metadata)
            batch_uuids = [str(uuid4()) for _ in range(len(texts))]
            print(len(batch_uuids), len(texts))
            print(batch_uuids[0])
            res = self.vector_store.add_texts(
                texts=texts,
                metadatas=metadatas,
                ids=batch_uuids
            )

            total_results.append(res)
            print(f"Batch {i // batch_size + 1} processed: {len(batch_documents)} documents")

        return total_results

    async def fetch(self, query):
        results = await self.vector_store.asimilarity_search(query)
        return results

    async def fetch_by_vector(self, vec):
        results = self.vector_store.asimilarity_search_by_vector(vec)
        return results


    async def embed_query(self, query):
        vector = await self.embeddings.aembed_query(query)
        return vector

    async def embed_texts(self, texts):
        vector = await self.embeddings.aembed_texts(texts)
        return vector

    async def embed_documents(self, documents):
        vector = await self.embeddings.aembed_documents(documents)
        return vector


    def test(self):
        input_text = "this to vec"
        vector = self.embeddings.aembed_query(input_text)
        print(vector)


if __name__ == "__main__":
    input_text = "this to vec"
    mc = Milvus_Chain()
    print(mc)
    # vector = mc.embed_query(input_text)
    # print(vector)
    # LangChainCollection 수동 생성 필요하다