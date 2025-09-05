# Firebase 설정 정보

## 🔥 Firebase 프로젝트 정보
- **프로젝트 이름**: job-pubint
- **데이터베이스**: Cloud Firestore
- **컬렉션명**: `recruitment_jobs`
- **총 데이터 수**: 546건 (30일 필터링 적용)

## 🔑 인증 키 파일
```
파이어베이스 인증/job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json
```

## 📊 데이터베이스 구조
```javascript
Collection: recruitment_jobs
Document: {
    idx: string,              // 공고번호
    title: string,            // 채용공고 제목
    dept_name: string,        // 기관명
    work_region: string,      // 근무지역
    employment_type: string,  // 고용형태
    reg_date: string,         // 등록일 (YYYY-MM-DD)
    end_date: string,         // 마감일 (YYYY-MM-DD)
    recruit_num: number,      // 채용인원
    recruit_type: string,     // 채용구분
    ncs_category: string,     // NCS 분류
    education: string,        // 학력요구사항
    work_field: string,       // 근무분야
    salary_info: string,      // 급여정보
    preference: string,       // 우대조건
    detail_content: string,   // 상세내용
    recruit_period: string,   // 채용기간
    src_url: string,          // 원본 URL
    attachments: object,      // 첨부파일 정보
    status: string,           // 상태 (active)
    created_at: timestamp,    // 생성일시
    updated_at: timestamp     // 수정일시
}
```

## 🔒 보안 설정
- **읽기 권한**: 허용
- **쓰기 권한**: 제한됨 (서버 어드민만)
- **키 파일 보안**: 절대 외부 노출 금지

## 📋 필터링 규칙
- **기준일**: 2025년 8월 6일 이후
- **필터링**: `reg_date >= '2025-08-06'`
- **결과**: 546건 데이터

## 🔧 서버 연결 코드 (Python)
```python
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase 초기화
cred = credentials.Certificate("파이어베이스 인증/job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# 30일 필터링 쿼리
cutoff_date = datetime(2025, 8, 6)
collection_ref = db.collection('recruitment_jobs')
docs = collection_ref.get()
```

## ⚠️ 중요 참고사항
1. **키 파일 절대 노출 금지**: GitHub 등에 업로드 하지 마세요
2. **읽기 전용**: 이 앱은 데이터를 읽기만 합니다
3. **자동 업데이트**: 별도 GitHub Actions에서 관리
4. **백업**: Firebase Console에서 확인 가능

## 🌐 Firebase Console 접속
- URL: https://console.firebase.google.com
- 프로젝트: job-pubint
- 데이터베이스: Firestore Database

---
**Firebase 연결 상태**: ✅ 정상 작동 중