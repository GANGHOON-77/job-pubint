# -*- coding: utf-8 -*-
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

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
try:
    from attachment_collector import AttachmentCollector
except ImportError:
    AttachmentCollector = None
    print("AttachmentCollector not available")

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

# Firebase 초기화 (Vercel과 로컬 호환)
try:
    print(f"Current working directory: {os.getcwd()}")
    print(f"Files in directory: {os.listdir('.')}")
    
    # 이미 초기화되어 있는지 확인
    if not firebase_admin._apps:
        # Vercel 환경: 환경변수에서 Firebase 키 읽기
        firebase_key_env = os.getenv('FIREBASE_KEY')
        if firebase_key_env:
            import json
            import tempfile
            print("Vercel 환경: 환경변수에서 Firebase 키 읽기")
            firebase_config = json.loads(firebase_key_env)
            
            # 임시 JSON 파일 생성
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_f:
                json.dump(firebase_config, temp_f)
                temp_path = temp_f.name
            
            cred = credentials.Certificate(temp_path)
            print("Vercel Firebase 키 로드 성공")
        # 로컬: 기존 JSON 파일 사용
        elif os.path.exists("job-pubint-firebase-adminsdk-fbsvc-8a7f28a86e.json"):
            cred = credentials.Certificate("job-pubint-firebase-adminsdk-fbsvc-8a7f28a86e.json")
            print("로컬 Firebase JSON 키 파일 사용")
        else:
            raise Exception("Firebase 키를 찾을 수 없습니다 (환경변수 또는 파일)")
            
        firebase_admin.initialize_app(cred)
        print("Firebase 초기화 성공")
    else:
        print("Firebase 이미 초기화됨")
    db = firestore.client()
    print("Firebase 연결 성공")
except Exception as e:
    print(f"Firebase 연결 실패: {e}")
    db = None

# 첨부파일 컬렉터 초기화
attachment_collector = None
if db and AttachmentCollector:
    try:
        # 환경 변수 또는 로컬 파일 사용
        key_path = os.getenv('FIREBASE_KEY_PATH', "job-pubint-firebase-adminsdk-fbsvc-8a7f28a86e.json")
        attachment_collector = AttachmentCollector(key_path)
        print("AttachmentCollector 초기화 성공")
    except Exception as e:
        print(f"AttachmentCollector 초기화 실패: {e}")

# 첨부파일 모델
class AttachmentFile(BaseModel):
    fileID: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None

class JobAttachments(BaseModel):
    announcement: Optional[AttachmentFile] = None
    application: Optional[AttachmentFile] = None
    job_description: Optional[AttachmentFile] = None
    others: Optional[List[AttachmentFile]] = []
    unavailable_reason: Optional[str] = None

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
    src_url: Optional[str] = None
    attachments: Optional[JobAttachments] = None
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
    """HTML 페이지 제공 - index_v1.1.html로 리다이렉션"""
    return FileResponse("index_v1.1.html", media_type="text/html")

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
    print(f"Jobs API called with params: limit={limit}, days={days}, search={search}")
    if not db:
        print("Firebase db is None - connection failed")
        raise HTTPException(status_code=503, detail="Firebase 연결 오류")
    
    try:
        # Firebase에서 데이터 조회 (우리가 저장한 구조에 맞게)
        query = db.collection('recruitment_jobs')
        # 모든 데이터를 가져온 후 Python에서 reg_date 기준으로 정렬
        
        # 데이터 조회
        docs = query.stream()
        jobs = []
        
        # 날짜 필터링 기준
        cutoff_date = datetime.now() - timedelta(days=days)
        today = datetime.now()
        
        for doc in docs:
            firebase_data = doc.to_dict()
            
            # 날짜 형식 변환 함수
            def format_date(date_str):
                if not date_str:
                    return ''
                # YYYYMMDD -> YYYY-MM-DD
                if len(date_str) == 8 and date_str.isdigit():
                    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                return str(date_str)
            
            # Firebase 데이터를 UI가 기대하는 형식으로 변환
            reg_date_formatted = format_date(firebase_data.get('reg_date', ''))
            end_date_formatted = format_date(firebase_data.get('end_date', ''))
            
            job_data = {
                'id': doc.id,
                'idx': firebase_data.get('idx', ''),
                'title': firebase_data.get('title', ''),  # 신버전 필드명
                'dept_name': firebase_data.get('dept_name', ''),  # 신버전 필드명
                'work_region': firebase_data.get('work_region', ''),
                'employment_type': firebase_data.get('employment_type', ''),
                'reg_date': reg_date_formatted,  # 형식 변환된 날짜
                'end_date': end_date_formatted,  # 형식 변환된 날짜
                'recruit_num': int(firebase_data.get('recruit_num', 1)),  # 신버전 필드명
                'recruit_type': firebase_data.get('recruit_type', ''),
                'ncs_category': firebase_data.get('ncs_category', ''),
                'education': firebase_data.get('education', '학력무관'),
                'work_field': firebase_data.get('work_field', ''),
                'salary_info': firebase_data.get('salary_info', '회사내규에 따름'),
                'preference': firebase_data.get('preference', ''),
                'qualification': firebase_data.get('detail_content', ''),
                'detail_content': firebase_data.get('detail_content', ''),
                'recruit_period': firebase_data.get('recruit_period', reg_date_formatted + ' ~ ' + end_date_formatted),
                'src_url': firebase_data.get('src_url', ''),
                'created_at': convert_timestamp_to_string(firebase_data.get('created_at')),
                'updated_at': convert_timestamp_to_string(firebase_data.get('updated_at')),
                'status': firebase_data.get('status', 'active'),
                'attachments': firebase_data.get('attachments')  # 실제 Firebase 첨부파일 정보
            }
            
            # 상태 필터
            if active_only and job_data.get('status') != 'active':
                continue
            
            # src_url이 없는 경우 생성
            if not job_data.get('src_url'):
                job_idx = job_data.get('idx', '')
                job_data['src_url'] = f"https://job.alio.go.kr/recruitview.do?idx={job_idx}"
            
            jobs.append(job_data)
        
        # 등록일(reg_date) 기준으로 최신순 정렬 (YYYY-MM-DD 형식)
        jobs.sort(key=lambda x: x.get('reg_date', '1900-01-01'), reverse=True)
        
        # limit 적용
        jobs = jobs[:limit]
        
        return jobs
        
    except Exception as e:
        print(f"Error in get_jobs: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 조회 실패: {str(e)}")

def convert_timestamp_to_string(timestamp):
    """타임스탬프를 문자열로 변환"""
    if timestamp is None:
        return datetime.now().isoformat()
    
    # 이미 문자열인 경우
    if isinstance(timestamp, str):
        return timestamp
    
    # Firebase DatetimeWithNanoseconds 타입인 경우
    if hasattr(timestamp, 'isoformat'):
        return timestamp.isoformat()
    
    # 기타 타입은 문자열로 변환
    return str(timestamp)

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
        
        # Firebase timestamp 변환
        data['created_at'] = convert_timestamp_to_string(data.get('created_at'))
        data['updated_at'] = convert_timestamp_to_string(data.get('updated_at'))
        
        # src_url이 없는 경우에만 생성
        if not data.get('src_url'):
            job_idx = data.get('idx', '')
            data['src_url'] = f"https://job.alio.go.kr/recruitview.do?idx={job_idx}"
        
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
        # 전체 공고 조회 (status 조건 제거)
        docs = db.collection('recruitment_jobs')\
                .limit(1000)\
                .stream()
        
        jobs = []
        for doc in docs:
            data = doc.to_dict()
            jobs.append(data)
        
        # 통계 계산
        today = datetime.now()
        today_str = today.strftime('%Y-%m-%d')
        
        # 7일 전, 3일 후 날짜
        seven_days_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        three_days_later = (today + timedelta(days=3)).strftime('%Y-%m-%d')
        
        # 통계 계산
        total_count = len(jobs)  # 전체 265건
        urgent_count = 0
        new_count = 0
        org_set = set()
        
        for job in jobs:
            # 등록기관 (모든 공고)
            dept_name = job.get('dept_name', '')
            if dept_name:
                org_set.add(dept_name)
            
            # 등록일, 마감일 확인
            reg_date = job.get('reg_date', '')
            end_date = job.get('end_date', '')
            
            # 신규 채용 (등록일 7일 전 이후)
            if reg_date and reg_date >= seven_days_ago:
                new_count += 1
            
            # 임박 (마감일 3일 이내)
            if end_date and end_date <= three_days_later and end_date >= today_str:
                urgent_count += 1
        
        
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

@app.post("/api/jobs/{job_idx}/attachments")
async def update_job_attachments(job_idx: str):
    """특정 채용공고의 첨부파일 정보를 수집하고 업데이트"""
    if not db or not attachment_collector:
        raise HTTPException(status_code=503, detail="서비스 연결 오류")
    
    try:
        print(f"첨부파일 수집 요청: {job_idx}")
        
        # 첨부파일 정보 수집 및 업데이트
        attachments = attachment_collector.update_job_attachments(job_idx)
        
        if attachments:
            return {
                "success": True,
                "message": f"첨부파일 정보 업데이트 완료: {job_idx}",
                "attachments": attachments
            }
        else:
            return {
                "success": False,
                "message": f"첨부파일 정보를 찾을 수 없습니다: {job_idx}",
                "attachments": None
            }
            
    except Exception as e:
        print(f"첨부파일 수집 오류 ({job_idx}): {e}")
        raise HTTPException(status_code=500, detail=f"첨부파일 수집 실패: {str(e)}")

@app.get("/api/jobs/{job_idx}/attachments")
async def get_job_attachments(job_idx: str):
    """특정 채용공고의 첨부파일 정보 조회 (없으면 자동 수집)"""
    if not db:
        raise HTTPException(status_code=503, detail="Firebase 연결 오류")
    
    try:
        # Firebase에서 기존 첨부파일 정보 확인
        doc = db.collection('recruitment_jobs').document(job_idx).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="채용공고를 찾을 수 없습니다")
        
        data = doc.to_dict()
        existing_attachments = data.get('attachments')
        
        # 첨부파일 정보가 이미 있으면 반환
        if existing_attachments:
            return {
                "success": True,
                "attachments": existing_attachments,
                "source": "cached"
            }
        
        # 첨부파일 정보가 없으면 수집 시도
        if attachment_collector:
            print(f"첨부파일 정보 없음, 자동 수집 시도: {job_idx}")
            attachments = attachment_collector.update_job_attachments(job_idx)
            
            if attachments:
                return {
                    "success": True,
                    "attachments": attachments,
                    "source": "collected"
                }
        
        # 수집 실패
        return {
            "success": False,
            "attachments": None,
            "message": "첨부파일 정보를 찾을 수 없습니다"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"첨부파일 조회 오류 ({job_idx}): {e}")
        raise HTTPException(status_code=500, detail=f"첨부파일 조회 실패: {str(e)}")

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