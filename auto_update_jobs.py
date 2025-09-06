#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import requests
import json
import logging
import time
import random
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_update_jobs.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

class FirebaseManager:
    """Firebase 관리 클래스"""
    
    def __init__(self):
        self.db = None
        self.init_firebase()
    
    def init_firebase(self):
        """Firebase 초기화"""
        try:
            if not firebase_admin._apps:
                firebase_key = os.environ.get('FIREBASE_KEY')
                if firebase_key:
                    with open('firebase_key.json', 'w', encoding='utf-8') as f:
                        f.write(firebase_key)
                    cred = credentials.Certificate('firebase_key.json')
                else:
                    cred = credentials.Certificate('파이어베이스 인증/job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json')
                
                firebase_admin.initialize_app(cred)
                logging.info("Firebase 초기화 성공")
            
            self.db = firestore.client()
        except Exception as e:
            logging.error(f"Firebase 초기화 실패: {e}")
            self.db = None
    
    def get_existing_job_ids(self):
        """Firebase에 저장된 기존 게시글 ID 목록 가져오기"""
        if not self.db:
            return set()
        
        try:
            jobs_ref = self.db.collection('recruitment_jobs')
            docs = jobs_ref.stream()
            existing_ids = {doc.id for doc in docs}
            logging.info(f"기존 저장된 게시글: {len(existing_ids)}개")
            return existing_ids
        except Exception as e:
            logging.error(f"기존 게시글 ID 조회 실패: {e}")
            return set()
    
    def save_new_job(self, job_data):
        """신규 게시글 Firebase에 저장"""
        if not self.db or not job_data or not job_data.get('idx'):
            return False
        
        try:
            doc_ref = self.db.collection('recruitment_jobs').document(job_data['idx'])
            job_data['created_at'] = datetime.now().isoformat()
            job_data['updated_at'] = datetime.now().isoformat()
            job_data['status'] = 'active'
            
            doc_ref.set(job_data)
            logging.info(f"신규 게시글 저장 성공: {job_data.get('title', '')} (idx: {job_data['idx']})")
            return True
        except Exception as e:
            logging.error(f"Firebase 저장 실패: {e}, idx: {job_data.get('idx')}")
            return False
    
    def cleanup_old_jobs(self):
        """30일 이상 된 게시글 삭제 (매일 0시 서울시간)"""
        if not self.db:
            return 0
        
        # 서울시간 체크
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        
        if now_kst.hour != 0:
            logging.info(f"현재 서울시간: {now_kst.hour}시 - 0시가 아니므로 정리 작업 건너뜀")
            return 0
        
        try:
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            jobs_ref = self.db.collection('recruitment_jobs')
            query = jobs_ref.where('reg_date', '<', cutoff_date)
            docs = list(query.stream())
            
            deleted_count = 0
            batch = self.db.batch()
            batch_count = 0
            
            for doc in docs:
                job_data = doc.to_dict()
                logging.info(f"30일 경과 게시글 삭제: {job_data.get('title', '')} (등록일: {job_data.get('reg_date')})")
                
                batch.delete(doc.reference)
                batch_count += 1
                deleted_count += 1
                
                if batch_count >= 500:
                    batch.commit()
                    batch = self.db.batch()
                    batch_count = 0
            
            if batch_count > 0:
                batch.commit()
            
            logging.info(f"오래된 게시글 정리 완료: {deleted_count}개 삭제")
            return deleted_count
            
        except Exception as e:
            logging.error(f"게시글 정리 실패: {e}")
            return 0


class JobAPIClient:
    """공공데이터 API 클라이언트"""
    
    def __init__(self):
        self.service_key = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
        self.base_url = "http://apis.data.go.kr/1051000/recruitment/list"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_recent_jobs(self, max_pages=3):
        """최신 게시글 목록 가져오기 (API 한도 고려하여 최대 3페이지)"""
        all_jobs = []
        
        for page in range(1, max_pages + 1):
            try:
                params = {
                    'serviceKey': self.service_key,
                    'numOfRows': '100',
                    'pageNo': str(page),
                    'returnType': 'JSON'
                }
                
                url = f"{self.base_url}?{urlencode(params)}"
                logging.info(f"API 요청: 페이지 {page}")
                
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get('resultCode') == 200:
                    result = data.get('result', [])
                    if result:
                        all_jobs.extend(result)
                        logging.info(f"페이지 {page}: {len(result)}개 수집")
                    else:
                        logging.info(f"페이지 {page}: 데이터 없음")
                        break
                else:
                    logging.error(f"API 오류: {data.get('resultMsg')}")
                    break
                
                # API 부하 방지
                time.sleep(random.uniform(0.5, 1.0))
                
            except Exception as e:
                logging.error(f"API 요청 실패 (페이지 {page}): {e}")
                break
        
        logging.info(f"총 {len(all_jobs)}개 게시글 수집 완료")
        return all_jobs
    
    def parse_date(self, date_str):
        """날짜 파싱 (data_collector.py와 동일)"""
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
        """텍스트 정제 (data_collector.py와 동일)"""
        if not text or text == 'null':
            return ""
        
        text = str(text).strip()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s가-힣\(\)\[\].,;:\-\+\/\%\&\@\!\?\'\"]', '', text)
        return text[:500]
    
    def process_job_data(self, job):
        """게시글 데이터 처리 (data_collector.py와 동일한 스키마)"""
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
            
            # 채용인원 정수 변환
            try:
                processed_job['recruit_count'] = int(processed_job['recruit_count']) if processed_job['recruit_count'] else 0
            except (ValueError, TypeError):
                processed_job['recruit_count'] = 0
            
            return processed_job
            
        except Exception as e:
            logging.error(f"데이터 처리 오류: {e}, job: {job}")
            return None


class JobUpdateManager:
    """채용공고 업데이트 관리 클래스"""
    
    def __init__(self):
        self.firebase_manager = FirebaseManager()
        self.api_client = JobAPIClient()
    
    def check_duplicates(self, api_jobs, existing_ids):
        """중복 체크 및 신규 게시글 필터링"""
        new_jobs = []
        
        for job in api_jobs:
            job_id = str(job.get('recrutPblntSn', ''))
            
            if job_id and job_id not in existing_ids:
                processed_job = self.api_client.process_job_data(job)
                if processed_job:
                    new_jobs.append(processed_job)
        
        logging.info(f"중복 체크 완료: 신규 게시글 {len(new_jobs)}개 발견")
        return new_jobs
    
    def process_new_jobs(self):
        """신규 게시글 처리 메인 로직"""
        try:
            # 1. 기존 게시글 ID 목록 가져오기
            existing_ids = self.firebase_manager.get_existing_job_ids()
            
            # 2. API에서 최신 게시글 가져오기
            api_jobs = self.api_client.fetch_recent_jobs(max_pages=3)
            
            if not api_jobs:
                logging.info("API에서 가져온 데이터가 없습니다.")
                return 0
            
            # 3. 중복 체크 및 신규 게시글 필터링
            new_jobs = self.check_duplicates(api_jobs, existing_ids)
            
            if not new_jobs:
                logging.info("신규 게시글이 없습니다.")
                return 0
            
            # 4. 신규 게시글 Firebase에 저장
            saved_count = 0
            for job in new_jobs:
                if self.firebase_manager.save_new_job(job):
                    saved_count += 1
                    # 저장 간격 조정
                    time.sleep(0.1)
            
            logging.info(f"신규 게시글 처리 완료: {saved_count}개 저장")
            return saved_count
            
        except Exception as e:
            logging.error(f"신규 게시글 처리 중 오류: {e}")
            return 0
    
    def daily_cleanup(self):
        """일일 정리 작업 (서울시간 0시)"""
        return self.firebase_manager.cleanup_old_jobs()
    
    def run_update_cycle(self):
        """5분 주기 업데이트 실행"""
        logging.info("=== 채용공고 업데이트 사이클 시작 ===")
        start_time = datetime.now()
        
        try:
            # 1. 신규 게시글 처리
            new_count = self.process_new_jobs()
            
            # 2. 일일 정리 작업 (0시에만)
            deleted_count = self.daily_cleanup()
            
            # 실행 시간 계산
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            logging.info("=== 업데이트 사이클 완료 ===")
            logging.info(f"신규 게시글: {new_count}개")
            logging.info(f"삭제된 게시글: {deleted_count}개")
            logging.info(f"실행 시간: {execution_time:.2f}초")
            
            return {
                'new_jobs': new_count,
                'deleted_jobs': deleted_count,
                'execution_time': execution_time
            }
            
        except Exception as e:
            logging.error(f"업데이트 사이클 오류: {e}")
            return None


def main():
    """메인 실행 함수"""
    try:
        logging.info("신규 채용공고 수집 시스템 시작")
        
        # JobUpdateManager 초기화 및 실행
        update_manager = JobUpdateManager()
        result = update_manager.run_update_cycle()
        
        if result:
            logging.info("프로그램 정상 종료")
        else:
            logging.error("프로그램 오류로 종료")
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"메인 프로그램 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
