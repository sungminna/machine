from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.models import Variable
from airflow.utils.dates import days_ago

from crawling.sel import NamuCrawler, RabbitManager


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=23),
}

def should_initialize(**context):
    try:
        last_init = Variable.get('last_init')
        last_init = datetime.fromisoformat(last_init)
        current = datetime.now()
        return (current - last_init).days >= 1
    except (KeyError, ValueError) as e:
        return True

def initialize_and_fetch_recent(**context):
    try:
        if should_initialize(**context):
            crawler = NamuCrawler()
            new_urls = crawler.crawl_startup()
            Variable.set('last_init', datetime.now().isoformat())
            print('initialized')
        else:
            print('passed initialization')
    except Exception as e:
        print(f"Error during initialization: {str(e)}")
        raise

def process_queue_continuously(**context):
    rabbit_manager = RabbitManager()
    try:
        rabbit_manager.start_consuming()
    except KeyboardInterrupt:
        pass
    finally:
        rabbit_manager.close()


with DAG(
    'namu_crawling',
    default_args=default_args,
    description='Crawl Namu Wiki',
    schedule_interval=timedelta(days=1),
    start_date=days_ago(1),
    catchup=False,
) as dag:

    start_crawl = EmptyOperator(
        task_id='start_crawl',
        dag=dag
    )

    init_task = PythonOperator(
        task_id='initialize_if_needed',
        python_callable=initialize_and_fetch_recent,
    )

    crawl_task = PythonOperator(
        task_id='crawl',
        python_callable=process_queue_continuously,
    )

    end_crawl = EmptyOperator(
        task_id='end_crawl',
        dag=dag
    )

    start_crawl >> init_task >> crawl_task >> end_crawl
