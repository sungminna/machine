from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.dates import days_ago
import asyncio

from crawling.sel import MongoDBManager
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
    'execution_timeout': timedelta(minutes=30),
}


async def vectorize(data):
    """문서 벡터화 및 저장"""
    text_preprocessor = TextPreprocessor()
    milvus_chain = Milvus_Chain()

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
                    metadata={'source': data['url']}
                )
                sentence_list.append(sentence)

    if sentence_list:
        try:
            await milvus_chain.save_documents(sentence_list)
            return True
        except Exception as e:
            print(f"Error vectorizing content for {data['url']}: {e}")
            return False
    return False


def process_new_docs(**context):
    """새로 크롤링된 문서 벡터화"""
    mongo_manager = MongoDBManager()

    # needs_vectorize가 True인 문서 조회
    new_docs = mongo_manager.collection.find_articles({
        'needs_vectorize': True,
    }, limit=100)

    if not new_docs:
        print("No new documents to vectorize")
        return

    async def process_batch(docs):
        for doc in docs:
            success = await vectorize(doc)
            if success:
                mongo_manager.collection.update_one(
                    {'url': doc['url']},
                    {
                        '$set': {
                            'needs_vectorize': False,
                            'vectorized_at': datetime.now()
                        }
                    }
                )

    # 비동기 실행
    asyncio.run(process_batch(new_docs))
    print(f"Processed {len(new_docs)} documents")

with DAG(
    'namu_vectorization',
    default_args=default_args,
    description='Namu Wiki Vectorization Pipeline',
    schedule_interval=timedelta(minutes=30),  # 5분마다 실행
    start_date=days_ago(1),
    catchup=False,
) as dag:

    start_vectorize = EmptyOperator(
        task_id='start_vectorize',
        dag=dag
    )

    vectorize_task = PythonOperator(
        task_id='vectorize',
        python_callable=process_new_docs,
    )

    end_vectorize = EmptyOperator(
        task_id='end_vectorize',
        dag=dag
    )

    start_vectorize >> vectorize_task >> end_vectorize
