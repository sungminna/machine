from pymilvus import MilvusClient
class Milvus:
    def __init__(self):
        self.client = MilvusClient("http://localhost:19530")

        