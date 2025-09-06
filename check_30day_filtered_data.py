# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

def check_30day_filtered_data():
    """30일 이내 등록된 채용공고 데이터 확인"""
    
    # Firebase 초기화
    try:
        cred = credentials.Certificate("파이어베이스 인증/job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("[SUCCESS] Firebase 연결 성공")
    except Exception as e:
        print(f"[ERROR] Firebase 연결 실패: {e}")
        return []
    
    try:
        # 오늘 날짜와 30일 전 날짜 계산
        today = datetime.now()
        thirty_days_ago = today - timedelta(days=30)
        
        print(f"[INFO] 오늘 날짜: {today.strftime('%Y-%m-%d')}")
        print(f"[INFO] 30일 전 날짜: {thirty_days_ago.strftime('%Y-%m-%d')}")
        print(f"[INFO] 필터링 기준: 2025-08-06 이후 등록된 건만 조회")
        print("[INFO] Firebase에서 30일 이내 데이터 조회 중...")
        
        # recruitment_jobs 컬렉션에서 데이터 조회
        collection_ref = db.collection('recruitment_jobs')
        docs = collection_ref.get()
        
        # 30일 이내 데이터 필터링
        filtered_jobs = []
        cutoff_date = datetime(2025, 8, 6)  # 8월 6일
        
        for doc in docs:
            data = doc.to_dict()
            reg_date_str = data.get('reg_date', '')
            
            # 날짜 파싱
            try:
                if reg_date_str:
                    reg_date = datetime.strptime(reg_date_str, '%Y-%m-%d')
                    if reg_date >= cutoff_date:
                        job_data = {
                            'id': doc.id,
                            'title': data.get('title', ''),
                            'dept_name': data.get('dept_name', ''),
                            'reg_date': reg_date_str,
                            'end_date': data.get('end_date', ''),
                            'work_region': data.get('work_region', ''),
                            'employment_type': data.get('employment_type', '')
                        }
                        filtered_jobs.append(job_data)
            except:
                continue
        
        # 날짜순 정렬 (최신순)
        filtered_jobs.sort(key=lambda x: x['reg_date'], reverse=True)
        
        print(f"\n[RESULT] 총 {len(filtered_jobs)}건의 채용공고가 8월 6일 이후 등록되었습니다.")
        
        # 샘플 출력
        if filtered_jobs:
            print("\n[SAMPLE] 최근 등록된 채용공고 10개:")
            for i, job in enumerate(filtered_jobs[:10], 1):
                print(f"  {i}. [{job['reg_date']}] {job['title'][:40]}...")
                print(f"     기관: {job['dept_name']}, 지역: {job['work_region']}, 고용형태: {job['employment_type']}")
                print(f"     마감일: {job['end_date']}")
                print()
        
        return filtered_jobs
        
    except Exception as e:
        print(f"[ERROR] 데이터 조회 중 오류: {e}")
        return []

if __name__ == "__main__":
    print("[START] 30일 필터링 데이터 확인")
    print("=" * 70)
    filtered_data = check_30day_filtered_data()
    print("=" * 70)
    print(f"[END] 필터링 완료 - 총 {len(filtered_data)}건")