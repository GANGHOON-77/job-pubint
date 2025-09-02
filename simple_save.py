# -*- coding: utf-8 -*-
import sys
import os
import requests
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')

def simple_firebase_save():
    """간단한 Firebase 저장 테스트"""
    
    # Firebase 연결
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate("job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        print("✅ Firebase 연결 성공")
        
    except Exception as e:
        print(f"❌ Firebase 연결 실패: {e}")
        return
    
    # API 호출
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    BASE_URL = "http://apis.data.go.kr/1051000/recruitment/list"
    
    params = {
        'serviceKey': SERVICE_KEY,
        'numOfRows': 100,
        'pageNo': 1,
        'returnType': 'JSON'
    }
    
    try:
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        
        if data.get('resultCode') == 200 and data.get('result'):
            jobs = data['result']
            print(f"📄 {len(jobs)}건 데이터 확인")
            
            saved_count = 0
            
            for job in jobs:  # 모든 데이터 처리
                try:
                    # 간단한 데이터 매핑
                    doc_data = {
                        'idx': str(job.get('recrutPblntSn', '')),
                        'inst_nm': str(job.get('instNm', '')),
                        'recruit_title': str(job.get('recrutPbancTtl', '')),
                        'work_region': str(job.get('workRgnNmLst', '')),
                        'recruit_person_cnt': str(job.get('recrutNope', '')),
                        'inst_type_nm': '공공기관',  # 기본값
                        'reg_date': str(job.get('pbancBgngYmd', '')),
                        'rcept_end_date': str(job.get('pbancEndYmd', '')),
                        'employment_type': str(job.get('hireTypeNmLst', '')),
                        'recruit_se': str(job.get('recrutSeNm', '')),
                        'preference': str(job.get('prefCondCn', '')),
                        'qualification': str(job.get('aplyQlfcCn', '')),
                        'source_url': str(job.get('srcUrl', '')),
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat(),
                        'status': 'active'
                    }
                    
                    # Firebase에 저장
                    doc_id = doc_data['idx']
                    db.collection('recruitment_jobs').document(doc_id).set(doc_data)
                    
                    print(f"✅ 저장: [{doc_id}] {doc_data['inst_nm']} - {doc_data['recruit_title'][:30]}...")
                    saved_count += 1
                    
                except Exception as e:
                    print(f"❌ 저장 실패: {e}")
            
            print(f"\n🎉 총 {saved_count}건 저장 완료!")
            
        else:
            print(f"❌ API 응답 오류: {data}")
            
    except Exception as e:
        print(f"❌ API 호출 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_firebase_save()