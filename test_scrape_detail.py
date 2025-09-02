# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

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
        
        print(f"스크래핑 URL: {detail_url}")
        response = requests.get(detail_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print("페이지 구조 분석 중...")
        
        # 가능한 모든 클래스명으로 시도
        possible_selectors = [
            'div.recruitView_left',
            'div.recruit_view_left', 
            'div.detail_content',
            'div.content_left',
            'div.left_content',
            '.recruitview_left',
            '.recruit-view-left',
            'div[class*="left"]',
            'div[class*="content"]',
            'div[class*="detail"]'
        ]
        
        detail_content = ""
        
        for selector in possible_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"찾은 셀렉터: {selector} ({len(elements)}개)")
                for element in elements:
                    text = element.get_text(separator='\n', strip=True)
                    if text and len(text) > 50:  # 의미있는 내용이 있는지 확인
                        detail_content = text
                        print(f"내용 추출 성공: {len(text)}자")
                        break
                if detail_content:
                    break
        
        # 모든 셀렉터로 찾지 못했다면 전체 body에서 텍스트 추출
        if not detail_content:
            print("구체적인 셀렉터로 찾지 못함, 전체 body에서 추출 시도")
            body = soup.find('body')
            if body:
                detail_content = body.get_text(separator='\n', strip=True)
                print(f"Body 전체에서 추출: {len(detail_content)}자")
        
        detail_sections = [detail_content] if detail_content else []
            
        result = "\n\n".join(detail_sections) if detail_sections else "내용을 찾을 수 없음"
        print(f"스크래핑 결과 길이: {len(result)}자")
        print(f"미리보기: {result[:500]}...")
        
        return result
        
    except Exception as e:
        print(f"스크래핑 실패: {e}")
        return None

def update_job_with_scraped_content(job_idx):
    """특정 job의 detail_content를 스크래핑한 내용으로 업데이트"""
    scraped_content = scrape_job_detail(job_idx)
    
    if scraped_content:
        # Firebase 업데이트
        docs = db.collection('recruitment_jobs').where('idx', '==', job_idx).limit(1).stream()
        
        for doc in docs:
            db.collection('recruitment_jobs').document(doc.id).update({
                'detail_content': scraped_content
            })
            print(f"✓ Firebase 업데이트 완료: {job_idx}")
            break

if __name__ == "__main__":
    # 테스트할 job_idx
    test_job_idx = "290214"  # 국립낙동강생물자원관
    update_job_with_scraped_content(test_job_idx)