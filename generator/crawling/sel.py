from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from pymongo import MongoClient
class MongoDBManager:
    def __init__(self):
        self.client = MongoClient('mongodb://localhost:27017/')
        self.db = self.client['namu_wiki']
        self.collection = self.db['articles']
        self.collection.create_index('url', unique=True)

    def save_article(self, data):
        data['crawled_at'] = datetime.now()

        self.collection.update_one(
            {'url': data['url']},
            {'$set': data},
            upsert=True
        )

    def close(self):
        self.client.close()

class NamuCrawler():
    def __init__(self, class_name="", attr_name=""):
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
        self.chrome_options.page_load_strategy = 'normal'

        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.driver.set_page_load_timeout(6)
        self.wait = WebDriverWait(self.driver, 6)

        self.driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
            'headers': {
                'X-Forwarded-For': '66.249.66.1',
                'From': 'googlebot(at)googlebot.com'
            }
        })
        self.class_name = class_name
        self.attr_name = attr_name

        self.dbm = MongoDBManager()

    def crawl_startup(self):
        try:
            self.get_attribute_and_tag()
            hrefs = self.get_recent_link()

            for href in hrefs:
                try:
                    href, title, paragraph_names, paragraphs, next_hrefs_unique = self.crawl_namu_data(href)
                    if href is not None and href.strip() != "":
                        data = {
                            'url': href,
                            'title': title,
                            'paragraph_names': paragraph_names,
                            'paragraphs': paragraphs,
                        }
                        self.dbm.save_article(data)
                except Exception as e:
                    print(f"document error: {str(e)}")
                    continue

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
                paragraph_names.extend([self.get_text_content(h) for h in headers])
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
            hrefs = [link.get_attribute('href') for link in links if link.get_attribute('href')]
            next_hrefs_unique = set(hrefs[1:])
            next_hrefs_unique = list(next_hrefs_unique)

            return href, title, paragraph_names, paragraph_data, next_hrefs_unique

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
        element = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h2"))
        )
        attributes = element.get_property('attributes')
        name = ""
        for attr in attributes:
            attr_name = attr['name']
            if attr_name.startswith('data-v-'):
                name = attr_name
                break

        xpath_template = '//div[@{}]'
        xpath = xpath_template.format(name)
        element = self.wait.until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        attributes = element.get_property('attributes')
        parent_class_name = element.get_attribute("class")
        class_name = self.find_para_match(parent_class_name)
        return class_name

    def find_para_match(self, parent_class_name):
        target = "div." + parent_class_name
        elements = self.wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, target))
        )
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

    cr = NamuCrawler()
    cr.crawl_startup()
