from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import uvicorn

app = FastAPI(title="공공기관 채용정보 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    cred = credentials.Certificate("info-gov-firebase-adminsdk-9o52l-f6b59e8ae8.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase 연결 성공")
except Exception as e:
    print(f"Firebase 연결 실패: {e}")
    db = None

@app.get("/")
async def root():
    return {
        "message": "공공기관 채용정보 API",
        "firebase_status": "connected" if db else "disconnected"
    }

@app.get("/api/jobs")
async def get_jobs():
    if not db:
        raise HTTPException(status_code=503, detail="Firebase 연결 오류")
    
    try:
        docs = db.collection('recruitment_jobs').limit(300).stream()
        jobs = []
        
        cutoff_date = datetime.now() - timedelta(days=30)
        today = datetime.now()
        
        for doc in docs:
            data = doc.to_dict()
            
            try:
                reg_date = datetime.strptime(data.get('reg_date', ''), '%Y-%m-%d')
                end_date = datetime.strptime(data.get('end_date', ''), '%Y-%m-%d')
                
                if reg_date >= cutoff_date and end_date >= today:
                    jobs.append(data)
                    
            except (ValueError, TypeError):
                continue
        
        return {"jobs": jobs, "count": len(jobs)}
        
    except Exception as e:
        print(f"조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    if not db:
        raise HTTPException(status_code=503, detail="Firebase 연결 오류")
    
    try:
        docs = db.collection('recruitment_jobs').limit(300).stream()
        jobs = []
        
        for doc in docs:
            jobs.append(doc.to_dict())
        
        today = datetime.now()
        cutoff_date = today - timedelta(days=30)
        seven_days_ago = today - timedelta(days=7)
        three_days_later = today + timedelta(days=3)
        
        total_count = 0
        urgent_count = 0
        new_count = 0
        orgs = set()
        
        for job in jobs:
            try:
                reg_date = datetime.strptime(job.get('reg_date', ''), '%Y-%m-%d')
                end_date = datetime.strptime(job.get('end_date', ''), '%Y-%m-%d')
                
                if reg_date >= cutoff_date and end_date >= today:
                    total_count += 1
                    orgs.add(job.get('dept_name', ''))
                    
                    if end_date <= three_days_later:
                        urgent_count += 1
                    
                    if reg_date >= seven_days_ago:
                        new_count += 1
                        
            except (ValueError, TypeError):
                continue
        
        return {
            "total_count": total_count,
            "urgent_count": urgent_count,
            "new_count": new_count,
            "org_count": len(orgs)
        }
        
    except Exception as e:
        print(f"통계 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("FastAPI 서버 시작 - http://localhost:8000")
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)