# -*- coding: utf-8 -*-
import sys
import firebase_admin
from firebase_admin import credentials, firestore
sys.stdout.reconfigure(encoding='utf-8')

def debug_recent_docs():
    """Firebase에서 최근 저장된 문서들 확인"""
    
    try:
        # Firebase 초기화
        cred = credentials.Certificate("job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        print("=== Firebase 최근 5개 문서 확인 ===")
        
        # 컬렉션의 모든 문서를 reg_date 기준으로 정렬해서 가져오기
        collection_ref = db.collection('recruitment_jobs')
        docs = collection_ref.limit(5).get()
        
        for i, doc in enumerate(docs, 1):
            data = doc.to_dict()
            print(f"\n문서 {i} (ID: {doc.id}):")
            print(f"  title: '{data.get('title', 'NO_TITLE')}'")
            print(f"  dept_name: '{data.get('dept_name', 'NO_DEPT')}'")
            print(f"  reg_date: '{data.get('reg_date', 'NO_DATE')}'")
            print(f"  idx: '{data.get('idx', 'NO_IDX')}'")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_recent_docs()