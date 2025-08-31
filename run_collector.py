#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
공공기관 채용정보 데이터 수집 실행 스크립트
중복 제거 및 최적화된 수집 기능 포함
"""

import sys
import os
from datetime import datetime

# 현재 디렉토리를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_collector import PublicJobCollector

def main():
    print("=" * 60)
    print("🏢 공공기관 채용정보 수집 시스템")
    print(f"⏰ 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 설정
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    FIREBASE_KEY_PATH = "info-gov-firebase-adminsdk-9o52l-f6b59e8ae8.json"
    
    try:
        # 컬렉터 초기화
        print("🔧 시스템 초기화 중...")
        collector = PublicJobCollector(SERVICE_KEY, FIREBASE_KEY_PATH)
        
        if not collector.db:
            print("❌ Firebase 연결 실패. 종료합니다.")
            return
        
        # 사전 통계 확인
        print("\n📊 수집 전 상태 확인:")
        pre_stats = collector.get_collection_stats()
        if pre_stats:
            print(f"   - 기존 전체 문서: {pre_stats['total']}건")
            print(f"   - 기존 활성 문서: {pre_stats['active']}건")
            print(f"   - 오늘 업데이트: {pre_stats['today_updated']}건")
        
        print(f"   - 중복 체크 캐시: {len(collector.existing_job_ids)}건")
        
        # 사용자 확인
        print("\n" + "=" * 60)
        response = input("🚀 데이터 수집을 시작하시겠습니까? (y/N): ").strip().lower()
        
        if response != 'y':
            print("❌ 사용자가 취소했습니다.")
            return
        
        # 데이터 수집 실행
        print("\n🚀 데이터 수집 시작...")
        start_time = datetime.now()
        
        # 최대 10페이지까지 수집 (상황에 따라 조정)
        collected_jobs = collector.collect_and_save(max_pages=10)
        
        end_time = datetime.now()
        elapsed_time = end_time - start_time
        
        # 수집 후 통계
        print("\n📊 수집 완료 후 상태:")
        post_stats = collector.get_collection_stats()
        if post_stats and pre_stats:
            new_total = post_stats['total'] - pre_stats['total']
            new_today = post_stats['today_updated'] - pre_stats['today_updated']
            
            print(f"   - 현재 전체 문서: {post_stats['total']}건 (+{new_total})")
            print(f"   - 현재 활성 문서: {post_stats['active']}건")
            print(f"   - 오늘 업데이트: {post_stats['today_updated']}건 (+{new_today})")
        
        # 수집 결과 요약
        print("\n" + "=" * 60)
        print("🎉 수집 작업 완료!")
        print(f"⏱️  소요 시간: {elapsed_time}")
        print(f"📝 처리된 데이터: {len(collected_jobs)}건")
        
        if len(collected_jobs) > 0:
            print("\n📋 수집된 최신 공고 (상위 5개):")
            for i, job in enumerate(collected_jobs[:5], 1):
                title = job.get('title', 'No Title')[:40]
                dept = job.get('dept_name', 'No Dept')[:20]
                reg_date = job.get('reg_date', 'No Date')
                print(f"   {i}. {title} | {dept} | {reg_date}")
        
        print("\n✅ 웹페이지(index.html)에서 최신 데이터를 확인하세요!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n⚠️ 사용자가 중단했습니다.")
    except Exception as e:
        print(f"\n❌ 실행 중 오류 발생: {e}")
        print("📝 자세한 로그는 콘솔을 확인하세요.")
    
    finally:
        print(f"\n⏰ 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()