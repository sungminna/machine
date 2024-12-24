from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.utils.dates import days_ago
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
    'queue': 'namu_queue',
}

def should_initialize(**context):
    try:
        last_init = Variable.get('last_init')
        last_init = datetime.fromisoformat(last_init)
        current = datetime.now()
        return (current - last_init).days >= 1
    except KeyError as e:
        return True

def initialize_and_fetch_recent(**context):
    if should_initialize(**context):

        crawler = NamuCrawler()
        new_urls = crawler.crawl_startup()

        Variable.set('last_init', datetime.now().isoformat())
        print('initialized')
    else:
        print('passed initialization')

def process_queue_continuously(**context):
    rabbit_manager = RabbitManager()
    try:
        rabbit_manager.start_consuming()
    except KeyboardInterrupt:
        pass
    finally:
        rabbit_manager.close()

async def vectorize(url):
    """문서 벡터화 및 저장"""
    mongo_manager = MongoDBManager()
    text_preprocessor = TextPreprocessor()
    milvus_chain = Milvus_Chain()

    data = mongo_manager.get_article(url)
    if not data:
        print(f"No data found for URL: {url}")
        return

    paragraph_list = []
    for para in data['paragraphs']:
        text = text_preprocessor.preprocess(para)
        paragraph_list.append(text)

    sentence_list = []
    for para in paragraph_list:
        sentences = text_preprocessor.chunk(para)
        if sentences:
            for sentence in sentences:
                sentence = Document(
                    page_content=sentence,
                    metadata={'source': url}
                )
                sentence_list.append(sentence)

    if sentence_list:
        res = await milvus_chain.save_documents(sentence_list)
        print(f"Vectorized and saved {len(sentence_list)} sentences for {url}")
        return res
    else:
        print(f"No sentences to vectorize for {url}")


def preprocess_article(url: str, **context) -> dict:
    text_preprocessor = TextPreprocessor()
    crawler = NamuCrawler()
    content = crawler.get