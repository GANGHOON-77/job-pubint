# 🚀 GitHub Actions 자동 스케줄러 설정 가이드

## 📋 개요
`auto_update_jobs.py`와 GitHub Actions를 활용한 채용정보 자동 업데이트 시스템

## 🎯 주요 기능

### 1️⃣ 신규 채용공고 자동 수집
- **스케줄**: 매 5분마다 실행
- **기능**: API에서 최신 채용공고 조회 → Firebase 중복성 체크 → 신규 데이터 저장
- **수집 정보**: 모든 필드 + 상세내용 + 첨부파일 정보

### 2️⃣ 30일 경과 채용공고 자동 정리
- **스케줄**: 매일 새벽 0시 (한국 시간 기준)
- **기능**: 등록일 기준 30일 이상 경과한 채용공고 삭제

## ⚙️ GitHub Repository 설정

### 1. Secrets 설정
GitHub Repository → Settings → Secrets and variables → Actions에서 다음 2개 추가:

#### `FIREBASE_CREDENTIALS`
```json
{
  "type": "service_account",
  "project_id": "job-pubint",
  "private_key_id": "1c4c2dbd08...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-fbsvc@job-pubint.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40job-pubint.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
```

#### `MOEF_API_KEY`
```
1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg==
```

### 2. 파일 업로드
다음 파일들을 GitHub Repository에 업로드:

```
📁 Repository Root/
├── auto_update_jobs.py                    # 자동 업데이트 스크립트
├── requirements.txt                       # Python 의존성
├── .github/workflows/job_update_scheduler.yml  # GitHub Actions 워크플로우
└── README.md                             # 프로젝트 문서
```

## 🔧 로컬 테스트

### 신규 채용공고 수집 테스트
```bash
cd 버전1.5_확정_20250906
set UPDATE_MODE=new_jobs
python auto_update_jobs.py
```

### 30일 경과 채용공고 정리 테스트
```bash
set UPDATE_MODE=cleanup
python auto_update_jobs.py
```

## 📊 모니터링

### GitHub Actions 로그 확인
1. GitHub Repository → Actions 탭
2. "🚀 채용정보 자동 업데이트 스케줄러" 워크플로우 선택
3. 실행 로그에서 다음 정보 확인:
   - 신규 채용공고 수집 결과
   - 30일 경과 채용공고 정리 결과
   - 에러 발생 여부

### 수동 실행
1. GitHub Repository → Actions 탭
2. "🚀 채용정보 자동 업데이트 스케줄러" 선택
3. "Run workflow" 버튼 클릭
4. 모드 선택:
   - `new_jobs`: 신규 채용공고만 수집
   - `cleanup`: 30일 경과 채용공고만 정리
   - `both`: 두 작업 모두 실행

## 🚨 주의사항

### API 호출 제한
- 공공데이터포털 API 일일 호출 제한 고려
- 과도한 API 호출 시 차단 가능성

### Firebase 사용량
- Firestore 읽기/쓰기 작업 비용 발생
- 배치 처리로 최적화되어 있음

### 크롤링 부하
- 상세 내용 및 첨부파일 수집 시 서버 부하 고려
- 적절한 지연시간 설정

## 🔄 웹페이지 실시간 반영

Firebase Firestore의 실시간 리스너 기능을 통해 데이터 변경사항이 웹페이지에 자동 반영됩니다:

```javascript
// portal_v1.5.html에서 Firebase 실시간 리스너 작동
db.collection('recruitment_jobs').onSnapshot((snapshot) => {
    // 데이터 변경 시 자동으로 UI 업데이트
    loadJobs();
});
```

## 📈 기대 효과

1. **24시간 자동 운영**: 수동 작업 없이 채용정보 최신 상태 유지
2. **데이터 정확성**: 중복 제거 및 최신 정보만 제공
3. **저장공간 최적화**: 30일 이상 경과 데이터 자동 정리
4. **실시간 업데이트**: 웹사이트에서 최신 정보 즉시 확인

---

**🎉 설정 완료 후 자동으로 운영됩니다!**