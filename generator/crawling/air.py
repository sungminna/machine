from datetime import datetime, timedelta
import asyncio


from crawling.sel import NamuCrawler, MongoDBManager, RabbitManager
from crawling.text_preprocessing import TextPreprocessor
from chain.retrieval import Milvus_Chain

from langchain_core.documents import Document

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def initialize_and_fetch_recent():
    crawler = NamuCrawler()
    crawler.crawl_startup()
    print('Crawler initialized and fetched recent')

def process_queue(**context):
    rabbit_manager = RabbitManager()
    try:
        rabbit_manager.start_consuming()
    except KeyboardInterrupt:
        pass
    finally:
        rabbit_manager.close()

async def vectorize(url):
    mongo_manager = MongoDBManager()
    text_preprocessor = TextPreprocessor()
    milvus_chain = Milvus_Chain()

    data = mongo_manager.get_article(url)
    paragraphs = data['paragraphs']
    paragraph_list = []
    for para in paragraphs:
        text = text_preprocessor.preprocess(para)
        paragraph_list.append(text)
    sentence_list = []
    for para in paragraph_list:
        sentences = text_preprocessor.chunk(para)
        if sentences:
            for sentence in sentences:
                sentence = Document(page_content=sentence, metadata={'source': url})
                sentence_list.append(sentence)
    # vec = await milvus_chain.embed_documents(sentence_list)
    res = await milvus_chain.save_documents(sentence_list)







if __name__ == '__main__':
    asyncio.run(vectorize('https://namu.wiki/w/%EA%B2%BD%EC%A3%BC%EC%97%AD'))

