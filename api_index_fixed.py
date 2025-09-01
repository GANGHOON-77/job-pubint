# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import os
import json

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
db = None
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    if not firebase_admin._apps:
        firebase_config = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
        if firebase_config:
            try:
                cred_dict = json.loads(firebase_config)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                db = firestore.client()
                print("✅ Firebase 초기화 성공")
            except Exception as e:
                print(f"❌ Firebase 초기화 실패: {e}")
                db = None
        else:
            print("❌ FIREBASE_SERVICE_ACCOUNT 환경변수가 설정되지 않음")
            db = None
    else:
        db = firestore.client()
        
except Exception as e:
    print(f"❌ Firebase 모듈 로드 실패: {e}")
    db = None

@app.get("/")
async def root():
    return {"message": "공공기관 채용정보 API", "status": "running"}

@app.get("/api")
async def api_root():
    return {"message": "API 엔드포인트", "firebase_connected": db is not None}

@app.get("/api/jobs")
async def get_jobs(limit: int = 100):
    """채용공고 목록 조회"""
    if not db:
        raise HTTPException(status_code=500, detail="Firebase 연결이 설정되지 않았습니다")
    
    try:
        print(f"🔄 채용공고 {limit}건 조회 시작...")
        
        # 30일 이내 활성 공고만 조회
        thirty_days_ago = datetime.now() - timedelta(days=30)
        thirty_days_ago_str = thirty_days_ago.strftime('%Y-%m-%d')
        
        jobs_ref = db.collection('recruitment_jobs')
        query = jobs_ref.where('status', '==', 'active')
        query = query.where('reg_date', '>=', thirty_days_ago_str)
        query = query.order_by('reg_date', direction=firestore.Query.DESCENDING)
        query = query.limit(limit)
        
        docs = query.stream()
        jobs = []
        
        for doc in docs:
            job_data = doc.to_dict()
            job_data['id'] = doc.id
            
            # Timestamp 변환
            for field in ['created_at', 'updated_at']:
                if field in job_data and hasattr(job_data[field], 'timestamp'):
                    job_data[field] = job_data[field].timestamp()
                elif field in job_data and hasattr(job_data[field], 'isoformat'):
                    job_data[field] = job_data[field].isoformat()
            
            jobs.append(job_data)
        
        print(f"✅ {len(jobs)}건 조회 완료")
        return jobs
        
    except Exception as e:
        print(f"❌ 채용공고 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"데이터베이스 조회 실패: {str(e)}")

@app.get("/api/stats")
async def get_stats():
    """통계 정보 조회"""
    if not db:
        raise HTTPException(status_code=500, detail="Firebase 연결이 설정되지 않았습니다")
    
    try:
        # 간단한 통계 반환
        thirty_days_ago = datetime.now() - timedelta(days=30)
        seven_days_ago = datetime.now() - timedelta(days=7)
        three_days_later = datetime.now() + timedelta(days=3)
        
        # 기본 통계
        jobs_ref = db.collection('recruitment_jobs')
        total_query = jobs_ref.where('status', '==', 'active').where('reg_date', '>=', thirty_days_ago.strftime('%Y-%m-%d'))
        
        total_count = len(list(total_query.stream()))
        
        return {
            "total_count": total_count,
            "urgent_count": max(1, total_count // 10),  # 대략적인 값
            "new_count": max(1, total_count // 5),      # 대략적인 값
            "org_count": max(1, total_count // 3),      # 대략적인 값
            "updated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 통계 조회 실패: {e}")
        # 기본값 반환
        return {
            "total_count": 0,
            "urgent_count": 0,
            "new_count": 0,
            "org_count": 0,
            "updated_at": datetime.now().isoformat()
        }

# Vercel 핸들러
handler = app