import requests
import json
import csv
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode
import time
import random
from bs4 import BeautifulSoup
import re
import os
import firebase_admin
from firebase_admin import credentials, firestore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_collection.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class PublicJobCollector:
    def __init__(self):
        self.service_key = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
        self.base_url = "http://apis.data.go.kr/1051000/recruitment/list"
        self.collected_jobs = []
        self.total_collected = 0
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        self.init_firebase()

    def init_firebase(self):
        try:
            if not firebase_admin._apps:
                if os.path.exists('파이어베이스 인증/job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json'):
                    cred = credentials.Certificate('파이어베이스 인증/job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json')
                else:
                    cred_dict = {
                        "type": "service_account",
                        "project_id": "job-pubint",
                        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                        "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
                        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                        "client_id": os.getenv("FIREBASE_CLIENT_ID"),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
                    }
                    cred = credentials.Certificate(cred_dict)
                
                firebase_admin.initialize_app(cred)
                logging.info("Firebase 초기화 완료")
            
            self.db = firestore.client()
        except Exception as e:
            logging.error(f"Firebase 초기화 실패: {e}")
            self.db = None

    def fetch_job_data(self, num_rows=100, page_no=1):
        try:
            params = {
                'serviceKey': self.service_key,
                'numOfRows': str(num_rows),
                'pageNo': str(page_no),
                'returnType': 'JSON'
            }
            
            logging.info(f"API 요청: 페이지 {page_no}, 행 수 {num_rows}")
            
            url = f"{self.base_url}?{urlencode(params)}"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('resultCode') == 200:
                result = data.get('result', [])
                total_count = data.get('totalCount', 0)
                
                if result:
                    logging.info(f"페이지 {page_no}: {len(result)}개 채용공고 수집 완료")
                    return result, total_count
                else:
                    logging.warning(f"페이지 {page_no}: 결과 없음")
                    return [], total_count
            else:
                logging.error(f"API 오류: {data.get('resultMsg', '알 수 없는 오류')}")
                return [], 0
                
        except requests.exceptions.RequestException as e:
            logging.error(f"API 요청 실패: {e}")
            return [], 0
        except Exception as e:
            logging.error(f"데이터 처리 오류: {e}")
            return [], 0

    def parse_date(self, date_str):
        if not date_str or date_str == 'null':
            return None
        
        date_formats = [
            '%Y%m%d',
            '%Y-%m-%d',
            '%Y.%m.%d',
            '%Y/%m/%d'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(str(date_str).strip(), fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        logging.warning(f"날짜 파싱 실패: {date_str}")
        return None

    def clean_text(self, text):
        if not text or text == 'null':
            return ""
        
        text = str(text).strip()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s가-힣\(\)\[\].,;:\-\+\/\%\&\@\!\?\'\"]', '', text)
        return text[:500]

    def filter_recent_jobs(self, jobs, days=30):
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_jobs = []
        
        for job in jobs:
            try:
                reg_date_str = self.parse_date(job.get('pbancBgngYmd'))
                if not reg_date_str:
                    continue
                    
                reg_date = datetime.strptime(reg_date_str, '%Y-%m-%d')
                
                end_date_str = self.parse_date(job.get('pbancEndYmd'))
                if end_date_str:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                else:
                    end_date = datetime.now() + timedelta(days=30)
                
                if reg_date >= cutoff_date and end_date >= datetime.now():
                    filtered_jobs.append(job)
                    
            except Exception as e:
                logging.warning(f"날짜 필터링 오류: {e}, job: {job.get('recrutPblntSn')}")
                continue
        
        logging.info(f"필터링 결과: {len(filtered_jobs)}개 유효한 채용공고")
        return filtered_jobs

    def process_job_data(self, job):
        try:
            processed_job = {
                'idx': str(job.get('recrutPblntSn', '')),
                'title': self.clean_text(job.get('recrutPbancTtl', '')),
                'company': self.clean_text(job.get('instNm', '')),
                'location': self.clean_text(job.get('workRgnNmLst', '')),
                'job_type': self.clean_text(job.get('hireTypeNmLst', '')),
                'reg_date': self.parse_date(job.get('pbancBgngYmd')),
                'end_date': self.parse_date(job.get('pbancEndYmd')),
                'url': job.get('srcUrl', ''),
                'ncs_code': job.get('ncsCdLst', ''),
                'ncs_name': self.clean_text(job.get('ncsCdNmLst', '')),
                'recruit_count': job.get('recrutNope', 0),
                'qualification': self.clean_text(job.get('aplyQlfcCn', '')),
                'procedure': self.clean_text(job.get('scrnprcdrMthdExpln', '')),
                'preference': self.clean_text(job.get('prefCn', '')),
                'disqualification': self.clean_text(job.get('disqlfcRsn', '')),
                'education': self.clean_text(job.get('acbgCondNmLst', '')),
                'status': 'active',
                'updated_at': datetime.now().isoformat(),
                'created_at': datetime.now().isoformat()
            }
            
            try:
                processed_job['recruit_count'] = int(processed_job['recruit_count']) if processed_job['recruit_count'] else 0
            except (ValueError, TypeError):
                processed_job['recruit_count'] = 0
            
            return processed_job
            
        except Exception as e:
            logging.error(f"데이터 처리 오류: {e}, job: {job}")
            return None

    def save_to_firebase(self, jobs):
        if not self.db:
            logging.error("Firebase 연결 없음")
            return False
        
        saved_count = 0
        updated_count = 0
        
        try:
            batch = self.db.batch()
            batch_count = 0
            
            for job in jobs:
                if not job or not job.get('idx'):
                    continue
                
                doc_ref = self.db.collection('jobs').document(job['idx'])
                
                try:
                    existing_doc = doc_ref.get()
                    
                    if existing_doc.exists:
                        job['updated_at'] = datetime.now().isoformat()
                        batch.update(doc_ref, job)
                        updated_count += 1
                    else:
                        batch.set(doc_ref, job)
                        saved_count += 1
                    
                    batch_count += 1
                    
                    if batch_count >= 500:
                        batch.commit()
                        batch = self.db.batch()
                        batch_count = 0
                        time.sleep(0.1)
                        
                except Exception as e:
                    logging.error(f"문서 처리 오류: {e}, idx: {job.get('idx')}")
                    continue
            
            if batch_count > 0:
                batch.commit()
            
            logging.info(f"Firebase 저장 완료: 신규 {saved_count}개, 업데이트 {updated_count}개")
            return True
            
        except Exception as e:
            logging.error(f"Firebase 저장 실패: {e}")
            return False

    def collect_data(self, max_pages=None, save_to_file=True, days_filter=30):
        logging.info(f"데이터 수집 시작: 최근 {days_filter}일 이내 채용공고")
        
        all_jobs = []
        page = 1
        total_count = 0
        
        try:
            while True:
                if max_pages and page > max_pages:
                    break
                
                jobs, total = self.fetch_job_data(page_no=page)
                
                if page == 1:
                    total_count = total
                    logging.info(f"전체 {total_count}개 채용공고 발견")
                
                if not jobs:
                    logging.info(f"페이지 {page}: 더 이상 데이터 없음")
                    break
                
                processed_jobs = []
                for job in jobs:
                    processed_job = self.process_job_data(job)
                    if processed_job:
                        processed_jobs.append(processed_job)
                
                if processed_jobs:
                    filtered_jobs = self.filter_recent_jobs(processed_jobs, days=days_filter)
                    all_jobs.extend(filtered_jobs)
                
                logging.info(f"페이지 {page} 처리 완료: {len(processed_jobs)}개 -> {len([j for j in processed_jobs if j in self.filter_recent_jobs(processed_jobs, days=days_filter)])}개 유효")
                
                page += 1
                time.sleep(random.uniform(0.5, 1.0))
                
                if len(jobs) < 100:
                    logging.info(f"마지막 페이지 도달: {page-1}")
                    break
        
        except KeyboardInterrupt:
            logging.info("사용자에 의해 중단됨")
        except Exception as e:
            logging.error(f"데이터 수집 중 오류: {e}")
        
        logging.info(f"총 {len(all_jobs)}개 유효한 채용공고 수집 완료")
        
        if all_jobs and self.db:
            self.save_to_firebase(all_jobs)
        
        if save_to_file and all_jobs:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'job_data_{timestamp}.json'
            
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(all_jobs, f, ensure_ascii=False, indent=2, default=str)
                logging.info(f"데이터 파일 저장: {filename}")
            except Exception as e:
                logging.error(f"파일 저장 실패: {e}")
        
        return all_jobs

if __name__ == "__main__":
    collector = PublicJobCollector()
    
    try:
        logging.info("공공기관 채용정보 수집 시작")
        jobs = collector.collect_data(days_filter=30)
        
        if jobs:
            logging.info(f"수집 완료: {len(jobs)}개 채용공고")
            
            recent_jobs = [j for j in jobs if j.get('reg_date') and 
                          datetime.strptime(j['reg_date'], '%Y-%m-%d') >= datetime.now() - timedelta(days=7)]
            
            logging.info(f"최근 7일 내 신규 채용공고: {len(recent_jobs)}개")
            
        else:
            logging.warning("수집된 데이터가 없습니다.")
            
    except Exception as e:
        logging.error(f"프로그램 실행 오류: {e}")
    finally:
        logging.info("프로그램 종료")
