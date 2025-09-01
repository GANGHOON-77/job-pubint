# -*- coding: utf-8 -*-
import sys
import firebase_admin
from firebase_admin import credentials, firestore
sys.stdout.reconfigure(encoding='utf-8')

def debug_specific_doc():
    """특정 문서의 정확한 데이터 확인"""
    
    try:
        # Firebase 초기화
        cred = credentials.Certificate("job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        print("=== 특정 문서 290214 상세 조회 ===")
        
        # 특정 문서 직접 조회
        doc_ref = db.collection('recruitment_jobs').document('290214')
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            print(f"문서 ID: {doc.id}")
            print(f"문서 존재: {doc.exists}")
            
            # 모든 필드 출력
            for field, value in data.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"  {field}: '{value[:100]}...' (길이: {len(value)})")
                else:
                    print(f"  {field}: '{value}' (타입: {type(value)})")
        else:
            print("문서가 존재하지 않습니다")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_specific_doc()