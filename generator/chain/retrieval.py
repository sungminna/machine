from langchain_milvus import Milvus
from langchain_ollama import OllamaEmbeddings
from typing import List

from langchain_core.documents import Document
from langchain_core.runnables import chain


@chain
class Retriever:
    def __init__(self):
        self.uri = "http://localhost:19530"

        self.embeddings = OllamaEmbeddings(
            model="snowflake-arctic-embed2"
        )

        self.vector_store = Milvus(
            embedding_function=self.embeddings,
            connection_args={"uri": self.uri}
        )

    def retriver(self, query: str) -> List[Document]:
        return self.vector_store.similarity_search(query, k=1)


class Milvus_Chain:
    def __init__(self):
        self.uri = "http://localhost:19530"

        self.embeddings = OllamaEmbeddings(
            model="snowflake-arctic-embed2"
        )

        self.vector_store = Milvus(
            embedding_function=self.embeddings,
            connection_args={"uri": self.uri}
        )

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
