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

app = FastAPI(title="30일 필터링 채용정보 API")

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
    """HTML 페이지 제공"""
    return FileResponse("ui_30day_filtered.html", media_type="text/html")

@app.get("/api/jobs")
async def get_filtered_jobs():
    """30일 이내 채용공고 조회"""
    if not db:
        raise HTTPException(status_code=500, detail="Firebase 연결 실패")
    
    try:
        # 필터링 기준일 (8월 6일)
        cutoff_date = datetime(2025, 8, 6)
        today = datetime.now()
        
        # 데이터 조회
        collection_ref = db.collection('recruitment_jobs')
        docs = collection_ref.get()
        
        filtered_jobs = []
        for doc in docs:
            data = doc.to_dict()
            reg_date_str = data.get('reg_date', '')
            
            try:
                if reg_date_str:
                    reg_date = datetime.strptime(reg_date_str, '%Y-%m-%d')
                    if reg_date >= cutoff_date:
                        job_data = {
                            'id': doc.id,
                            'idx': data.get('idx', ''),
                            'title': data.get('title', ''),
                            'dept_name': data.get('dept_name', ''),
                            'reg_date': reg_date_str,
                            'end_date': data.get('end_date', ''),
                            'work_region': data.get('work_region', ''),
                            'employment_type': data.get('employment_type', ''),
                            'recruit_num': data.get('recruit_num', 0),
                            'recruit_type': data.get('recruit_type', ''),
                            'detail_content': data.get('detail_content', ''),
                            'src_url': data.get('src_url', '')
                        }
                        filtered_jobs.append(job_data)
            except:
                continue
        
        # 날짜순 정렬 (최신순)
        filtered_jobs.sort(key=lambda x: x['reg_date'], reverse=True)
        
        return JSONResponse(content={
            'success': True,
            'total_count': len(filtered_jobs),
            'jobs': filtered_jobs,
            'filter_info': {
                'cutoff_date': cutoff_date.strftime('%Y-%m-%d'),
                'today': today.strftime('%Y-%m-%d')
            }
        })
        
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
        
        filtered_count = 0
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
                        filtered_count += 1
                        org_set.add(dept_name)
                        
                        # 마감 임박 (3일 이내)
                        if end_date_str:
                            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                            if end_date <= three_days_later:
                                urgent_count += 1
                        
                        # 신규 채용 (7일 이내)
                        if reg_date >= seven_days_ago:
                            new_count += 1
            except:
                continue
        
        return JSONResponse(content={
            'success': True,
            'stats': {
                'total_count': filtered_count,
                'urgent_count': urgent_count,
                'new_count': new_count,
                'org_count': len(org_set)
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("[START] 30일 필터링 서버 시작")
    print("브라우저에서 http://localhost:8002 접속")
    uvicorn.run(app, host="0.0.0.0", port=8002)