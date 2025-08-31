# -*- coding: utf-8 -*-
"""
GitHub Actions용 자동 수집 및 정리 스크립트
- 5분마다 신규 게시글 체크 및 수집
- 30일 지난 게시글 자동 삭제
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from bs4 import BeautifulSoup
import time

class GitHubAutoCollector:
    def __init__(self):
        self.service_key = os.getenv('SERVICE_KEY')
        self.firebase_key_path = 'firebase-key.json'
        self.db = None
        self.existing_job_ids = set()
        
        if not self.service_key:
            raise ValueError("SERVICE_KEY environment variable not set")
            
        self.init_firebase()
        self.load_existing_jobs()
        
    def init_firebase(self):
        """Firebase 초기화"""
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(self.firebase_key_path)
                firebase_admin.initialize_app(cred)
            
            self.db = firestore.client()
            print("✅ Firebase 연결 성공")
            
        except Exception as e:
            print(f"❌ Firebase 연결 실패: {e}")
            sys.exit(1)
            
    def load_existing_jobs(self):
        """기존 채용공고 ID 로드"""
        try:
            docs = self.db.collection('recruitment_jobs').stream()
            self.existing_job_ids = {doc.to_dict().get('idx') for doc in docs if doc.to_dict().get('idx')}
            print(f"📋 기존 데이터 {len(self.existing_job_ids)}건 로드 완료")
            
        except Exception as e:
            print(f"⚠️ 기존 데이터 로드 실패: {e}")
            self.existing_job_ids = set()
            
    def delete_old_jobs(self):
        """30일 지난 채용공고 삭제"""
        try:
            cutoff_date = datetime.now() - timedelta(days=30)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d')
            
            print(f"🗑️ {cutoff_str} 이전 공고 삭제 시작...")
            
            # 30일 이전 공고 조회
            docs = self.db.collection('recruitment_jobs')\
                         .where('reg_date', '<', cutoff_str)\
                         .stream()
            
            deleted_count = 0
            batch = self.db.batch()
            batch_count = 0
            
            for doc in docs:
                batch.delete(doc.reference)
                batch_count += 1
                deleted_count += 1
                
                # 500개씩 배치로 삭제 (Firestore 제한)
                if batch_count >= 500:
                    batch.commit()
                    batch = self.db.batch()
                    batch_count = 0
                    
            # 마지막 배치 커밋
            if batch_count > 0:
                batch.commit()
                
            print(f"✅ 만료된 공고 {deleted_count}건 삭제 완료")
            return deleted_count
            
        except Exception as e:
            print(f"❌ 구 데이터 삭제 실패: {e}")
            return 0
            
    def fetch_jobs_from_api(self, page=1, max_pages=3):
        """API에서 채용공고 데이터 가져오기"""
        try:
            url = "http://apis.data.go.kr/1051000/recruitment/list"
            params = {
                'serviceKey': self.service_key,
                'numOfRows': 100,
                'pageNo': page,
                'returnType': 'JSON'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # API 응답 구조 확인
            if 'result' in data and data['result']:
                return data['result']
            elif 'response' in data and 'body' in data['response'] and 'items' in data['response']['body']:
                return data['response']['body']['items']
            else:
                print(f"⚠️ 예상치 못한 API 응답 구조: {list(data.keys())}")
                return []
                
        except Exception as e:
            print(f"❌ API 호출 실패 (페이지 {page}): {e}")
            return []
            
    def get_job_attachments(self, job_idx):
        """채용공고 첨부파일 정보 크롤링"""
        if not job_idx:
            return {}
            
        try:
            detail_url = f"https://job.alio.go.kr/recruitview.do?idx={job_idx}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(detail_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            attachments = {
                'announcement': None,
                'application': None, 
                'job_description': None,
                'others': [],
                'unavailable_reason': None
            }
            
            # 첨부파일 테이블 찾기
            tables = soup.find_all('table')
            for table in tables:
                if '첨부파일' in table.get_text() or '공고문' in table.get_text():
                    rows = table.find_all('tr')
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            category_cell = cells[0]
                            file_cell = cells[1]
                            
                            category = category_cell.get_text(strip=True)
                            file_link = file_cell.find('a')
                            
                            if file_link:
                                href = file_link.get('href', '')
                                file_name = file_link.get_text(strip=True)
                                
                                if 'fileNo=' in href:
                                    file_id = self.extract_file_id(href)
                                    
                                    if '공고문' in category:
                                        attachments['announcement'] = {
                                            'fileID': file_id,
                                            'name': file_name,
                                            'type': 'A'
                                        }
                                    elif '입사지원서' in category:
                                        attachments['application'] = {
                                            'fileID': file_id,
                                            'name': file_name,
                                            'type': 'B'
                                        }
                                    elif '직무기술서' in category:
                                        attachments['job_description'] = {
                                            'fileID': file_id,
                                            'name': file_name,
                                            'type': 'C'
                                        }
                                    elif '기타' in category:
                                        attachments['others'].append({
                                            'fileID': file_id,
                                            'name': file_name,
                                            'type': 'Z'
                                        })
                            elif '미첨부사유' in category and len(cells) >= 2:
                                reason = file_cell.get_text(strip=True)
                                if reason:
                                    attachments['unavailable_reason'] = reason
                    break
            
            return attachments
            
        except Exception as e:
            print(f"⚠️ 첨부파일 크롤링 실패 (idx: {job_idx}): {e}")
            return {}
            
    def extract_file_id(self, url):
        """URL에서 fileID 또는 fileNo 추출"""
        try:
            if 'fileNo=' in url:
                start = url.find('fileNo=') + 7
                end = url.find('&', start)
                if end == -1:
                    return url[start:]
                return url[start:end]
            elif 'fileID=' in url:
                start = url.find('fileID=') + 7
                end = url.find('&', start)
                if end == -1:
                    return url[start:]
                return url[start:end]
        except:
            pass
        return None
        
    def process_job_data(self, job):
        """채용공고 데이터 처리"""
        try:
            # 필수 필드 추출
            job_data = {
                'idx': str(job.get('recrutPblntSn', '')),
                'title': job.get('recrutPbancTtl', ''),
                'dept_name': job.get('instNm', ''),
                'work_region': job.get('workRgnNmLst', ''),
                'employment_type': job.get('empmnStleNmLst', ''),
                'reg_date': self.parse_date(job.get('recrutPblntYmd')),
                'end_date': self.parse_date(job.get('recrutCloseYmd')),
                'recruit_num': self.parse_number(job.get('recrutNope')),
                'recruit_type': job.get('ncsCdNmLst', ''),
                'detail_content': job.get('dtyCn', ''),
                'education': job.get('acdmcrNm', ''),
                'work_field': job.get('ncsCdNmLst', ''),
                'salary_info': job.get('cprtnTypeCd', 'Company policy'),
                'preference': job.get('prefStleNm', ''),
                'recruit_period': f"{self.parse_date(job.get('recrutPblntYmd'))} ~ {self.parse_date(job.get('recrutCloseYmd'))}",
                'src_url': job.get('recrutPbancUrl', ''),
                'source': 'moef_api',
                'status': 'active',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            return job_data
            
        except Exception as e:
            print(f"❌ 데이터 처리 실패: {e}")
            return None
            
    def parse_date(self, date_str):
        """날짜 파싱"""
        if not date_str:
            return None
            
        try:
            date_str = str(date_str).strip()
            
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                return date_str[:10]
            elif re.match(r'\d{8}', date_str):
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            else:
                return datetime.now().strftime('%Y-%m-%d')
                
        except Exception:
            return datetime.now().strftime('%Y-%m-%d')
            
    def parse_number(self, num_str):
        """숫자 파싱"""
        try:
            import re
            return int(re.sub(r'[^\d]', '', str(num_str))) if num_str else 1
        except:
            return 1
            
    def collect_new_jobs(self):
        """신규 채용공고 수집"""
        print("🔍 신규 채용공고 검색 시작...")
        
        new_jobs = []
        total_processed = 0
        
        # 최근 3페이지만 체크 (신규 게시글 위주)
        for page in range(1, 4):
            print(f"📄 페이지 {page} 처리 중...")
            
            jobs = self.fetch_jobs_from_api(page)
            if not jobs:
                continue
                
            for job in jobs:
                total_processed += 1
                job_idx = str(job.get('recrutPblntSn', ''))
                
                if not job_idx or job_idx in self.existing_job_ids:
                    continue
                    
                # 신규 데이터 처리
                job_data = self.process_job_data(job)
                if job_data:
                    # 첨부파일 정보 수집
                    print(f"📎 첨부파일 수집 중: {job_idx}")
                    attachments = self.get_job_attachments(job_idx)
                    if attachments:
                        job_data['attachments'] = attachments
                    
                    new_jobs.append(job_data)
                    self.existing_job_ids.add(job_idx)
                    
                    time.sleep(1)  # API 호출 간격 조절
                    
        print(f"📊 처리 결과: 전체 {total_processed}건 중 신규 {len(new_jobs)}건 발견")
        
        # Firebase에 저장
        if new_jobs:
            self.save_jobs_to_firebase(new_jobs)
            
        return len(new_jobs)
        
    def save_jobs_to_firebase(self, jobs):
        """Firebase에 채용공고 저장"""
        try:
            batch = self.db.batch()
            
            for job in jobs:
                doc_ref = self.db.collection('recruitment_jobs').document(job['idx'])
                batch.set(doc_ref, job)
                
            batch.commit()
            print(f"✅ Firebase에 {len(jobs)}건 저장 완료")
            
        except Exception as e:
            print(f"❌ Firebase 저장 실패: {e}")
            
    def run(self):
        """메인 실행 함수"""
        try:
            print("🚀 GitHub Actions 자동 수집 시작")
            print(f"⏰ 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 매일 3시에만 구 데이터 삭제 (GitHub Actions cron 기준)
            current_hour = datetime.now().hour
            if current_hour == 3:
                deleted_count = self.delete_old_jobs()
                print(f"🗑️ 구 데이터 삭제: {deleted_count}건")
            
            # 신규 데이터 수집
            new_count = self.collect_new_jobs()
            
            print(f"✅ 자동 수집 완료: 신규 {new_count}건")
            
            # 결과 요약
            print("\n📊 실행 결과 요약:")
            print(f"  - 기존 데이터: {len(self.existing_job_ids)}건")
            print(f"  - 신규 수집: {new_count}건") 
            print(f"  - 실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            print(f"❌ 자동 수집 실패: {e}")
            sys.exit(1)

if __name__ == "__main__":
    import re
    collector = GitHubAutoCollector()
    collector.run()