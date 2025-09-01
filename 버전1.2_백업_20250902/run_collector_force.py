# -*- coding: utf-8 -*-
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

from data_collector import PublicJobCollector

def force_collect_recent_data():
    """최근 30일 데이터 강제 수집"""
    # API 키
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    
    # Firebase 키 파일 경로
    FIREBASE_KEY_PATH = "job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json"
    
    print("=== 공공기관 채용정보 강제 수집기 시작 ===")
    
    # 컬렉터 초기화
    collector = PublicJobCollector(SERVICE_KEY, FIREBASE_KEY_PATH)
    
    print(f"기존 데이터: {len(collector.existing_job_ids)}건 확인됨")
    
    # 직접 API 호출하여 데이터 수집
    all_jobs = []
    
    try:
        for page in range(1, 6):  # 5페이지까지 수집
            print(f"\n📄 페이지 {page} 처리 중...")
            
            jobs_data, total_count = collector.fetch_job_data(num_rows=100, page_no=page)
            
            if not jobs_data:
                print(f"페이지 {page}: 데이터 없음")
                continue
            
            print(f"페이지 {page}: {len(jobs_data)}건 데이터 확인")
            
            # 각 데이터 처리
            for job_data in jobs_data:
                processed_job = collector.clean_and_process_job(job_data)
                if processed_job:
                    # Firebase에 저장
                    try:
                        if collector.db:
                            doc_id = str(processed_job['idx'])
                            
                            # 중복 체크 없이 무조건 저장 (덮어쓰기)
                            collector.db.collection('recruitment_jobs').document(doc_id).set(processed_job)
                            collector.add_to_cache(doc_id)
                            all_jobs.append(processed_job)
                            
                            print(f"✅ 저장 완료: {processed_job['inst_nm']} - {processed_job['recruit_title'][:50]}")
                        
                    except Exception as e:
                        print(f"❌ 저장 실패: {e}")
                        
        print(f"\n=== 수집 완료! 총 {len(all_jobs)}건 저장됨 ===")
        
        # 통계 출력
        if all_jobs:
            # 기관별 통계
            inst_count = {}
            for job in all_jobs:
                inst = job.get('inst_nm', '알 수 없음')
                inst_count[inst] = inst_count.get(inst, 0) + 1
            
            print(f"\n📊 기관별 저장 통계:")
            for inst, count in sorted(inst_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"   - {inst}: {count}건")
                
            # 첨부파일 통계
            attachment_count = sum(1 for job in all_jobs if job.get('attachments'))
            print(f"\n📎 첨부파일 정보 포함: {attachment_count}건 ({attachment_count/len(all_jobs)*100:.1f}%)")
                
    except Exception as e:
        print(f"수집 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = force_collect_recent_data()
    if success:
        print("\n🎉 강제 수집기 실행 완료")
    else:
        print("\n❌ 강제 수집기 실행 실패")