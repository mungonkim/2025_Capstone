import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re

# ChromeDriver 경로 자동 설정
service = Service(ChromeDriverManager().install())

# 웹 드라이버 설정
driver = webdriver.Chrome(service=service)

# URL 설정
url = "https://comic.naver.com/bestChallenge/list?titleId=825136"

match = re.search(r"titleId=(\d+)", url)

if match:
    title_id = match.group(1)

# URL 열기
driver.get(url)

# 페이지 로드 대기 (필요 시 조정)
time.sleep(3)

# 페이지의 HTML 내용 가져오기
html_content = driver.page_source

# BeautifulSoup으로 HTML 파싱
soup = BeautifulSoup(html_content, 'html.parser')

# 제목 출력
title = soup.find('h2', class_='EpisodeListInfo__title--mYLjC').get_text(strip=True)
print(title)

# 장르 추출
genre_text = soup.find('em', class_='ContentMetaInfo__info_item--utGrf').get_text(strip=True)
genre = genre_text.split('∙')[1].strip()
print(genre)

# 줄거리 출력
story = soup.find('p', class_='EpisodeListInfo__summary--Jd1WG EpisodeListInfo__challenge--vanSL').get_text(strip=True)
print(story)

# 총화
story_cnt = soup.find('div', class_='EpisodeListView__count--fTMc5').get_text(strip=True)
print(story_cnt)
cnt = re.search(r'\d+', story_cnt).group()
print(cnt)

# CSV 파일 생성 및 헤더 작성
csv_filename = title + ".csv"
with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["Episode", "Comment"])
    # 각 화의 댓글 수집 및 저장
    for i in range(1, int(cnt) + 1):
        episode_url = f'https://comic.naver.com/bestChallenge/detail?titleId={title_id}&no={i}'
        driver.get(episode_url)
        time.sleep(2)  # 페이지 로드 대기
        
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')

        # 댓글 추출
        comment_texts = soup.find_all('span', class_='u_cbox_contents')
        for comment in comment_texts:
            writer.writerow([i, comment.get_text(strip=True)])

# 웹 드라이버 종료
driver.quit()

print(f"댓글이 {csv_filename} 파일에 저장되었습니다.")
