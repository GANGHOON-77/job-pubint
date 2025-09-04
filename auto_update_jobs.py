#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import requests
import json
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from data_collector import PublicJobCollector  # ✅ 수정됨: DataCollector → PublicJobCollector
import logging

def setup_logging():
    """로깅 설정"""
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
            # GitHub Actions 환경에서는 환경변수로 Firebase 키를 설정
            firebase_key = os.environ.get('FIREBASE_KEY')
            if firebase_key:
                # JSON 문자열을 파일로 저장
                with open('firebase_key.json', 'w', encoding='utf-8') as f:
                    f.write(firebase_key)
                cred = credentials.Certificate('firebase_key.json')
            else:
                # 로컬 환경에서는 키 파일 사용
                cred = credentials.Certificate('job-pubint-firebase-adminsdk-fbsvc-8a7f28a86e.json')
            
            firebase_admin.initialize_app(cred)
            logging.info("Firebase 초기화 성공")
        
        return firestore.client()
    except Exception as e:
        logging.error(f"Firebase 초기화 실패: {e}")
        return None

def collect_new_jobs():
    """새로운 채용공고 수집"""
    try:
        collector = PublicJobCollector()  # ✅ 수정됨: DataCollector() → PublicJobCollector()
        # 최근 1일 데이터만 수집 (신규 확인용)
        new_jobs = collector.collect_data(days_ago=1, save_to_file=False)
        logging.info(f"API에서 {len(new_jobs)}개 채용공고 수집")
        return new_jobs
    except Exception as e:
        logging.error(f"새 데이터 수집 실패: {e}")
        return []

def save_new_jobs_to_firebase(db, new_jobs):
    """새로운 채용공고를 Firebase에 저장"""
    if not new_jobs:
        logging.info("저장할 새로운 채용공고가 없습니다")
        return 0
    
    saved_count = 0
    collection_ref = db.collection('recruitment_jobs')
    
    for job in new_jobs:
        try:
            # 고유 ID로 중복 확인
            job_id = job.get('id') or job.get('pblntfPblancId', 'unknown')
            
            # 이미 존재하는지 확인
            existing_doc = collection_ref.where('pblntfPblancId', '==', job_id).limit(1).get()
            
            if not existing_doc:
                # 새로운 문서 추가
                job_data = {
                    **job,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now(),
                    'status': 'active'
                }
                collection_ref.add(job_data)
                saved_count += 1
                logging.info(f"새 채용공고 저장: {job.get('instNm', '기관명 없음')} - {job.get('ncsCdNmLst', '제목 없음')}")
            
        except Exception as e:
            logging.error(f"채용공고 저장 실패: {e}")
    
    logging.info(f"총 {saved_count}개 새로운 채용공고 저장 완료")
    return saved_count

def delete_old_jobs(db):
    """15일 이상된 오래된 채용공고 삭제 (단, 마감일이 지나지 않은 경우 유지)"""
    try:
        collection_ref = db.collection('recruitment_jobs')
        cutoff_date = datetime.now() - timedelta(days=15)
        
        # 15일 이전에 생성된 문서들 조회
        old_docs = collection_ref.where('created_at', '<', cutoff_date).get()
        
        deleted_count = 0
        kept_count = 0
        
        for doc in old_docs:
            doc_data = doc.to_dict()
            
            # 마감일 확인
            end_date_str = doc_data.get('pbancEndYmd') or doc_data.get('rcritEndDt')
            
            if end_date_str:
                try:
                    # 날짜 형식 변환 (YYYYMMDD 또는 YYYY-MM-DD)
                    if len(end_date_str) == 8 and end_date_str.isdigit():
                        end_date = datetime.strptime(end_date_str, '%Y%m%d')
                    else:
                        end_date = datetime.strptime(end_date_str[:10], '%Y-%m-%d')
                    
                    # 마감일이 지나지 않았으면 유지
                    if end_date > datetime.now():
                        kept_count += 1
                        continue
                        
                except ValueError:
                    pass  # 날짜 파싱 실패 시 삭제 진행
            
            # 오래된 문서 삭제
            doc.reference.delete()
            deleted_count += 1
        
        logging.info(f"15일 이상된 채용공고 {deleted_count}개 삭제, {kept_count}개 유지 (마감일 미경과)")
        return deleted_count
        
    except Exception as e:
        logging.error(f"오래된 데이터 삭제 실패: {e}")
        return 0

def get_current_stats(db):
    """현재 채용공고 통계 조회"""
    try:
        collection_ref = db.collection('recruitment_jobs')
        total_count = len(collection_ref.get())
        
        # 활성 상태 문서 수
        active_count = len(collection_ref.where('status', '==', 'active').get())
        
        return {
            'total': total_count,
            'active': active_count
        }
    except Exception as e:
        logging.error(f"통계 조회 실패: {e}")
        return {'total': 0, 'active': 0}

def main():
    """메인 실행 함수"""
    setup_logging()
    logging.info("=== 자동 채용공고 업데이트 시작 ===")
    
    # Firebase 초기화
    db = initialize_firebase()
    if not db:
        logging.error("Firebase 연결 실패로 종료")
        sys.exit(1)
    
    try:
        # 1. 새로운 채용공고 수집
        logging.info("1. 새로운 채용공고 수집 시작")
        new_jobs = collect_new_jobs()
        
        # 2. Firebase에 새 데이터 저장
        logging.info("2. Firebase에 새 데이터 저장 시작")
        saved_count = save_new_jobs_to_firebase(db, new_jobs)
        
        # 3. 오래된 데이터 삭제
        logging.info("3. 오래된 데이터 삭제 시작")
        deleted_count = delete_old_jobs(db)
        
        # 4. 현재 통계 확인
        stats = get_current_stats(db)
        
        # 결과 요약
        logging.info("=== 업데이트 완료 ===")
        logging.info(f"수집된 새 채용공고: {len(new_jobs)}개")
        logging.info(f"저장된 새 채용공고: {saved_count}개")
        logging.info(f"삭제된 오래된 채용공고: {deleted_count}개")
        logging.info(f"현재 총 채용공고 수: {stats['total']}개 (활성: {stats['active']}개)")
        
        # 임시 파일 정리
        if os.path.exists('firebase_key.json'):
            os.remove('firebase_key.json')
            
    except Exception as e:
        logging.error(f"실행 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
