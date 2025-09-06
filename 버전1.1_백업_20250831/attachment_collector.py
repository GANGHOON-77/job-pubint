# -*- coding: utf-8 -*-
import sys
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import time
import re

sys.stdout.reconfigure(encoding='utf-8')

class AttachmentCollector:
    """첨부파일 수집기"""
    
    def __init__(self, firebase_key_path):
        # Firebase 초기화
        if not firebase_admin._apps:
            cred = credentials.Certificate(firebase_key_path)
            firebase_admin.initialize_app(cred)
        
        self.db = firestore.client()
    
    def get_job_attachments(self, job_idx):
        """채용공고 페이지에서 첨부파일 정보 크롤링"""
        if not job_idx:
            return {}
        
        try:
            # 채용공고 상세 페이지 URL
            detail_url = f"https://job.alio.go.kr/recruitview.do?idx={job_idx}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(detail_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 첨부파일 정보 추출
            attachments = {
                'announcement': None,      # 공고문
                'application': None,       # 입사지원서
                'job_description': None,   # 직무기술서
                'others': [],              # 기타 첨부파일
                'unavailable_reason': None # 미접수사유
            }
            
            print(f"  🔍 {job_idx} 첨부파일 크롤링 중...")
            
            # 첨부파일 테이블 찾기
            tables = soup.find_all('table')
            for table in tables:
                table_text = table.get_text()
                if '첨부파일' in table_text or '공고문' in table_text or '지원서' in table_text:
                    rows = table.find_all('tr')
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            category_cell = cells[0]
                            file_cell = cells[1]
                            
                            category = category_cell.get_text(strip=True)
                            file_links = file_cell.find_all('a')
                            
                            # 파일 링크가 있는 경우
                            for file_link in file_links:
                                href = file_link.get('href', '')
                                file_name = file_link.get_text(strip=True)
                                
                                if 'fileNo=' in href or 'download' in href.lower():
                                    file_id = self.extract_file_id(href)
                                    
                                    if file_id:
                                        file_info = {
                                            'fileID': file_id,
                                            'name': file_name,
                                            'url': href
                                        }
                                        
                                        # 파일 유형 분류
                                        if '공고문' in category:
                                            attachments['announcement'] = file_info
                                            print(f"    📋 공고문: {file_name}")
                                        elif '입사지원서' in category or '지원서' in category:
                                            attachments['application'] = file_info
                                            print(f"    📝 입사지원서: {file_name}")
                                        elif '직무기술서' in category or '직무' in category:
                                            attachments['job_description'] = file_info
                                            print(f"    📄 직무기술서: {file_name}")
                                        elif '기타' in category or category == '' or len(category) < 3:
                                            attachments['others'].append(file_info)
                                            print(f"    📎 기타: {file_name}")
                                        else:
                                            attachments['others'].append(file_info)
                                            print(f"    📎 {category}: {file_name}")
                            
                            # 미접수사유 확인
                            if '미접수사유' in category or '미첨부' in category:
                                reason = file_cell.get_text(strip=True)
                                if reason and len(reason) > 3:
                                    attachments['unavailable_reason'] = reason
                                    print(f"    ❓ 미첨부사유: {reason}")
            
            # 첨부파일이 하나라도 있는지 확인
            has_files = (
                attachments['announcement'] or 
                attachments['application'] or 
                attachments['job_description'] or 
                attachments['others'] or 
                attachments['unavailable_reason']
            )
            
            if has_files:
                return attachments
            else:
                print(f"    ℹ️ 첨부파일 없음")
                return None
            
        except Exception as e:
            print(f"    ❌ 첨부파일 크롤링 실패: {e}")
            return None
    
    def extract_file_id(self, url):
        """URL에서 fileID 또는 fileNo 추출"""
        try:
            # fileNo= 형태 확인
            if 'fileNo=' in url:
                match = re.search(r'fileNo=([^&]+)', url)
                if match:
                    return match.group(1)
            
            # fileID= 형태 확인
            if 'fileID=' in url:
                match = re.search(r'fileID=([^&]+)', url)
                if match:
                    return match.group(1)
            
            # download 링크인 경우 전체 URL 반환
            if 'download' in url.lower():
                return url
                
        except Exception as e:
            print(f"    ⚠️ 파일 ID 추출 실패: {e}")
            
        return None
    
    def update_job_attachments(self, job_idx):
        """특정 공고의 첨부파일 정보를 Firebase에 업데이트"""
        try:
            # 첨부파일 정보 수집
            attachments = self.get_job_attachments(job_idx)
            
            if attachments:
                # Firebase 업데이트
                doc_ref = self.db.collection('recruitment_jobs').document(str(job_idx))
                doc_ref.update({
                    'attachments': attachments,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                print(f"  ✅ Firebase 업데이트 완료: {job_idx}")
                return attachments
            else:
                print(f"  ℹ️ 업데이트할 첨부파일 없음: {job_idx}")
                return None
                
        except Exception as e:
            print(f"  ❌ Firebase 업데이트 실패 ({job_idx}): {e}")
            return None

if __name__ == "__main__":
    # 테스트
    collector = AttachmentCollector("job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
    
    # 테스트할 공고 번호
    test_idx = "290195"  
    print(f"테스트 공고: {test_idx}")
    
    attachments = collector.update_job_attachments(test_idx)
    if attachments:
        print("\n수집된 첨부파일:")
        print(attachments)