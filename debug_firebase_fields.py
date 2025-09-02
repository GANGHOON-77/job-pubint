# -*- coding: utf-8 -*-
import sys
import firebase_admin
from firebase_admin import credentials, firestore
sys.stdout.reconfigure(encoding='utf-8')

def debug_firebase_fields():
    """Firebase에서 실제 저장된 데이터 필드 확인"""
    
    try:
        # Firebase 초기화
        cred = credentials.Certificate("job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        print("=== Firebase 저장된 데이터 필드 구조 확인 ===")
        
        # 최근 저장된 문서 1개 조회
        collection_ref = db.collection('recruitment_jobs')
        docs = collection_ref.limit(1).get()
        
        if docs:
            doc = docs[0]
            data = doc.to_dict()
            
            print(f"문서 ID: {doc.id}")
            print(f"문서 필드 구조:")
            
            for field, value in data.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"  {field}: {value[:100]}... (길이: {len(value)})")
                else:
                    print(f"  {field}: {value}")
        else:
            print("저장된 문서가 없습니다.")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_firebase_fields()