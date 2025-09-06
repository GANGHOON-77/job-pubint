# -*- coding: utf-8 -*-
import sys
import os
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding='utf-8')

from data_collector import PublicJobCollector

def collect_30day_optimized_data():
    """30일 이내 등록, 진행중인 게시글만 최적화 수집 (중복 스킵 + 첨부파일 포함)"""
    # API 키
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    
    # Firebase 키 파일 경로
    FIREBASE_KEY_PATH = "job-pubint-firebase-adminsdk-fbsvc-8a7f28a86e.json"
    
    print("=== 30일 이내 진행중 채용공고 최적화 수집기 시작 ===")
    print("✨ 개선사항: 중복 스킵 + 첨부파일 포함 + API 호출 최소화")
    
    # 30일 전 날짜 계산
    cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    print(f"🗓️  수집 기준일: {cutoff_date} 이후 등록")
    
    # 컬렉터 초기화
    collector = PublicJobCollector(SERVICE_KEY, FIREBASE_KEY_PATH)
    
    print(f"📊 기존 데이터: {len(collector.existing_job_ids)}건 확인됨 (중복 체크 준비)")
    
    # 수집 통계
    stats = {
        'total_processed': 0,
        'new_saved': 0,
        'duplicates_skipped': 0,
        'attachment_included': 0,
        'api_calls': 0
    }
    
    all_jobs = []
    
    try:
        # API 호출 최적화: 페이지별 처리
        for page in range(1, 11):  # 10페이지까지 수집 (1000건)
            print(f"\n📄 페이지 {page} 처리 중...")
            
            # API 호출
            stats['api_calls'] += 1
            jobs_data, total_count = collector.fetch_job_data(num_rows=100, page_no=page)
            
            if not jobs_data:
                print(f"   ❌ 페이지 {page}: 데이터 없음 - 수집 종료")
                break
            
            print(f"   📦 페이지 {page}: {len(jobs_data)}건 API 데이터 수신")
            
            page_new = 0
            page_duplicates = 0
            page_filtered = 0
            
            # 각 데이터 처리
            for job_data in jobs_data:
                stats['total_processed'] += 1
                
                # 1단계: 진행중인 게시글만 필터링 (ongoingYn = 'Y')
                if job_data.get('ongoingYn') != 'Y':
                    page_filtered += 1
                    continue
                
                # 2단계: 중복 체크 (API 호출 최소화)
                job_idx = str(job_data.get('recrutPblntSn', ''))
                if collector.is_job_exists(job_idx):
                    page_duplicates += 1
                    stats['duplicates_skipped'] += 1
                    continue
                
                # 3단계: 데이터 정제 및 처리
                processed_job = collector.clean_and_process_job(job_data)
                if not processed_job:
                    continue
                
                # 4단계: 30일 이내 등록 필터
                reg_date = processed_job.get('reg_date', '')
                if not reg_date or reg_date < cutoff_date:
                    continue
                
                # 5단계: 첨부파일 정보 포함 확인
                attachments = processed_job.get('attachments', {})
                has_attachments = bool(attachments and (
                    attachments.get('announcement') or 
                    attachments.get('application') or 
                    attachments.get('job_description') or 
                    attachments.get('others')
                ))
                
                if has_attachments:
                    stats['attachment_included'] += 1
                
                # 6단계: Firebase 저장 (신규만)
                try:
                    if collector.db:
                        doc_id = str(processed_job['idx'])
                        
                        # Firebase에 저장
                        collector.db.collection('recruitment_jobs').document(doc_id).set(processed_job)
                        collector.add_to_cache(doc_id)  # 캐시 업데이트
                        all_jobs.append(processed_job)
                        
                        page_new += 1
                        stats['new_saved'] += 1
                        
                        attachment_status = "📎" if has_attachments else "📋"
                        print(f"   ✅ 저장: {processed_job['dept_name'][:15]} - {processed_job['title'][:30]}... ({reg_date}) {attachment_status}")
                    
                except Exception as e:
                    print(f"   ❌ 저장 실패: {e}")
            
            # 페이지별 요약
            print(f"   📊 페이지 {page} 요약: 신규 {page_new}건 | 중복 {page_duplicates}건 | 필터제외 {page_filtered}건")
            
            # 데이터가 없으면 종료 (최적화)
            if page_new == 0 and page_duplicates == 0:
                print(f"   🔚 새로운 데이터가 없어 수집 종료")
                break
        
        # 최종 결과 출력
        print(f"\n{'='*60}")
        print(f"🎯 최종 수집 결과")
        print(f"{'='*60}")
        print(f"📋 총 처리된 데이터: {stats['total_processed']:,}건")
        print(f"✅ 신규 저장: {stats['new_saved']:,}건")
        print(f"⏭️  중복 스킵: {stats['duplicates_skipped']:,}건")
        print(f"📎 첨부파일 포함: {stats['attachment_included']:,}건")
        print(f"🔄 API 호출 수: {stats['api_calls']:,}회")
        
        if stats['new_saved'] > 0:
            print(f"📈 첨부파일 포함율: {(stats['attachment_included']/stats['new_saved']*100):.1f}%")
        
        # 상세 통계
        if all_jobs:
            print(f"\n📊 상세 분석:")
            
            # 날짜별 통계
            date_count = {}
            for job in all_jobs:
                date = job.get('reg_date', '알 수 없음')
                date_count[date] = date_count.get(date, 0) + 1
            
            print(f"\n🗓️  날짜별 신규 데이터 (최근 10일):")
            for date, count in sorted(date_count.items(), reverse=True)[:10]:
                print(f"   - {date}: {count}건")
            
            # 기관별 통계
            inst_count = {}
            for job in all_jobs:
                inst = job.get('dept_name', '알 수 없음')
                inst_count[inst] = inst_count.get(inst, 0) + 1
            
            print(f"\n🏢 기관별 신규 데이터 (상위 10개):")
            for inst, count in sorted(inst_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"   - {inst}: {count}건")
            
            # 고용형태별 통계
            emp_count = {}
            for job in all_jobs:
                emp_type = job.get('employment_type', '알 수 없음')
                emp_count[emp_type] = emp_count.get(emp_type, 0) + 1
            
            print(f"\n💼 고용형태별 신규 데이터:")
            for emp_type, count in sorted(emp_count.items(), key=lambda x: x[1], reverse=True):
                print(f"   - {emp_type}: {count}건")
                
    except Exception as e:
        print(f"수집 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False, stats
    
    return True, stats

if __name__ == "__main__":
    success, final_stats = collect_30day_optimized_data()
    if success:
        print(f"\n🎉 30일 이내 최적화 수집기 실행 완료")
        print(f"💡 효율성: 총 {final_stats['api_calls']}번의 API 호출로 {final_stats['new_saved']}건 신규 수집")
    else:
        print(f"\n❌ 30일 이내 최적화 수집기 실행 실패")