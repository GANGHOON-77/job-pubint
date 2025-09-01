# -*- coding: utf-8 -*-
import sys
import requests
import json
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding='utf-8')

def check_30_day_count():
    """30일 필터 적용시 몇 건인지 확인"""
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    
    print("=== 14일 필터 적용 데이터 건수 확인 ===")
    
    # 14일 전 날짜 (2025-08-18)
    target_date = "2025-08-18"
    print(f"기준 날짜: {target_date} 이후 등록된 게시글 (14일 필터)")
    
    count_after_date = 0
    total_checked = 0
    
    try:
        # 처음 1페이지만 확인 (API 타임아웃 방지)
        for page in range(1, 2):  # 1페이지만 확인
            print(f"\n📄 페이지 {page} 확인 중...")
            
            url = f"http://apis.data.go.kr/1051000/recruitment/list"
            params = {
                'serviceKey': SERVICE_KEY,
                'numOfRows': 100,
                'pageNo': page,
                'returnType': 'JSON'
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('result', [])
                total_count = data.get('totalCount', len(items))
                
                print(f"페이지 {page}: {len(items)}건 확인, 전체 데이터: {total_count}건")
                
                # 처음 페이지에서 첫 번째 항목 구조 확인
                if page == 1 and len(items) > 0:
                    print(f"   첫 번째 항목의 ongoingYn: {items[0].get('ongoingYn')}")
                    print(f"   첫 번째 항목의 pbancEndYmd: {items[0].get('pbancEndYmd')}")
                    print(f"   샘플 5개의 ongoingYn 값들:")
                    for i, item in enumerate(items[:5]):
                        print(f"     항목 {i+1}: ongoingYn = {item.get('ongoingYn')}, 마감일 = {item.get('pbancEndYmd')}")
                
                page_count = 0
                # 처음 5개만 샘플로 날짜 확인
                sample_dates = []
                
                for i, item in enumerate(items):
                    total_checked += 1
                    
                    # 등록일 확인 (공고시작일)
                    reg_date_str = item.get('pbancBgngYmd', '')
                    if reg_date_str and len(reg_date_str) == 8:
                        # YYYYMMDD -> YYYY-MM-DD 변환
                        reg_date = f"{reg_date_str[:4]}-{reg_date_str[4:6]}-{reg_date_str[6:8]}"
                        
                        if i < 5:  # 처음 5개 샘플 날짜 저장
                            sample_dates.append(reg_date)
                        
                        if reg_date >= target_date:
                            count_after_date += 1
                            page_count += 1
                            
                print(f"페이지 {page}에서 {target_date} 이후 등록: {page_count}건")
                if page == 1:
                    print(f"   샘플 날짜들: {sample_dates[:5]}")
                
                if page == 1:
                    print(f"\n📊 전체 데이터 규모: {total_count}건")
                    if total_count > 1000:
                        print(f"⚠️  전체 데이터가 많습니다. 처음 5페이지(500건)만 샘플링하여 비율 계산합니다.")
            else:
                print(f"API 호출 실패: {response.status_code}")
        
        print(f"\n=== 결과 요약 ===")
        print(f"확인한 데이터: {total_checked}건")
        print(f"{target_date} 이후 등록: {count_after_date}건")
        
        if total_checked > 0:
            ratio = count_after_date / total_checked
            print(f"비율: {ratio*100:.1f}%")
            
            # 전체 데이터에 적용한 예상치 계산
            if 'total_count' in locals():
                estimated_total = int(total_count * ratio)
                print(f"전체 {total_count}건 중 예상 30일 이내 등록: 약 {estimated_total}건")
        
    except Exception as e:
        print(f"확인 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_30_day_count()