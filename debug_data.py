# -*- coding: utf-8 -*-
import sys
import os
import requests
import json
sys.stdout.reconfigure(encoding='utf-8')

def debug_api_response():
    """API 응답 구조 분석"""
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv%2BJNSythF12BiijhVB3qE96%2F4Jxr70zUNg%3D%3D"
    BASE_URL = "http://apis.data.go.kr/1051000/recruitment/list"
    
    params = {
        'serviceKey': SERVICE_KEY,
        'numOfRows': 10,  # 10건만 테스트
        'pageNo': 1,
        'returnType': 'JSON'
    }
    
    try:
        response = requests.get(BASE_URL, params=params)
        print(f"응답 상태코드: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"응답 구조:")
            print(f"- resultCode: {data.get('resultCode')}")
            print(f"- resultMsg: {data.get('resultMsg')}")
            print(f"- totalCount: {data.get('totalCount')}")
            print(f"- result 배열 크기: {len(data.get('result', []))}")
            
            # 첫 번째 데이터 구조 분석
            if data.get('result'):
                first_job = data['result'][0]
                print(f"\n첫 번째 데이터 구조:")
                for key, value in first_job.items():
                    print(f"  {key}: {value}")
                    
                # 실제 저장해보기
                try:
                    from data_collector import PublicJobCollector
                    
                    FIREBASE_KEY_PATH = "job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json"
                    collector = PublicJobCollector("dummy", FIREBASE_KEY_PATH)
                    
                    # 데이터 처리 테스트
                    processed_job = collector.clean_and_process_job(first_job)
                    if processed_job:
                        print(f"\n✅ 데이터 처리 성공:")
                        print(f"  idx: {processed_job.get('idx')}")
                        print(f"  inst_nm: {processed_job.get('inst_nm')}")
                        print(f"  recruit_title: {processed_job.get('recruit_title')}")
                        
                        # Firebase에 저장
                        if collector.db:
                            doc_id = str(processed_job['idx'])
                            collector.db.collection('recruitment_jobs').document(doc_id).set(processed_job)
                            print(f"✅ Firebase 저장 완료: {doc_id}")
                        else:
                            print("❌ Firebase 연결 없음")
                    else:
                        print("❌ 데이터 처리 실패")
                        
                except Exception as e:
                    print(f"❌ 처리 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print(f"API 호출 실패: {response.text}")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_api_response()