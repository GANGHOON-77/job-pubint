# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import uvicorn

app = FastAPI(title="공공기관 채용정보 API - 확정 UI")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firebase 초기화
try:
    cred = credentials.Certificate("파이어베이스 인증/job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("[SUCCESS] Firebase 연결 성공")
except Exception as e:
    print(f"[ERROR] Firebase 연결 실패: {e}")
    db = None

@app.get("/")
async def serve_index():
    """확정된 HTML 페이지 제공"""
    return FileResponse("portal_confirmed.html", media_type="text/html")

@app.get("/api/jobs")
async def get_jobs():
    """채용공고 조회 - 30일 필터링 적용"""
    if not db:
        raise HTTPException(status_code=500, detail="Firebase 연결 실패")
    
    try:
        cutoff_date = datetime(2025, 8, 6)  # 8월 6일 이후만
        
        collection_ref = db.collection('recruitment_jobs')
        docs = collection_ref.get()
        
        jobs = []
        for doc in docs:
            data = doc.to_dict()
            reg_date_str = data.get('reg_date', '')
            
            try:
                if reg_date_str:
                    reg_date = datetime.strptime(reg_date_str, '%Y-%m-%d')
                    if reg_date >= cutoff_date:
                        job_data = {
                            'idx': data.get('idx', ''),
                            'title': data.get('title', ''),
                            'dept_name': data.get('dept_name', ''),
                            'work_region': data.get('work_region', ''),
                            'employment_type': data.get('employment_type', ''),
                            'reg_date': reg_date_str,
                            'end_date': data.get('end_date', ''),
                            'recruit_num': data.get('recruit_num', 0),
                            'recruit_type': data.get('recruit_type', ''),
                            'ncs_category': data.get('ncs_category', ''),
                            'education': data.get('education', ''),
                            'work_field': data.get('work_field', ''),
                            'salary_info': data.get('salary_info', ''),
                            'preference': data.get('preference', ''),
                            'detail_content': data.get('detail_content', ''),
                            'recruit_period': data.get('recruit_period', ''),
                            'src_url': data.get('src_url', ''),
                            'attachments': data.get('attachments', {}),
                            'status': 'active'
                        }
                        jobs.append(job_data)
            except:
                continue
        
        # 날짜순 정렬 (최신순)
        jobs.sort(key=lambda x: x['reg_date'], reverse=True)
        
        # HTML이 기대하는 형식으로 반환
        return jobs
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """통계 정보 조회"""
    if not db:
        raise HTTPException(status_code=500, detail="Firebase 연결 실패")
    
    try:
        cutoff_date = datetime(2025, 8, 6)
        today = datetime.now()
        three_days_later = today + timedelta(days=3)
        seven_days_ago = today - timedelta(days=7)
        
        collection_ref = db.collection('recruitment_jobs')
        docs = collection_ref.get()
        
        total_count = 0
        urgent_count = 0
        new_count = 0
        org_set = set()
        
        for doc in docs:
            data = doc.to_dict()
            reg_date_str = data.get('reg_date', '')
            end_date_str = data.get('end_date', '')
            dept_name = data.get('dept_name', '')
            
            try:
                if reg_date_str:
                    reg_date = datetime.strptime(reg_date_str, '%Y-%m-%d')
                    if reg_date >= cutoff_date:
                        total_count += 1
                        org_set.add(dept_name)
                        
                        # 마감 임박 (3일 이내)
                        if end_date_str:
                            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                            if end_date <= three_days_later and end_date >= today:
                                urgent_count += 1
                        
                        # 신규 채용 (7일 이내)
                        if reg_date >= seven_days_ago:
                            new_count += 1
            except:
                continue
        
        return JSONResponse(content={
            'total_count': total_count,
            'urgent_count': urgent_count,
            'new_count': new_count,
            'org_count': len(org_set),
            'updated_at': today.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("[START] 확정 UI 서버 시작")
    print("[INFO] 546건의 채용공고 데이터 (8월 6일 이후)")
    print("[URL] http://localhost:8003 접속")
    uvicorn.run(app, host="0.0.0.0", port=8003)