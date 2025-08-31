# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
from pathlib import Path

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firebase 초기화
if not firebase_admin._apps:
    # Vercel 환경변수에서 Firebase 설정 읽기
    firebase_config = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if firebase_config:
        import json
        cred_dict = json.loads(firebase_config)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)

db = firestore.client()

@app.get("/")
async def serve_index():
    """메인 페이지 서빙"""
    index_path = Path(__file__).parent.parent / "index.html"
    return FileResponse(str(index_path))

@app.get("/api/jobs")
async def get_jobs():
    """채용공고 목록 조회"""
    try:
        # 30일 이내 활성 공고만 조회
        thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        thirty_days_ago = thirty_days_ago.replace(day=max(1, thirty_days_ago.day - 30))
        
        jobs_ref = db.collection('recruitment_jobs')
        query = jobs_ref.where('status', '==', 'active').order_by('reg_date', direction=firestore.Query.DESCENDING)
        
        docs = query.stream()
        jobs = []
        
        for doc in docs:
            job_data = doc.to_dict()
            job_data['id'] = doc.id
            
            # Timestamp 변환
            for field in ['created_at', 'updated_at']:
                if field in job_data and hasattr(job_data[field], 'timestamp'):
                    job_data[field] = job_data[field].timestamp()
            
            jobs.append(job_data)
        
        return {"status": "success", "data": jobs}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/{job_id}")
async def get_job_detail(job_id: str):
    """특정 채용공고 상세 조회"""
    try:
        doc = db.collection('recruitment_jobs').document(job_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_data = doc.to_dict()
        job_data['id'] = doc.id
        
        # Timestamp 변환
        for field in ['created_at', 'updated_at']:
            if field in job_data and hasattr(job_data[field], 'timestamp'):
                job_data[field] = job_data[field].timestamp()
        
        return {"status": "success", "data": job_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Vercel serverless function handler
handler = app