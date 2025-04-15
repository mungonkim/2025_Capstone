import time
import sys
import re
import pandas as pd
import urllib.parse as urlparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 크롬드라이버 초기 설정
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

# 결과 누적 리스트
info_list = []
comment_dict = {}

# 텍스트 파일에서 list URL 읽기  
with open("현판.txt", "r", encoding="utf-8") as f:  #웹툰 url이 들어 있는 txt 파일만 변경하면 됨 
    list_urls = [line.strip() for line in f if line.strip()]

for list_url in list_urls:
    try:
        parsed = urlparse.urlparse(list_url)
        novel_id = urlparse.parse_qs(parsed.query)['novelId'][0]

        def get_detail_url(volume_no):
            return f"https://novel.naver.com/webnovel/detail?novelId={novel_id}&volumeNo={volume_no}"

        # 접속
        driver.get(list_url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 웹소설 기본 정보
        title_tag = soup.find('h2', class_='title')
        title = title_tag.text.strip() if title_tag else f"작품_{novel_id}"

        genre = soup.find('span', class_='item')
        genre = genre.text.strip() if genre else '장르 없음'

        score_tag = soup.select_one('span.score_area')
        score = score_tag.get_text(strip=True).replace('별점', '') if score_tag else '별점 없음'

        download_tag = soup.select_one('span.count')
        download = download_tag.get_text(strip=True) if download_tag else '다운로드 수 없음'

        concern_tag = soup.find('span', id='concernCount')
        concern = concern_tag.text.strip() if concern_tag else '관심 수 없음'

        # 댓글 수집
        comments = []
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'li.wcc_CommentItem__root'))
            )
            for _ in range(20):
                try:
                    more_button = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'button.wcc_CommentMore__more'))
                    )
                    driver.execute_script("arguments[0].scrollIntoView(true);", more_button)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", more_button)
                    time.sleep(1)
                except:
                    break

            last_height = driver.execute_script("return document.body.scrollHeight")
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            comment_items = soup.select('li.wcc_CommentItem__root')
            for item in comment_items:
                body = item.select_one('p.wcc_CommentBody__root span')
                if body:
                    comments.append(body.get_text(strip=True))
        except:
            pass

        # 댓글 저장용 dict 에 추가
        comment_dict[title] = comments

        # 회차 본문 수집
        try:
            total_episode_tag = soup.select_one("span.past_number")
            total_episode = int(re.search(r'\d+', total_episode_tag.text).group()) if total_episode_tag else 0

            mid = total_episode // 2
            volume_nos = list(range(1, 4)) + list(range(mid - 1, mid + 2)) + list(range(total_episode - 2, total_episode + 1))
            episode_texts = {}

            for vol in volume_nos:
                driver.get(get_detail_url(vol))
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'div.detail_view_content.ft15'))
                    )
                    detail_soup = BeautifulSoup(driver.page_source, "html.parser")
                    content_div = detail_soup.select_one('div.detail_view_content.ft15')
                    paragraphs = content_div.find_all('p')
                    text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                    episode_texts[vol] = text
                except:
                    episode_texts[vol] = "본문 로딩 실패"
        except:
            episode_texts = {}

        # 초/중/후 3화
        first_3 = "\n\n".join([episode_texts.get(i, "") for i in range(1, 4)])
        middle_3 = "\n\n".join([episode_texts.get(i, "") for i in range((total_episode // 2) - 1, (total_episode // 2) + 2)])
        last_3 = "\n\n".join([episode_texts.get(i, "") for i in range(total_episode - 2, total_episode + 1)])

        # 정보 누적
        info_list.append({
            "제목": title,
            "장르": genre,
            "별점": score,
            "다운로드 수": download,
            "관심 수": concern,
            "초반 2화": first_3,
            "중간 2화": middle_3,
            "마지막 2화": last_3
        })

        print(f"처리 완료: {title}")

    except Exception as e:
        print(f"오류 발생: {list_url}")
        print(e)

# 드라이버 종료
driver.quit()

# CSV로 저장
df_info = pd.DataFrame(info_list)
df_info.to_csv("현판_본문정보.csv", index=False, encoding="utf-8-sig")
print("📘 전체 본문 CSV 저장 완료")

# 댓글 dict → DataFrame (column = 제목)
df_comment = pd.DataFrame(dict([(k, pd.Series(v)) for k, v in comment_dict.items()]))
df_comment.to_csv("현판_댓글.csv", index=False, encoding="utf-8-sig")
print("💬 전체 댓글 CSV 저장 완료")
