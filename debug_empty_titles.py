# -*- coding: utf-8 -*-
import sys
import firebase_admin
from firebase_admin import credentials, firestore
sys.stdout.reconfigure(encoding='utf-8')

def debug_empty_titles():
    """빈 제목을 가진 문서들 확인"""
    
    try:
        # Firebase 초기화
        cred = credentials.Certificate("job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        print("=== 빈 제목을 가진 문서들 확인 ===")
        
        # 모든 문서 조회
        collection_ref = db.collection('recruitment_jobs')
        docs = collection_ref.get()
        
        empty_title_docs = []
        valid_docs = []
        
        for doc in docs:
            data = doc.to_dict()
            title = data.get('title', '').strip()
            dept_name = data.get('dept_name', '').strip()
            
            if not title or not dept_name:
                empty_title_docs.append({
                    'id': doc.id,
                    'title': title,
                    'dept_name': dept_name,
                    'reg_date': data.get('reg_date', ''),
                    'idx': data.get('idx', '')
                })
            else:
                valid_docs.append({
                    'id': doc.id,
                    'title': title[:50] + '...' if len(title) > 50 else title,
                    'dept_name': dept_name,
                    'reg_date': data.get('reg_date', ''),
                    'idx': data.get('idx', '')
                })
        
        print(f"\n전체 문서: {len(docs)}건")
        print(f"빈 제목/기관명 문서: {len(empty_title_docs)}건")
        print(f"정상 문서: {len(valid_docs)}건")
        
        if empty_title_docs:
            print(f"\n빈 제목 문서들 (처음 5개):")
            for doc in empty_title_docs[:5]:
                print(f"  ID: {doc['id']}, IDX: {doc['idx']}, title: '{doc['title']}', dept: '{doc['dept_name']}', date: {doc['reg_date']}")
        
        if valid_docs:
            print(f"\n정상 문서들 (최신 5개):")
            valid_docs.sort(key=lambda x: x.get('reg_date', '1900-01-01'), reverse=True)
            for doc in valid_docs[:5]:
                print(f"  ID: {doc['id']}, title: '{doc['title']}', dept: '{doc['dept_name']}', date: {doc['reg_date']}")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_empty_titles()