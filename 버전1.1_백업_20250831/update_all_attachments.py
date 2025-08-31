# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import firebase_admin
from firebase_admin import credentials, firestore
from data_collector import PublicJobCollector
import time

def update_all_attachments():
    """모든 공고의 첨부파일 정보를 업데이트"""
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    FIREBASE_KEY_PATH = "info-gov-firebase-adminsdk-9o52l-f6b59e8ae8.json"
    
    # Firebase 초기화
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred)
    
    db = firestore.client()
    collector = PublicJobCollector(SERVICE_KEY, FIREBASE_KEY_PATH)
    
    # 모든 공고 조회
    print("모든 공고 조회 중...")
    docs = list(db.collection('recruitment_jobs').stream())
    total_count = len(docs)
    print(f"총 {total_count}건의 공고 발견")
    
    updated_count = 0
    error_count = 0
    
    for i, doc in enumerate(docs, 1):
        data = doc.to_dict()
        job_idx = data.get('idx')
        
        if not job_idx:
            print(f"[{i}/{total_count}] ID {doc.id}: idx 없음, 스킵")
            continue
            
        print(f"[{i}/{total_count}] 공고 {job_idx} 처리 중...")
        
        # 이미 첨부파일 정보가 있는 경우 스킵
        if data.get('attachments'):
            print(f"  -> 이미 첨부파일 정보 있음, 스킵")
            continue
            
        try:
            # 첨부파일 정보 크롤링
            attachments = collector.get_job_attachments(job_idx)
            
            if attachments:
                # 첨부파일 정보가 있는 경우만 업데이트
                has_files = (
                    attachments.get('announcement') or 
                    attachments.get('application') or 
                    attachments.get('job_description') or 
                    attachments.get('others') or 
                    attachments.get('unavailable_reason')
                )
                
                if has_files:
                    doc.reference.update({
                        'attachments': attachments,
                        'updated_at': firestore.SERVER_TIMESTAMP
                    })
                    updated_count += 1
                    print(f"  -> 첨부파일 정보 업데이트 완료")
                    
                    # 첨부파일 내용 출력
                    if attachments.get('announcement'):
                        print(f"    공고문: {attachments['announcement']['name']}")
                    if attachments.get('application'):
                        print(f"    입사지원서: {attachments['application']['name']}")
                    if attachments.get('job_description'):
                        print(f"    직무기술서: {attachments['job_description']['name']}")
                    if attachments.get('others'):
                        print(f"    기타: {len(attachments['others'])}개")
                    if attachments.get('unavailable_reason'):
                        print(f"    미첨부사유: {attachments['unavailable_reason']}")
                else:
                    print(f"  -> 첨부파일 없음")
            else:
                print(f"  -> 첨부파일 정보 추출 실패")
                
        except Exception as e:
            error_count += 1
            print(f"  -> 오류 발생: {e}")
            
        # API 호출 간격 조절 (너무 빠르면 차단될 수 있음)
        time.sleep(1)
    
    print(f"\n=== 업데이트 완료 ===")
    print(f"총 처리: {total_count}건")
    print(f"업데이트: {updated_count}건")
    print(f"오류: {error_count}건")

if __name__ == "__main__":
    update_all_attachments()