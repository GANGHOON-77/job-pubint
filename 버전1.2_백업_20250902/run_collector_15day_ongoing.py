# -*- coding: utf-8 -*-
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

from data_collector import PublicJobCollector

def collect_15day_ongoing_data():
    """15일 이내 등록, 진행중인 게시글만 수집"""
    # API 키
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    
    # Firebase 키 파일 경로
    FIREBASE_KEY_PATH = "job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json"
    
    print("=== 15일 이내 진행중 채용공고 수집기 시작 ===")
    
    # 컬렉터 초기화
    collector = PublicJobCollector(SERVICE_KEY, FIREBASE_KEY_PATH)
    
    print(f"기존 데이터: {len(collector.existing_job_ids)}건 확인됨")
    
    # 직접 API 호출하여 데이터 수집
    all_jobs = []
    
    try:
        for page in range(1, 6):  # 5페이지까지 수집 (500건)
            print(f"\n📄 페이지 {page} 처리 중...")
            
            jobs_data, total_count = collector.fetch_job_data(num_rows=100, page_no=page)
            
            if not jobs_data:
                print(f"페이지 {page}: 데이터 없음")
                continue
            
            print(f"페이지 {page}: {len(jobs_data)}건 데이터 확인")
            
            # 각 데이터 처리
            for job_data in jobs_data:
                # 진행중인 게시글만 필터링 (ongoingYn = 'Y')
                if job_data.get('ongoingYn') != 'Y':
                    continue
                
                processed_job = collector.clean_and_process_job(job_data)
                if processed_job:
                    # 15일 이내 등록 필터 (2025-08-17 이후)
                    reg_date = processed_job.get('reg_date', '')
                    if reg_date and reg_date >= '2025-08-17':
                        try:
                            if collector.db:
                                doc_id = str(processed_job['idx'])
                                
                                # Firebase에 저장
                                collector.db.collection('recruitment_jobs').document(doc_id).set(processed_job)
                                collector.add_to_cache(doc_id)
                                all_jobs.append(processed_job)
                                
                                print(f"✅ 저장: {processed_job['dept_name']} - {processed_job['title'][:40]}... ({reg_date})")
                            
                        except Exception as e:
                            print(f"❌ 저장 실패: {e}")
                    else:
                        print(f"  🔍 날짜 필터링 제외: {reg_date}")
                        
        print(f"\n=== 수집 완료! 총 {len(all_jobs)}건 저장됨 ===")
        
        # 통계 출력
        if all_jobs:
            # 날짜별 통계
            date_count = {}
            for job in all_jobs:
                date = job.get('reg_date', '알 수 없음')
                date_count[date] = date_count.get(date, 0) + 1
            
            print(f"\n📊 날짜별 저장 통계:")
            for date, count in sorted(date_count.items(), reverse=True)[:10]:
                print(f"   - {date}: {count}건")
            
            # 기관별 통계
            inst_count = {}
            for job in all_jobs:
                inst = job.get('dept_name', '알 수 없음')
                inst_count[inst] = inst_count.get(inst, 0) + 1
            
            print(f"\n🏢 기관별 저장 통계 (상위 10개):")
            for inst, count in sorted(inst_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"   - {inst}: {count}건")
                
    except Exception as e:
        print(f"수집 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = collect_15day_ongoing_data()
    if success:
        print("\n🎉 15일 이내 진행중 수집기 실행 완료")
    else:
        print("\n❌ 15일 이내 진행중 수집기 실행 실패")