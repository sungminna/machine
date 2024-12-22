from pymilvus import MilvusClient
class Milvus:
    def __init__(self):
        self.client = MilvusClient("http://localhost:19530")

    def f(self):
        res = self.client.list_collections()


        print(res)


if __name__ == '__main__':
    mv = Milvus()
    mv.f()