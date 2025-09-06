# -*- coding: utf-8 -*-
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

def check_firebase_data_count():
    """Firebase에 저장된 채용공고 데이터 건수 확인"""
    
    # Firebase 초기화
    try:
        # 올바른 키 파일 경로 사용
        cred = credentials.Certificate("파이어베이스 인증/job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("[SUCCESS] Firebase 연결 성공")
    except Exception as e:
        print(f"[ERROR] Firebase 연결 실패: {e}")
        return
    
    try:
        # recruitment_jobs 컬렉션에서 전체 문서 수 조회
        collection_ref = db.collection('recruitment_jobs')
        
        print("[INFO] Firebase 데이터 건수 조회 중...")
        
        # 전체 문서 수 확인
        docs = collection_ref.get()
        total_count = len(docs)
        
        print(f"[RESULT] 전체 채용공고 데이터: {total_count}건")
        
        # 샘플 문서 5개 조회하여 구조 확인
        if total_count > 0:
            print("\n[SAMPLE] 최근 데이터 샘플 (최대 5개):")
            sample_docs = list(docs)[:5]
            
            for i, doc in enumerate(sample_docs, 1):
                data = doc.to_dict()
                title = data.get('title', '제목 없음')[:50]
                dept_name = data.get('dept_name', '기관명 없음')
                reg_date = data.get('reg_date', '날짜 없음')
                
                print(f"  {i}. [{doc.id}] {title}... ({dept_name}) - {reg_date}")
        
        # 컬렉션별 통계 (다른 컬렉션이 있는지 확인)
        print(f"\n[COLLECTIONS] 컬렉션별 통계:")
        collections = db.collections()
        for collection in collections:
            collection_name = collection.id
            collection_count = len(collection.get())
            print(f"  - {collection_name}: {collection_count}건")
            
    except Exception as e:
        print(f"[ERROR] 데이터 조회 중 오류: {e}")

if __name__ == "__main__":
    print("[START] Firebase 데이터 건수 확인 시작")
    print("=" * 50)
    check_firebase_data_count()
    print("=" * 50)
    print("[END] 확인 완료")