# -*- coding: utf-8 -*-
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import glob
import os

def upload_json_to_firebase():
    """JSON 파일에서 데이터를 읽어서 Firebase에 업로드"""
    
    # Firebase 초기화
    try:
        cred = credentials.Certificate("info-gov-firebase-adminsdk-9o52l-f6b59e8ae8.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase connected successfully")
    except Exception as e:
        print(f"Firebase connection failed: {e}")
        return False
    
    # 최신 JSON 파일 찾기
    json_files = glob.glob("jobs_data_*.json")
    if not json_files:
        print("No JSON data files found")
        return False
    
    latest_file = max(json_files, key=os.path.getctime)
    print(f"Loading data from: {latest_file}")
    
    # JSON 파일 읽기
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        jobs = data.get('jobs', [])
        print(f"Found {len(jobs)} jobs in JSON file")
        
    except Exception as e:
        print(f"Failed to read JSON file: {e}")
        return False
    
    if not jobs:
        print("No jobs data found")
        return False
    
    # Firebase에 저장
    collection_ref = db.collection('recruitment_jobs')
    saved_count = 0
    updated_count = 0
    error_count = 0
    
    print("Starting upload to Firebase...")
    
    for i, job in enumerate(jobs, 1):
        try:
            job_idx = str(job.get('idx', ''))
            if not job_idx:
                print(f"  WARNING: Skipping job {i}: No ID")
                error_count += 1
                continue
            
            doc_ref = collection_ref.document(job_idx)
            
            # 기존 문서 확인
            existing_doc = doc_ref.get()
            
            if existing_doc.exists:
                # 업데이트
                job['updated_at'] = datetime.now().isoformat()
                doc_ref.update(job)
                updated_count += 1
                action = "Updated"
            else:
                # 신규 저장
                job['created_at'] = datetime.now().isoformat()
                job['updated_at'] = datetime.now().isoformat()
                doc_ref.set(job)
                saved_count += 1
                action = "Saved"
            
            # 진행 상황 출력 (10개마다)
            if i % 10 == 0 or i <= 5:
                title = job.get('title', 'No Title')[:40]
                dept = job.get('dept_name', 'No Dept')[:20]
                print(f"  {action} ({i}/{len(jobs)}): {job_idx} - {title} | {dept}")
            
        except Exception as e:
            print(f"  ERROR: Error saving job {i}: {e}")
            error_count += 1
    
    # 결과 요약
    print(f"\nUpload completed!")
    print(f"   New jobs saved: {saved_count}")
    print(f"   Jobs updated: {updated_count}")
    if error_count > 0:
        print(f"   Errors: {error_count}")
    print(f"   Total processed: {saved_count + updated_count}")
    
    # Firebase 컬렉션 확인
    try:
        total_docs = len(list(collection_ref.limit(1000).stream()))
        print(f"   Total documents in collection: {total_docs}")
    except:
        print("   Could not count total documents")
    
    return saved_count + updated_count

if __name__ == "__main__":
    print("=" * 50)
    print("Firebase Upload Tool")
    print("=" * 50)
    
    result = upload_json_to_firebase()
    
    if result:
        print(f"\nSuccessfully uploaded {result} jobs to Firebase!")
        print("Check your Firebase console to see the data")
    else:
        print("\nUpload failed")
    
    print("=" * 50)