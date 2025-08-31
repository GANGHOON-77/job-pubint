# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import firebase_admin
from firebase_admin import credentials, firestore
from data_collector import PublicJobCollector

def update_single_job_attachments(job_idx):
    """특정 공고의 첨부파일 정보를 업데이트"""
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    FIREBASE_KEY_PATH = "info-gov-firebase-adminsdk-9o52l-f6b59e8ae8.json"
    
    # Firebase 초기화
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred)
    
    db = firestore.client()
    collector = PublicJobCollector(SERVICE_KEY, FIREBASE_KEY_PATH)
    
    # 첨부파일 정보 크롤링
    print(f"공고 {job_idx} 첨부파일 정보 크롤링 중...")
    attachments = collector.get_job_attachments(job_idx)
    
    if attachments:
        print("첨부파일 정보:")
        print(f"- 공고문: {attachments.get('announcement')}")
        print(f"- 입사지원서: {attachments.get('application')}")  
        print(f"- 직무기술서: {attachments.get('job_description')}")
        print(f"- 기타: {attachments.get('others')}")
        print(f"- 미접수사유: {attachments.get('unavailable_reason')}")
        
        # Firebase에서 해당 문서 찾기
        docs = db.collection('recruitment_jobs').where('idx', '==', str(job_idx)).limit(1).stream()
        
        for doc in docs:
            print(f"문서 ID: {doc.id}")
            # 첨부파일 정보 업데이트
            doc.reference.update({
                'attachments': attachments,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            print("첨부파일 정보 업데이트 완료!")
            return True
    
    print("첨부파일 정보 업데이트 실패")
    return False

if __name__ == "__main__":
    # 290240번 공고 업데이트
    success = update_single_job_attachments("290240")
    if success:
        print("\n업데이트 완료! localhost:8001에서 확인하세요.")
    else:
        print("\n업데이트 실패")