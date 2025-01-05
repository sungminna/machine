from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

from pymongo import MongoClient

import pika
import json

from selenium.webdriver.chrome.service import Service

from airflow.utils.log.logging_mixin import LoggingMixin
class RabbitManager:
    def __init__(self, crawler=None):
        # self.connection = pika.BlockingConnection(
        #     pika.ConnectionParameters(host='localhost')
        # )
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='rabbitmq')
        )
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='task_queue', durable=True)
        if crawler:
            self.crawler = crawler
        else:
            self.crawler = NamuCrawler()
            self.crawler.get_attribute_and_tag()
        print(self.crawler.attr_name, self.crawler.class_name)

    def publish_url(self, url):
        message = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
        }
        self.channel.basic_publish(
            exchange='',
            routing_key='task_queue',
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )

    def callback(self, ch, method, properties, body):
        try:
            data = json.loads(body)
            url = data['url']
            try:
                href, title, paragraph_names, paragraphs, next_hrefs_unique = self.crawler.crawl_namu_data(url)
                if href is None:
                    return None
                for next_url in next_hrefs_unique:
                    self.publish_url(next_url)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                print(f"Crawling error: {e}")
                ch.basic_ack(delivery_tag=method.delivery_tag)

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def start_consuming(self):
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue='task_queue',
            on_message_callback=self.callback
        )
        self.channel.start_consuming()

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()


class MongoDBManager(LoggingMixin):
    def __init__(self):
        super().__init__()
        # self.client = MongoClient('mongodb://localhost:27017/')
        self.client = MongoClient(
            'mongodb://namu:namu@mongodb:27017/'
        )
        self.db = self.client['namu_wiki']
        self.collection = self.db['articles']
        self.collection.create_index('url', unique=True)

    def save_article(self, data):
        if not data.get('url'):
            print("Error: Missing URL")
            return False

        try:
            self.log.info('mongodd')
            self.log.info(data)
            data['crawled_at'] = datetime.now()
            if 'title' not in data:
                data['title'] = ''
            if 'paragraphs' not in data:
                data['paragraphs'] = []
            if 'paragraph_names' not in data:
                data['paragraph_names'] = []
            if 'needs_vectorize' not in data:
                data['needs_vectorize'] = True
            if 'vectorized_at' not in data:
                data['vectorized_at'] = "not_yet"
            print(data)
            result = self.collection.update_one(
                {'url': data['url']},
                {'$set': data},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"Error saving article: {str(e)}")
            return False

    def get_article(self, url):
        return self.collection.find_one({'url': url})

    def close(self):
        self.client.close()

class NamuCrawler(LoggingMixin):
    def __init__(self, class_name="", attr_name=""):
        super().__init__()
        self.chrome_options = Options()
        # self.chrome_options.add_argument("--headless=new")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument('--disable-software-rasterizer')
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--disable-infobars')
        self.chrome_options.add_argument('--disable-notifications')
        self.chrome_options.add_argument('--ignore-certificate-errors')
        # self.chrome_options.page_load_strategy = 'eager'

        self.chrome_options.add_argument("--enable-javascript")

        # self.chrome_options.add_argument(f'--user-agent=Googlebot')
        self.chrome_options.add_argument(f'--header=From: googlebot(at)googlebot.com')
        self.chrome_options.add_argument(f'--header=X-Forwarded-For: 66.249.66.1')

        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)

        self.chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')


        # self.driver = webdriver.Chrome(options=self.chrome_options)
        self.driver = webdriver.Remote(
            command_executor='http://selenium:4444/wd/hub',  # docker-compose의 service 이름
            options=self.chrome_options
        )

        self.driver.set_page_load_timeout(7)
        self.wait = WebDriverWait(self.driver, 7)

        self.class_name = class_name
        self.attr_name = attr_name

        self.dbm = MongoDBManager()

    def __del__(self):
        self.driver.quit()


    def crawl_startup(self):
        try:
            self.get_attribute_and_tag()
            print(self.attr_name, self.class_name)
            hrefs = self.get_recent_link()
            print(hrefs)
            rqm = RabbitManager(self)
            self.log.info(rqm)
            for href in hrefs:
                rqm.publish_url(href)
            rqm.close()

        except Exception as e:
            print(f"Critical error: {str(e)}")
        finally:
            self.driver.quit()
            self.dbm.close()


    def crawl_namu_data(self, href):
        self.driver.get(href)
        try:
            # 제목 수집
            titles = self.safe_find_elements('h1')
            title = titles[0].text
            if titles:
                print(f"Title: {title}")

            # 모든 헤더 수집
            paragraph_names = []
            for header_level in ['h2', 'h3', 'h4']:
                headers = self.safe_find_elements(f'{header_level}')
                paragraph_names.extend([str(self.get_text_content(h)) for h in headers])
            paragraph_names = self.normalize_section_number(paragraph_names)
            if paragraph_names:
                paragraph_names = [name for name in paragraph_names if name]  # 빈 문자열 제거
                #paragraph_names.sort()
                print(f"Found {len(paragraph_names)} headers:", paragraph_names)
            else:
                print("No headers found in this page")

            # 본문 단락 수집
            selector = 'div.' + self.class_name
            paragraphs = self.safe_find_elements(selector)
            paragraph_data = []
            if paragraphs:
                print(f"\nFound {len(paragraphs)} paragraphs:")
                for i, para in enumerate(paragraphs, 1):
                    text = para.get_attribute('textContent')
                    paragraph_data.append(text)
                    print(f"Paragraph {i}: {text[:100]}...")  # 처음 100자만 출력
            else:
                print("No paragraphs found in this page")

            # 페이지 내 링크 수집
            links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href^="/w/"]')
            hrefs = []
            for link in links:
                try:
                    href = link.get_attribute('href')
                    if href and isinstance(href, str) and href.startswith('https://namu.wiki/w/'):
                        hrefs.append(href)
                except Exception as e:
                    print(f"Error getting href from link: {e}")
                    continue
            if hrefs:
                next_hrefs_unique = list(set(hrefs[1:]))
            else:
                next_hrefs_unique = []

            if href is not None and href.strip() != "":
                data = {
                    'url': href,
                    'title': title,
                    'paragraph_names': paragraph_names,
                    'paragraphs': paragraph_data,
                    'needs_vectorize': True,
                    'vectorized_at': "not_yet",
                }
                self.dbm.save_article(data)
            return href, title, paragraph_names, paragraph_data, next_hrefs_unique

        except WebDriverException as e:
            if "connection refused" in str(e).lower():
                # 연결이 끊어진 경우 드라이버 재시작
                try:
                    self.driver.quit()
                    self.dbm.close()
                    self.__init__()
                    self.get_attribute_and_tag()
                except Exception as init_error:
                    print(f"Failed to reinitialize driver: {init_error}")
            return None, None, None, None, None

        except Exception as e:
            print(f"Error processing page {href}: {str(e)}")

    def get_attribute_and_tag(self):
        self.driver.get('https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4')
        self.class_name = self.find_paragraph_attr_name()

        # 최근 변경 페이지 접근
        self.driver.get('https://namu.wiki/RecentChanges')
        self.attr_name = self.find_recent_changes_attr_name()

    def get_recent_link(self):
        self.driver.get('https://namu.wiki/RecentChanges')
        xpath_template = '//a[@{} and starts-with(@href, "/w/")]'
        xpath = xpath_template.format(self.attr_name)
        # 링크 수집
        links = self.safe_find_elements(
            xpath,
            By.XPATH
        )
        hrefs = [link.get_attribute('href') for link in links if link.get_attribute('href')]
        return hrefs

    def find_paragraph_attr_name(self):
        self.log.info('find_attr_start')

        # JavaScript로 직접 속성 가져오기
        script = """
        const element = document.querySelector('h2');
        const attributes = Array.from(element.attributes);
        return attributes.map(attr => ({
            name: attr.name,
            value: attr.value
        }));
        """
        attributes = self.driver.execute_script(script)

        # data-v- 속성 찾기
        data_attr = None
        for attr in attributes:
            self.log.info(attr)
            if attr['name'].startswith('data-v-'):
                data_attr = attr['name']
                break

        if not data_attr:
            raise ValueError("Could not find data-v- attribute")

        # div 요소 찾기
        script_div = f"""
        const div = document.querySelector('div[{data_attr}]');
        return div ? div.getAttribute('class') : null;
        """
        parent_class_name = self.driver.execute_script(script_div)
        if not parent_class_name:
            raise ValueError("No class attribute found on element")

        class_name = self.find_para_match(parent_class_name)
        return class_name

    def find_para_match(self, parent_class_name):
        target = "div." + self.escape_css_selector(parent_class_name)
        self.log.info(target)
        elements = self.wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, target))
        )
        self.log.info(elements)
        if len(elements) > 3:
            element = elements[2]
        else:
            element = elements[0]
        pass_name = element.get_attribute("class")
        child_divs = element.find_elements(By.TAG_NAME, "div")
        class_name = ''
        for div in child_divs:
            name = div.get_attribute("class")
            if name:  # 클래스가 있는 경우만
                class_name = name
                break
        return class_name

    def escape_css_selector(self, selector):
        return selector.replace('+', '\\+')

    def find_recent_changes_attr_name(self):
        element = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article > div:nth-child(3) > div:nth-child(2)"))
        )
        class_name = element.get_attribute("class")
        attributes = element.get_property('attributes')
        for attr in attributes:
            attr_name = attr['name']
            if attr_name.startswith('data-v-'):
                return attr_name

    def safe_find_elements(self, selector, by=By.CSS_SELECTOR):
        """안전하게 요소들을 찾는 헬퍼 함수"""
        try:
            elements = self.wait.until(EC.presence_of_all_elements_located((by, selector)))
            return elements
        except TimeoutException:
            print(f"Warning: No elements found for selector '{selector}'")
            return []

    def get_text_content(self, element):
        """요소의 텍스트를 안전하게 가져오는 헬퍼 함수"""
        try:
            return element.text.strip("[편집]\n") if element else ""
        except Exception:
            return ""

    def normalize_section_number(self, sections):
        def convert_to_tuple(section):
            # 마지막 텍스트 부분을 제외한 숫자들 추출 (예: "1.1.1." -> [1, 1, 1])
            numbers_part = section.split('.')[:-1]  # 마지막 요소(텍스트)는 제외

            # 각 숫자를 정수로 변환
            numbers = []
            for num in numbers_part:
                try:
                    if num.strip():  # 빈 문자열이 아닌 경우만 처리
                        numbers.append(int(num))
                except ValueError:
                    continue

            # 정렬을 위해 튜플로 반환
            return (tuple(numbers), section)  # 원본 문자열도 함께 저장

        # 변환 후 정렬
        sorted_items = sorted(sections, key=convert_to_tuple)
        return sorted_items


if __name__ == "__main__":

    #cr = NamuCrawler()
    #cr.crawl_startup()
    #print('init done')
    mq = RabbitManager()
    try:
        mq.start_consuming()
    except KeyboardInterrupt:
        mq.close()
