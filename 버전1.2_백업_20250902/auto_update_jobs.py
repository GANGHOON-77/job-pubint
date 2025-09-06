# -*- coding: utf-8 -*-
"""
GitHub Actions용 자동 채용공고 업데이트 스크립트
5분마다 실행되어 신규 게시글 수집 및 15일 초과 게시글 삭제
"""
import sys
import os
import requests
import json
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from data_collector import DataCollector
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('update_log.txt', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def initialize_firebase():
    """Firebase 초기화"""
    try:
        if not firebase_admin._apps:
            # GitHub Actions 환경에서는 키 파일이 생성됨
            key_file = "job-pubint-firebase-adminsdk-fbsvc-8a7f28a86e.json"
            if os.path.exists(key_file):
                cred = credentials.Certificate(key_file)
                firebase_admin.initialize_app(cred)
                logging.info("Firebase 초기화 성공")
            else:
                raise Exception("Firebase 키 파일을 찾을 수 없습니다")
        
        return firestore.client()
    except Exception as e:
        logging.error(f"Firebase 초기화 실패: {e}")
        return None

def get_existing_job_ids(db):
    """기존 Firebase에 저장된 채용공고 ID 목록 가져오기"""
    try:
        docs = db.collection('recruitment_jobs').stream()
        existing_ids = set()
        for doc in docs:
            existing_ids.add(doc.id)
        logging.info(f"기존 채용공고 {len(existing_ids)}개 확인")
        return existing_ids
    except Exception as e:
        logging.error(f"기존 데이터 조회 실패: {e}")
        return set()

def collect_new_jobs():
    """새로운 채용공고 수집"""
    try:
        collector = DataCollector()
        # 최근 1일 데이터만 수집 (신규 확인용)
        new_jobs = collector.collect_data(days_ago=1, save_to_file=False)
        logging.info(f"API에서 {len(new_jobs)}개 채용공고 수집")
        return new_jobs
    except Exception as e:
        logging.error(f"새 데이터 수집 실패: {e}")
        return []

def save_new_jobs_to_firebase(db, new_jobs, existing_ids):
    """신규 채용공고만 Firebase에 저장"""
    new_count = 0
    
    for job in new_jobs:
        job_id = job['idx']
        
        if job_id not in existing_ids:
            try:
                # 신규 채용공고 저장
                doc_ref = db.collection('recruitment_jobs').document(job_id)
                job['created_at'] = datetime.now()
                job['updated_at'] = datetime.now()
                job['status'] = 'active'
                
                doc_ref.set(job)
                new_count += 1
                logging.info(f"신규 채용공고 저장: {job_id} - {job.get('title', 'N/A')}")
                
            except Exception as e:
                logging.error(f"채용공고 저장 실패 ({job_id}): {e}")
    
    logging.info(f"총 {new_count}개의 신규 채용공고 저장 완료")
    return new_count

def delete_old_jobs(db, days_threshold=15):
    """15일 이상 된 채용공고 삭제"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        # 15일 전 데이터 조회
        old_jobs_query = db.collection('recruitment_jobs').where(
            'created_at', '<', cutoff_date
        ).stream()
        
        deleted_count = 0
        for doc in old_jobs_query:
            try:
                doc.reference.delete()
                deleted_count += 1
                logging.info(f"오래된 채용공고 삭제: {doc.id}")
            except Exception as e:
                logging.error(f"채용공고 삭제 실패 ({doc.id}): {e}")
        
        logging.info(f"총 {deleted_count}개의 오래된 채용공고 삭제 완료")
        return deleted_count
        
    except Exception as e:
        logging.error(f"오래된 데이터 삭제 실패: {e}")
        return 0

def get_current_stats(db):
    """현재 통계 정보 조회"""
    try:
        total_docs = list(db.collection('recruitment_jobs').stream())
        total_count = len(total_docs)
        
        # 오늘 등록된 공고 수
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        new_today = db.collection('recruitment_jobs').where(
            'created_at', '>=', today_start
        ).stream()
        new_count = len(list(new_today))
        
        logging.info(f"현재 총 {total_count}개 채용공고, 오늘 신규 {new_count}개")
        return total_count, new_count
        
    except Exception as e:
        logging.error(f"통계 조회 실패: {e}")
        return 0, 0

def main():
    """메인 실행 함수"""
    logging.info("=== 자동 채용공고 업데이트 시작 ===")
    
    # Firebase 초기화
    db = initialize_firebase()
    if not db:
        logging.error("Firebase 연결 실패로 종료")
        return
    
    try:
        # 1. 기존 데이터 확인
        existing_ids = get_existing_job_ids(db)
        
        # 2. 새로운 채용공고 수집
        new_jobs = collect_new_jobs()
        if not new_jobs:
            logging.info("수집된 새 데이터가 없습니다")
        
        # 3. 신규 채용공고 저장
        new_saved = save_new_jobs_to_firebase(db, new_jobs, existing_ids)
        
        # 4. 오래된 채용공고 삭제
        deleted_count = delete_old_jobs(db, days_threshold=15)
        
        # 5. 현재 상태 확인
        total_count, today_new = get_current_stats(db)
        
        # 6. 업데이트 요약
        logging.info("=== 업데이트 완료 ===")
        logging.info(f"신규 저장: {new_saved}개")
        logging.info(f"오래된 삭제: {deleted_count}개")
        logging.info(f"현재 총 채용공고: {total_count}개")
        logging.info(f"오늘 신규 채용공고: {today_new}개")
        
    except Exception as e:
        logging.error(f"업데이트 과정에서 오류 발생: {e}")
    
    logging.info("=== 자동 채용공고 업데이트 종료 ===")

if __name__ == "__main__":
    main()