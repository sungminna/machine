from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator

from crawling.sel import NamuCrawler, MongoDBManager, RabbitManager

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

with DAG(
    'namu_wiki_crawler',
    default_args=default_args,
    description='Crawls Namu Wiki articles',
    schedule_interval=timedelta(hours=1),
    catchup=False,
    tags=['crawler', 'wiki'],
) as dag:

    start = EmptyOperator(task_id='start')

    init_crawler = PythonOperator(
        task_id='initialize_and_fetch_recent',
        python_callable=initialize_and_fetch_recent,
    )

    process_links = PythonOperator(
        task_id='process_links',
        python_callable=process_queue,
    )

    end = EmptyOperator(task_id='end')