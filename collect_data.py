# -*- coding: utf-8 -*-
import requests
import json
import time
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from urllib.parse import urlencode
import re

class SimpleCollector:
    def __init__(self):
        self.service_key = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
        self.base_url = "http://apis.data.go.kr/1051000/recruitment/list"
        
        # Firebase 초기화
        try:
            cred = credentials.Certificate("info-gov-firebase-adminsdk-9o52l-f6b59e8ae8.json")
            firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            print("Firebase connected successfully")
        except Exception as e:
            print(f"Firebase connection failed: {e}")
            self.db = None
    
    def fetch_data(self, page=1, rows=50):
        """API에서 데이터 가져오기"""
        params = {
            'serviceKey': self.service_key,
            'numOfRows': str(rows),
            'pageNo': str(page),
            'returnType': 'JSON'
        }
        
        try:
            url = f"{self.base_url}?{urlencode(params)}"
            print(f"Calling API: page {page}")
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # 실제 API 응답 구조에 맞게 수정
            if 'resultCode' in data and data['resultCode'] == 200:
                if 'result' in data and data['result']:
                    items = data['result']
                    total_count = data.get('totalCount', len(items))
                    print(f"Got {len(items)} items from API (total: {total_count})")
                    return items, total_count
            else:
                print(f"API Error: {data.get('resultMsg', 'Unknown error')}")
            
            return [], 0
            
        except Exception as e:
            print(f"API call failed: {e}")
            return [], 0
    
    def process_job(self, job_data):
        """채용 데이터 정리 - 실제 API 필드명 사용"""
        try:
            processed = {
                'idx': str(job_data.get('recrutPblntSn', '')),  # 채용공고일련번호
                'title': str(job_data.get('recrutPbancTtl', '')).strip(),  # 채용공고제목
                'dept_name': str(job_data.get('instNm', '')).strip(),  # 기관명
                'work_region': str(job_data.get('workRgnNmLst', '')).strip(),  # 근무지역명목록
                'employment_type': str(job_data.get('hireTypeNmLst', '')),  # 고용형태명목록
                'reg_date': self.parse_date(job_data.get('pbancBgngYmd', '')),  # 공고시작일
                'end_date': self.parse_date(job_data.get('pbancEndYmd', '')),  # 공고종료일
                'recruit_num': self.parse_number(job_data.get('recrutNope', '1')),  # 채용인원
                'recruit_type': str(job_data.get('recrutSeNm', '')),  # 채용구분명
                'ncs_category': str(job_data.get('ncsCdNmLst', '')).strip(),  # NCS코드명목록
                'education': str(job_data.get('acdmcrCn', '')).strip(),  # 학력내용
                'work_field': str(job_data.get('ncsCdNmLst', '')).strip(),  # 직무분야
                'salary_info': str(job_data.get('salaryInfo', 'Company policy')).strip(),  # 급여정보
                'preference': str(job_data.get('prefCondCn', '')).strip(),  # 우대조건내용
                'detail_content': str(job_data.get('aplyQlfcCn', '')).strip(),  # 지원자격내용
                'src_url': str(job_data.get('srcUrl', '')).strip(),  # 원본URL
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'status': 'active',
                'source': 'moef_api'
            }
            
            if processed['reg_date'] and processed['end_date']:
                processed['recruit_period'] = f"{processed['reg_date']} ~ {processed['end_date']}"
            
            return processed if processed['idx'] and processed['title'] else None
            
        except Exception as e:
            print(f"Job processing failed: {e}")
            return None
    
    def parse_date(self, date_str):
        """날짜 파싱"""
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d')
        
        try:
            date_str = str(date_str).strip()
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                return date_str[:10]
            if re.match(r'\d{8}', date_str):
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            return datetime.now().strftime('%Y-%m-%d')
        except:
            return datetime.now().strftime('%Y-%m-%d')
    
    def parse_number(self, num_str):
        """숫자 파싱"""
        try:
            return int(re.sub(r'[^\d]', '', str(num_str))) if num_str else 1
        except:
            return 1
    
    def save_to_firebase(self, jobs):
        """Firebase에 저장"""
        if not self.db or not jobs:
            return 0
        
        saved_count = 0
        collection_ref = self.db.collection('recruitment_jobs')
        
        for job in jobs:
            try:
                doc_ref = collection_ref.document(job['idx'])
                doc_ref.set(job)
                saved_count += 1
                print(f"Saved: {job['idx']} - {job['title'][:30]}")
            except Exception as e:
                print(f"Save failed for {job['idx']}: {e}")
        
        return saved_count
    
    def collect_data(self, max_pages=5):
        """데이터 수집 실행"""
        print("=== Starting data collection ===")
        
        all_jobs = []
        page = 1
        
        while page <= max_pages:
            jobs_data, total_count = self.fetch_data(page=page, rows=100)
            
            if not jobs_data:
                print("No more data")
                break
            
            processed_jobs = []
            for job_data in jobs_data:
                processed = self.process_job(job_data)
                if processed:
                    processed_jobs.append(processed)
            
            print(f"Page {page}: processed {len(processed_jobs)} jobs")
            all_jobs.extend(processed_jobs)
            
            time.sleep(1)  # API rate limit
            page += 1
        
        # Filter recent jobs (30 days)
        cutoff_date = datetime.now() - timedelta(days=30)
        recent_jobs = []
        
        for job in all_jobs:
            try:
                reg_date = datetime.strptime(job['reg_date'], '%Y-%m-%d')
                end_date = datetime.strptime(job['end_date'], '%Y-%m-%d')
                
                if reg_date >= cutoff_date and end_date >= datetime.now():
                    recent_jobs.append(job)
            except:
                continue
        
        print(f"Filtered jobs: {len(recent_jobs)} (from {len(all_jobs)} total)")
        
        # Save to JSON file first
        if recent_jobs:
            # Save to JSON
            filename = f"jobs_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump({
                        'collected_at': datetime.now().isoformat(),
                        'total_count': len(recent_jobs),
                        'jobs': recent_jobs
                    }, f, ensure_ascii=False, indent=2)
                print(f"Data saved to {filename}")
            except Exception as e:
                print(f"JSON save failed: {e}")
            
            print(f"=== Collection completed ===")
            print(f"Total collected: {len(all_jobs)} jobs")
            print(f"Recent jobs (30 days): {len(recent_jobs)} jobs") 
            print(f"Sample job titles:")
            for i, job in enumerate(recent_jobs[:5], 1):
                print(f"  {i}. {job['title'][:50]} - {job['dept_name']}")
            return len(recent_jobs)
        
        return 0

if __name__ == "__main__":
    collector = SimpleCollector()
    result = collector.collect_data(max_pages=3)
    print(f"Final result: {result} jobs collected and saved")