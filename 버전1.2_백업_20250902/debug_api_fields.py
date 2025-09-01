# -*- coding: utf-8 -*-
import sys
import os
import requests
import json
sys.stdout.reconfigure(encoding='utf-8')

def debug_api_fields():
    """API 응답의 실제 필드명 확인"""
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    
    print("=== API 필드명 디버그 ===")
    
    try:
        url = f"http://apis.data.go.kr/1051000/recruitment/list"
        params = {
            'serviceKey': SERVICE_KEY,
            'numOfRows': 5,  # 처음 5개만 가져오기
            'pageNo': 1,
            'returnType': 'JSON'
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('result', [])
            
            print(f"전체 응답 구조:")
            print(f"- totalCount: {data.get('totalCount')}")
            print(f"- result 배열 크기: {len(items)}")
            
            if len(items) > 0:
                print(f"\n첫 번째 아이템의 모든 필드:")
                first_item = items[0]
                for key, value in first_item.items():
                    print(f"  {key}: {value}")
                
                print(f"\n주요 필드 값 확인:")
                print(f"- ongoingYn: {first_item.get('ongoingYn', 'NOT_FOUND')}")
                print(f"- pbancBgngYmd: {first_item.get('pbancBgngYmd', 'NOT_FOUND')}")
                print(f"- pbancEndYmd: {first_item.get('pbancEndYmd', 'NOT_FOUND')}")
                print(f"- empmnsnIdx: {first_item.get('empmnsnIdx', 'NOT_FOUND')}")
                print(f"- empmnsnTitle: {first_item.get('empmnsnTitle', 'NOT_FOUND')}")
                print(f"- recrutPblntSn: {first_item.get('recrutPblntSn', 'NOT_FOUND')}")
                print(f"- recrutPblntTtl: {first_item.get('recrutPblntTtl', 'NOT_FOUND')}")
                
                print(f"\n처음 3개 아이템의 ongoingYn 값:")
                for i, item in enumerate(items[:3]):
                    ongoing = item.get('ongoingYn', 'NOT_FOUND')
                    bgng_date = item.get('pbancBgngYmd', 'NOT_FOUND')
                    end_date = item.get('pbancEndYmd', 'NOT_FOUND')
                    print(f"  아이템 {i+1}: ongoingYn={ongoing}, 시작일={bgng_date}, 마감일={end_date}")
                
        else:
            print(f"API 호출 실패: {response.status_code}")
            print(f"응답: {response.text[:500]}...")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_api_fields()