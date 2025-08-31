# 공공기관 채용정보 시스템 버전 1.0

## 백업 일시
2025년 8월 31일

## 포함된 파일들
- `index_v1.html` - 메인 웹 인터페이스 (완성된 UI)
- `fastapi_server_v1.py` - FastAPI 백엔드 서버
- `upload_simple_v1.py` - Firebase 데이터 업로드 스크립트
- `jobs_data_v1.json` - 실제 채용공고 데이터 (237개)
- `firebase_credentials_v1.json` - Firebase 인증 파일

## 완성된 기능들

### 웹 인터페이스 (index_v1.html)
- ✅ 실시간 채용공고 통계 (전체, 임박, 신규, 기관수)
- ✅ 채용공고 카드 목록 표시
- ✅ 페이지네이션 (10페이지씩 그룹화)
- ✅ 검색 기능 (제목, 기관명)
- ✅ 통계 박스 클릭시 필터링 (전체/임박/신규)
- ✅ 상세보기 모달
- ✅ D-day 표시 (노란색: 일반, 빨간색: 임박)
- ✅ 고용형태 배지 (통일된 회색 스타일)
- ✅ 자동 데이터 로딩

### 모달 기능
- ✅ 왼쪽 패널: 기본정보 (공고번호, 기관명, 채용인원 등)
- ✅ 오른쪽 패널: 상세요강, 전형정보, 첨부파일
- ✅ 지원하기 버튼 (원본 사이트로 이동)
- ✅ 북마크 기능
- ✅ 실제 채용공고 내용 표시 (심플한 포맷)

### FastAPI 서버 (fastapi_server_v1.py)
- ✅ Firebase 연동
- ✅ CORS 설정
- ✅ HTML 파일 서빙
- ✅ 채용공고 API (/api/jobs)
- ✅ 통계 API (/api/stats)
- ✅ 상세조회 API (/api/jobs/{job_id})
- ✅ 필터링 및 검색 지원

### 데이터 업로드 (upload_simple_v1.py)
- ✅ JSON 파일에서 Firebase로 데이터 업로드
- ✅ Unicode 문제 해결
- ✅ 신규/업데이트 구분
- ✅ 진행상황 표시

## 실행 방법
1. FastAPI 서버 실행: `python fastapi_server_v1.py`
2. 브라우저에서 접속: http://localhost:8001
3. 데이터 업데이트: `python upload_simple_v1.py`

## 주요 특징
- 실제 정부 채용공고 데이터 (237개) 연동
- 반응형 디자인
- 실시간 통계 업데이트
- 사용자 친화적 UI/UX
- 원본 사이트 연동 (지원하기 버튼)

## 기술 스택
- Frontend: HTML, CSS, JavaScript
- Backend: FastAPI (Python)
- Database: Firebase Firestore
- Deployment: Local server (uvicorn)

## 데이터 소스
- 공공기관 채용정보 API
- 실시간 채용공고 수집 및 업데이트
- 상세 채용요강 및 첨부파일 정보 포함