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
        self.uri = "http://namu-milvus:19530"

        self.embeddings = OllamaEmbeddings(
            model="snowflake-arctic-embed2",
            base_url="http://namu-ollama:11434"
        )

        self.vector_store = Milvus(
            embedding_function=self.embeddings,
            connection_args={"uri": self.uri},
        )

    async def check_uniqueness(self, query: str) -> bool:
        query = query.page_content if hasattr(query, 'page_content') else query
        res = await self.vector_store.asimilarity_search(query, k=1)
        if not res or res[0].page_content != query:
            return True
        return False

    async def save_documents(self, documents):
        # 모든 유일성 검사를 동시에 실행
        uniqueness_checks = [self.check_uniqueness(doc) for doc in documents]
        results = await asyncio.gather(*uniqueness_checks)
        print(results)
        # 유일한 문서만 필터링
        unique_documents = [doc for doc, is_unique in zip(documents, results) if is_unique]

        if not unique_documents:
            return "No new documents to add"

        uuids = [str(uuid4()) for _ in range(len(unique_documents))]
        res = self.vector_store.aadd_documents(documents=unique_documents, ids=uuids)
        return res

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
    vector = mc.embed_query(input_text)
    print(vector)
