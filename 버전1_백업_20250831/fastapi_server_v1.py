# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uvicorn
from pydantic import BaseModel

app = FastAPI(
    title="공공기관 채용정보 API",
    description="Firebase와 연동된 공공기관 채용정보 FastAPI 서버",
    version="1.0.0"
)

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
    cred = credentials.Certificate("firebase_credentials_v1.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase 연결 성공")
except Exception as e:
    print(f"Firebase 연결 실패: {e}")
    db = None

# 응답 모델
class JobResponse(BaseModel):
    idx: str
    title: str
    dept_name: str
    work_region: str
    employment_type: str
    reg_date: str
    end_date: str
    recruit_num: int
    recruit_type: str
    ncs_category: Optional[str] = None
    education: Optional[str] = None
    work_field: Optional[str] = None
    salary_info: Optional[str] = None
    preference: Optional[str] = None
    detail_content: Optional[str] = None
    recruit_period: Optional[str] = None
    created_at: str
    updated_at: str
    status: str = "active"

class StatsResponse(BaseModel):
    total_count: int
    urgent_count: int
    new_count: int
    org_count: int
    updated_at: str

@app.get("/favicon.ico")
async def favicon():
    """Favicon 엔드포인트 - 404 오류 방지"""
    return {"message": "No favicon"}

@app.get("/")
async def serve_index():
    """HTML 페이지 제공"""
    return FileResponse("index.html", media_type="text/html")

@app.get("/api")
async def api_root():
    """API 루트 엔드포인트"""
    return {
        "message": "공공기관 채용정보 FastAPI 서버",
        "version": "1.0.0",
        "firebase_status": "connected" if db else "disconnected",
        "endpoints": {
            "jobs": "/api/jobs",
            "job_detail": "/api/jobs/{job_id}",
            "stats": "/api/stats",
            "health": "/api/health"
        }
    }

@app.get("/api/health")
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "firebase": "connected" if db else "disconnected",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/jobs", response_model=List[JobResponse])
async def get_jobs(
    limit: int = Query(default=100, le=1000, description="최대 조회 건수"),
    days: int = Query(default=30, le=90, description="최근 며칠간 등록된 공고"),
    search: Optional[str] = Query(default=None, description="검색어 (제목, 기관명)"),
    employment_type: Optional[str] = Query(default=None, description="고용형태 필터"),
    active_only: bool = Query(default=True, description="진행중 공고만 조회")
):
    """채용공고 목록 조회"""
    if not db:
        raise HTTPException(status_code=503, detail="Firebase 연결 오류")
    
    try:
        # 기본 쿼리 - 인덱스 문제를 피하기 위해 단순화
        query = db.collection('recruitment_jobs')
        query = query.order_by('reg_date', direction=firestore.Query.DESCENDING)
        query = query.limit(limit * 2)  # 필터링을 위해 더 많이 가져옴
        
        # 데이터 조회
        docs = query.stream()
        jobs = []
        
        # 날짜 필터링 기준
        cutoff_date = datetime.now() - timedelta(days=days)
        today = datetime.now()
        
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            
            # 상태 필터 (메모리에서)
            if active_only and data.get('status') != 'active':
                continue
            
            # 날짜 필터링
            try:
                reg_date = datetime.strptime(data.get('reg_date', ''), '%Y-%m-%d')
                end_date = datetime.strptime(data.get('end_date', ''), '%Y-%m-%d')
                
                # 날짜 조건 확인
                if reg_date < cutoff_date or (active_only and end_date < today):
                    continue
                    
            except (ValueError, TypeError):
                continue
            
            # 검색 필터
            if search:
                search_lower = search.lower()
                title = data.get('title', '').lower()
                dept_name = data.get('dept_name', '').lower()
                
                if search_lower not in title and search_lower not in dept_name:
                    continue
            
            # 고용형태 필터
            if employment_type and data.get('employment_type') != employment_type:
                continue
            
            jobs.append(data)
            
            # 원하는 수만큼 수집하면 중단
            if len(jobs) >= limit:
                break
        
        return jobs
        
    except Exception as e:
        print(f"Error in get_jobs: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 조회 실패: {str(e)}")

@app.get("/api/jobs/{job_id}")
async def get_job_detail(job_id: str):
    """특정 채용공고 상세 조회"""
    if not db:
        raise HTTPException(status_code=503, detail="Firebase 연결 오류")
    
    try:
        doc = db.collection('recruitment_jobs').document(job_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="채용공고를 찾을 수 없습니다")
        
        data = doc.to_dict()
        data['id'] = doc.id
        
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_job_detail: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 조회 실패: {str(e)}")

@app.get("/api/stats", response_model=StatsResponse)
async def get_statistics(days: int = Query(default=30, le=90, description="통계 기간")):
    """채용공고 통계 조회"""
    if not db:
        raise HTTPException(status_code=503, detail="Firebase 연결 오류")
    
    try:
        # 전체 활성 공고 조회
        docs = db.collection('recruitment_jobs')\
                .where('status', '==', 'active')\
                .limit(1000)\
                .stream()
        
        jobs = []
        for doc in docs:
            data = doc.to_dict()
            jobs.append(data)
        
        # 날짜 기준
        today = datetime.now()
        cutoff_date = today - timedelta(days=days)
        seven_days_ago = today - timedelta(days=7)
        three_days_later = today + timedelta(days=3)
        
        # 통계 계산
        total_count = 0
        urgent_count = 0
        new_count = 0
        org_set = set()
        
        for job in jobs:
            try:
                reg_date = datetime.strptime(job.get('reg_date', ''), '%Y-%m-%d')
                end_date = datetime.strptime(job.get('end_date', ''), '%Y-%m-%d')
                
                # 30일 이내 진행중 공고
                if reg_date >= cutoff_date and end_date >= today:
                    total_count += 1
                    org_set.add(job.get('dept_name', ''))
                    
                    # 마감 3일 이내 (임박)
                    if end_date <= three_days_later:
                        urgent_count += 1
                    
                    # 최근 7일 등록 (신규)
                    if reg_date >= seven_days_ago:
                        new_count += 1
                        
            except (ValueError, TypeError):
                continue
        
        return StatsResponse(
            total_count=total_count,
            urgent_count=urgent_count,
            new_count=new_count,
            org_count=len(org_set),
            updated_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        print(f"Error in get_statistics: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")

@app.get("/api/organizations")
async def get_organizations():
    """등록 기관 목록 조회"""
    if not db:
        raise HTTPException(status_code=503, detail="Firebase 연결 오류")
    
    try:
        docs = db.collection('recruitment_jobs')\
                .where('status', '==', 'active')\
                .limit(1000)\
                .stream()
        
        orgs = set()
        for doc in docs:
            data = doc.to_dict()
            dept_name = data.get('dept_name')
            if dept_name:
                orgs.add(dept_name)
        
        return sorted(list(orgs))
        
    except Exception as e:
        print(f"Error in get_organizations: {e}")
        raise HTTPException(status_code=500, detail=f"기관 조회 실패: {str(e)}")

@app.get("/api/employment-types")
async def get_employment_types():
    """고용형태 목록 조회"""
    if not db:
        raise HTTPException(status_code=503, detail="Firebase 연결 오류")
    
    try:
        docs = db.collection('recruitment_jobs')\
                .where('status', '==', 'active')\
                .limit(1000)\
                .stream()
        
        types = set()
        for doc in docs:
            data = doc.to_dict()
            employment_type = data.get('employment_type')
            if employment_type:
                types.add(employment_type)
        
        return sorted(list(types))
        
    except Exception as e:
        print(f"Error in get_employment_types: {e}")
        raise HTTPException(status_code=500, detail=f"고용형태 조회 실패: {str(e)}")

if __name__ == "__main__":
    print("FastAPI server starting...")
    print("Server address: http://localhost:8001")
    print("API docs: http://localhost:8001/docs")
    
    uvicorn.run(
        "fastapi_server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )