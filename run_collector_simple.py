# -*- coding: utf-8 -*-
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

from data_collector import PublicJobCollector

def main():
    # API 키
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    
    # Firebase 키 파일 경로
    FIREBASE_KEY_PATH = "info-gov-firebase-adminsdk-9o52l-f6b59e8ae8.json"
    
    print("=== 공공기관 채용정보 수집기 시작 ===")
    
    # 컬렉터 초기화
    collector = PublicJobCollector(SERVICE_KEY, FIREBASE_KEY_PATH)
    
    print(f"기존 데이터: {len(collector.existing_job_ids)}건 확인됨")
    
    # 데이터 수집 및 저장 (3페이지만 테스트)
    try:
        jobs = collector.collect_and_save(max_pages=3)
        print(f"\n=== 수집 완료! 총 {len(jobs)}건 처리됨 ===")
        
        if jobs:
            # 첨부파일 정보가 있는 건수 확인
            attachment_count = sum(1 for job in jobs if job.get('attachments'))
            print(f"첨부파일 정보 포함: {attachment_count}건")
            
    except Exception as e:
        print(f"수집 중 오류 발생: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("수집기 실행 완료")
    else:
        print("수집기 실행 실패")