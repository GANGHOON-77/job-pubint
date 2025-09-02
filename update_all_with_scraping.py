# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import time

# Firebase 초기화
cred = credentials.Certificate("job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def scrape_job_detail(job_idx):
    """실제 공고 페이지에서 상세요강 전체보기 내용 스크래핑"""
    try:
        detail_url = f"https://job.alio.go.kr/recruitview.do?idx={job_idx}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(detail_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 상세요강 전체보기 내용 추출
        detail_content = ""
        
        # 가능한 모든 클래스명으로 시도
        possible_selectors = [
            'div[class*="content"]',
            'div.recruitView_left',
            'div.recruit_view_left', 
            'div.detail_content',
            'div.content_left',
            'div.left_content',
            '.recruitview_left',
            '.recruit-view-left',
            'div[class*="left"]',
            'div[class*="detail"]'
        ]
        
        for selector in possible_selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    text = element.get_text(separator='\n', strip=True)
                    if text and len(text) > 50:  # 의미있는 내용이 있는지 확인
                        detail_content = text
                        break
                if detail_content:
                    break
        
        if detail_content and len(detail_content) > 50:
            print(f"✓ 스크래핑 성공: {job_idx} ({len(detail_content)}자)")
            return detail_content
        else:
            print(f"❌ 스크래핑 실패: {job_idx} (내용 부족)")
            return None
            
    except Exception as e:
        print(f"❌ 스크래핑 오류 ({job_idx}): {e}")
        return None

def update_all_jobs_with_scraping():
    """모든 기존 채용공고를 스크래핑된 내용으로 업데이트"""
    try:
        # 모든 활성 채용공고 가져오기
        docs = db.collection('recruitment_jobs').where('status', '==', 'active').stream()
        
        jobs_to_update = []
        for doc in docs:
            job_data = doc.to_dict()
            jobs_to_update.append({
                'doc_id': doc.id,
                'idx': job_data.get('idx'),
                'title': job_data.get('title', '제목없음')[:50]
            })
        
        print(f"총 {len(jobs_to_update)}개의 채용공고를 업데이트합니다.")
        
        success_count = 0
        for i, job in enumerate(jobs_to_update):
            print(f"\n[{i+1}/{len(jobs_to_update)}] {job['title']} (idx: {job['idx']})")
            
            # 스크래핑 수행
            scraped_content = scrape_job_detail(job['idx'])
            
            if scraped_content:
                # Firebase 업데이트
                db.collection('recruitment_jobs').document(job['doc_id']).update({
                    'detail_content': scraped_content
                })
                success_count += 1
                print(f"✓ 업데이트 완료")
            else:
                print(f"❌ 업데이트 실패 (스크래핑 실패)")
            
            # 요청 간격 조절 (서버 부하 방지)
            time.sleep(1)
        
        print(f"\n업데이트 완료: {success_count}/{len(jobs_to_update)}개 성공")
        
    except Exception as e:
        print(f"전체 업데이트 실패: {e}")

if __name__ == "__main__":
    update_all_jobs_with_scraping()