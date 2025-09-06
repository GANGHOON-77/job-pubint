#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import requests
import json
from datetime import datetime, timedelta
import pytz
import firebase_admin
from firebase_admin import credentials, firestore
from data_collector import PublicJobCollector
import logging

def setup_logging():
    """로깅 설정"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('auto_update_jobs.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def initialize_firebase():
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
        
        return firestore.client()
    except Exception as e:
        logging.error(f"Firebase 초기화 실패: {e}")
        return None

def collect_new_jobs():
    """새로운 채용공고 수집 - days_ago 제한 제거"""
    try:
        collector = PublicJobCollector()
        # 수정: days_ago 파라미터 완전 제거
        new_jobs = collector.collect_data(save_to_file=False)
        
        logging.info(f"API에서 {len(new_jobs)}개 채용공고 수집")
        return new_jobs
    except Exception as e:
        logging.error(f"새 채용공고 수집 실패: {e}")
        return []

def save_new_jobs_to_firebase(jobs):
    """새로운 채용공고를 Firebase에 저장"""
    if not jobs:
        logging.info("저장할 새 채용공고가 없습니다.")
        return 0
    
    db = initialize_firebase()
    if not db:
        logging.error("Firebase 연결 실패")
        return 0
    
    saved_count = 0
    updated_count = 0
    
    try:
        for job in jobs:
            if not job or not job.get('idx'):
                continue
            
            doc_ref = db.collection('jobs').document(job['idx'])
            
            try:
                existing_doc = doc_ref.get()
                
                if existing_doc.exists:
                    job['updated_at'] = datetime.now().isoformat()
                    doc_ref.update(job)
                    updated_count += 1
                    logging.info(f"채용공고 업데이트: {job.get('title', '')} (idx: {job['idx']})")
                else:
                    job['created_at'] = datetime.now().isoformat()
                    job['updated_at'] = datetime.now().isoformat()
                    job['status'] = 'active'
                    doc_ref.set(job)
                    saved_count += 1
                    logging.info(f"새 채용공고 저장: {job.get('title', '')} (idx: {job['idx']})")
                    
            except Exception as e:
                logging.error(f"문서 저장/업데이트 실패: {e}, idx: {job.get('idx')}")
                continue
        
        logging.info(f"Firebase 저장 완료: 신규 {saved_count}개, 업데이트 {updated_count}개")
        return saved_count + updated_count
        
    except Exception as e:
        logging.error(f"Firebase 저장 중 오류: {e}")
        return 0

def delete_old_jobs():
    """30일 이상 된 채용공고 삭제 - 매일 0시에만 실행"""
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    
    if now_kst.hour != 0:
        logging.info(f"현재 시간: {now_kst.hour}시 - 0시가 아니므로 삭제 작업 건너뜀")
        return 0
    
    db = initialize_firebase()
    if not db:
        logging.error("Firebase 연결 실패")
        return 0
    
    try:
        cutoff_date = datetime.now() - timedelta(days=30)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        jobs_ref = db.collection('jobs')
        query = jobs_ref.where('reg_date', '<', cutoff_str)
        docs = query.stream()
        
        deleted_count = 0
        batch = db.batch()
        batch_count = 0
        
        for doc in docs:
            job_data = doc.to_dict()
            end_date_str = job_data.get('end_date')
            
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                    if end_date < datetime.now():
                        batch.delete(doc.reference)
                        batch_count += 1
                        deleted_count += 1
                        logging.info(f"만료된 채용공고 삭제 예정: {job_data.get('title', '')} (idx: {doc.id})")
                        
                        if batch_count >= 500:
                            batch.commit()
                            batch = db.batch()
                            batch_count = 0
                            
                except ValueError:
                    logging.warning(f"잘못된 날짜 형식: {end_date_str}, idx: {doc.id}")
                    continue
        
        if batch_count > 0:
            batch.commit()
        
        logging.info(f"오래된 채용공고 삭제 완료: {deleted_count}개")
        return deleted_count
        
    except Exception as e:
        logging.error(f"오래된 채용공고 삭제 실패: {e}")
        return 0

def generate_statistics():
    """통계 생성 및 로깅"""
    try:
        db = initialize_firebase()
        if not db:
            return
        
        jobs_ref = db.collection('jobs')
        all_jobs = list(jobs_ref.stream())
        
        total_count = len(all_jobs)
        
        today = datetime.now().strftime('%Y-%m-%d')
        today_jobs = [job for job in all_jobs if job.to_dict().get('reg_date') == today]
        
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        week_jobs = [job for job in all_jobs if job.to_dict().get('reg_date') >= week_ago]
        
        logging.info(f"=== 채용공고 통계 ===")
        logging.info(f"전체 채용공고: {total_count}개")
        logging.info(f"오늘 등록: {len(today_jobs)}개")
        logging.info(f"최근 7일간: {len(week_jobs)}개")
        
    except Exception as e:
        logging.error(f"통계 생성 실패: {e}")

def main():
    """메인 실행 함수"""
    setup_logging()
    
    try:
        logging.info("=== 자동 채용공고 업데이트 시작 ===")
        start_time = datetime.now()
        
        # 1. 새로운 채용공고 수집
        logging.info("1. 새 채용공고 수집 중...")
        new_jobs = collect_new_jobs()
        
        # 2. Firebase에 저장
        logging.info("2. Firebase에 저장 중...")
        saved_count = save_new_jobs_to_firebase(new_jobs)
        
        # 3. 오래된 채용공고 삭제 (0시에만)
        logging.info("3. 오래된 채용공고 정리 중...")
        deleted_count = delete_old_jobs()
        
        # 4. 통계 생성
        logging.info("4. 통계 생성 중...")
        generate_statistics()
        
        # 실행 시간 계산
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        logging.info(f"=== 업데이트 완료 ===")
        logging.info(f"처리된 채용공고: {saved_count}개")
        logging.info(f"삭제된 채용공고: {deleted_count}개")
        logging.info(f"실행 시간: {execution_time:.2f}초")
        
    except Exception as e:
        logging.error(f"메인 프로세스 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
