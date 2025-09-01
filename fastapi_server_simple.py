# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Optional, List
from datetime import datetime, timedelta
import uvicorn
from pydantic import BaseModel
import os

app = FastAPI(
    title="공공기관 채용정보 API",
    description="Firebase 연동 간소화 버전",
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

# Firebase 초기화 (더 안전한 방식)
db = None
try:
    # 이미 초기화되어 있는지 확인
    if not firebase_admin._apps:
        # 가장 최신 인증 파일 사용
        cred_file = "info-gov-firebase-adminsdk-9o52l-423bfadd63.json"
        if os.path.exists(cred_file):
            cred = credentials.Certificate(cred_file)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print(f"[SUCCESS] Firebase 연결 성공: {cred_file}")
        else:
            print(f"[ERROR] Firebase 인증 파일을 찾을 수 없음: {cred_file}")
    else:
        db = firestore.client()
        print("[SUCCESS] Firebase 이미 초기화됨")
except Exception as e:
    print(f"[ERROR] Firebase 연결 실패: {e}")
    db = None

# 간단한 응답 모델
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
    status: str = "active"

class StatsResponse(BaseModel):
    total_count: int
    urgent_count: int
    new_count: int
    org_count: int
    updated_at: str

@app.get("/")
async def serve_index():
    """HTML 페이지 제공"""
    return FileResponse("index_v1.1.html", media_type="text/html")

@app.get("/api/health")
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "firebase": "connected" if db else "disconnected",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/jobs")
async def get_jobs(
    limit: int = Query(default=50, le=200, description="최대 조회 건수")
):
    """채용공고 목록 조회 - 간소화 버전"""
    if not db:
        # Firebase 연결 실패시 샘플 데이터 반환
        print("[WARNING] Firebase 연결 없음 - 샘플 데이터 반환")
        return generate_sample_jobs(limit)
    
    try:
        print(f"[INFO] Firebase에서 데이터 조회 시작 (limit: {limit})")
        
        # 가장 간단한 쿼리 - 조건 없이 바로 가져오기
        docs = db.collection('recruitment_jobs').limit(limit).stream()
        
        jobs = []
        count = 0
        for doc in docs:
            count += 1
            data = doc.to_dict()
            
            # 필수 필드만 추출
            job = {
                'idx': data.get('idx', doc.id),
                'title': data.get('title', '제목 없음'),
                'dept_name': data.get('dept_name', '기관명 없음'),
                'work_region': data.get('work_region', '지역 미정'),
                'employment_type': data.get('employment_type', '고용형태 미정'),
                'reg_date': data.get('reg_date', datetime.now().strftime('%Y-%m-%d')),
                'end_date': data.get('end_date', (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')),
                'recruit_num': data.get('recruit_num', 0),
                'recruit_type': data.get('recruit_type', '미정'),
                'status': data.get('status', 'active'),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # src_url 생성
            job['src_url'] = f"https://job.alio.go.kr/recruitview.do?idx={job['idx']}"
            
            jobs.append(job)
            
            # 10개마다 로그
            if count % 10 == 0:
                print(f"  ... {count}개 로드됨")
        
        print(f"[SUCCESS] 총 {len(jobs)}개 채용공고 로드 완료")
        return jobs
        
    except Exception as e:
        print(f"[ERROR] Firebase 조회 오류: {e}")
        print("[WARNING] 샘플 데이터로 대체")
        return generate_sample_jobs(limit)

@app.get("/api/stats")
async def get_statistics():
    """통계 정보 - 간소화 버전"""
    if not db:
        return StatsResponse(
            total_count=50,
            urgent_count=5,
            new_count=15,
            org_count=6,
            updated_at=datetime.now().isoformat()
        )
    
    try:
        # 간단한 통계만 반환
        docs = db.collection('recruitment_jobs').limit(100).stream()
        
        jobs = []
        for doc in docs:
            jobs.append(doc.to_dict())
        
        total_count = len(jobs)
        org_set = set(job.get('dept_name', '') for job in jobs)
        
        return StatsResponse(
            total_count=total_count,
            urgent_count=min(5, total_count // 10),
            new_count=min(15, total_count // 3),
            org_count=len(org_set),
            updated_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        print(f"[ERROR] 통계 조회 오류: {e}")
        return StatsResponse(
            total_count=0,
            urgent_count=0,
            new_count=0,
            org_count=0,
            updated_at=datetime.now().isoformat()
        )

def generate_sample_jobs(limit: int):
    """샘플 데이터 생성"""
    companies = ['한국전력공사', '한국수자원공사', '한국도로공사', '한국철도공사', '한국토지주택공사', '한국가스공사']
    titles = ['IT개발직 신입사원', '경영관리직 경력사원', '기술직 채용', '행정직 공개채용', '연구개발직 모집']
    locations = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종']
    types = ['정규직', '계약직', '무기계약직']
    
    jobs = []
    for i in range(1, min(limit + 1, 51)):
        reg_date = datetime.now() - timedelta(days=i % 30)
        end_date = reg_date + timedelta(days=30)
        
        job = {
            'idx': f'SAMPLE-2024-{str(i).zfill(4)}',
            'title': titles[i % len(titles)],
            'dept_name': companies[i % len(companies)],
            'work_region': locations[i % len(locations)],
            'employment_type': types[i % len(types)],
            'reg_date': reg_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'recruit_num': (i % 10) + 1,
            'recruit_type': '신입' if i % 2 == 0 else '경력',
            'status': 'active',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'src_url': f'https://job.alio.go.kr/recruitview.do?idx=SAMPLE-2024-{str(i).zfill(4)}'
        }
        jobs.append(job)
    
    return jobs

if __name__ == "__main__":
    print("=" * 50)
    print("Firebase 간소화 서버 시작")
    print("=" * 50)
    print(f"서버 주소: http://localhost:8001")
    print(f"API 문서: http://localhost:8001/docs")
    print(f"Firebase 상태: {'연결됨' if db else '연결 안됨'}")
    print("=" * 50)
    
    uvicorn.run(
        "fastapi_server_simple:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )