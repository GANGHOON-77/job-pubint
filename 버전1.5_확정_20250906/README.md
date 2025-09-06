# 🚀 대한민국 공공기관 채용정보 포털 v1.5

## 📅 버전 정보
- **버전**: 1.5 (확정)
- **날짜**: 2025-09-06
- **작성자**: Claude AI Assistant

## 🎯 프로젝트 개요
대한민국 정부기관, 공공기관, 지자체의 채용정보를 실시간으로 수집하고 제공하는 웹 포털 시스템

## ✨ v1.5 주요 기능

### 1. 📊 데이터 수집 시스템
- **완전한 데이터 수집**: `data_collector_v1.5.py`
  - 공공데이터포털 API 연동
  - 개별 채용공고 웹 크롤링
  - 첨부파일 URL 자동 수집
  - 중복 체크 및 업데이트
  - 30일 이내 데이터 필터링

### 2. 🎨 사용자 인터페이스
- **반응형 웹 디자인**: `portal_v1.5.html`
  - SEO 최적화 메타태그
  - 모바일 최적화 (2x2 통계 그리드)
  - 실시간 통계 대시보드
  - 상세 모달 창
  - 첨부파일 다운로드

### 3. 🔥 Firebase 연동
- **실시간 데이터베이스**
  - Firestore 컬렉션: `recruitment_jobs`
  - 완전한 필드 스키마
  - 실시간 동기화

### 4. 🖥️ 서버 시스템
- **로컬 서버**: `server_v1.5.py`
  - 포트: 8003
  - HTML 서빙
  - CORS 설정

## 📁 파일 구조
```
버전1.5_확정_20250906/
├── portal_v1.5.html           # 메인 UI (SEO 최적화)
├── data_collector_v1.5.py     # 데이터 수집기
├── server_v1.5.py             # 로컬 서버
├── 파이어베이스 인증/
│   └── job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json
└── README.md                  # 현재 문서
```

## 🔧 필드 스키마

### 필수 필드
```python
{
    'idx': str,                # 공고번호
    'title': str,              # 채용제목
    'dept_name': str,          # 기관명
    'work_region': str,        # 근무지역
    'employment_type': str,    # 채용형태
    'recruit_num': int,        # 채용인원
    'recruit_type': str,       # 채용구분
    'recruit_period': str,     # 채용기간
    'reg_date': str,           # 등록일
    'end_date': str,           # 마감일
    'detail_content': str,     # 상세내용
    'attachments': list,       # 첨부파일
    'url': str                 # 원본 URL
}
```

## 🚀 실행 방법

### 1. 데이터 수집
```bash
cd 버전1.5_확정_20250906
python data_collector_v1.5.py
```

### 2. 서버 실행
```bash
python server_v1.5.py
```

### 3. 웹 접속
```
http://localhost:8003
```

## 🎯 v1.5 개선사항

### UI/UX 개선
- ✅ SEO 최적화 (메타태그, Schema.org)
- ✅ 모바일 반응형 통계 박스 (2x2 그리드)
- ✅ "국가, 공공기관, 지자체 채용정보 모두를 이 사이트에서 확인 가능~^^" 문구 추가
- ✅ Pretendard 최신 폰트 적용

### 데이터 처리
- ✅ 완전한 필드 매핑 시스템
- ✅ 첨부파일 크롤링 및 저장
- ✅ 중복 체크 알고리즘
- ✅ 30일 필터링

### 시스템 안정성
- ✅ Firebase 연결 안정화
- ✅ 에러 핸들링 강화
- ✅ UTF-8 인코딩 문제 해결

## 📋 필요 패키지
```bash
pip install requests beautifulsoup4 firebase-admin fastapi uvicorn
```

## ⚠️ 주의사항
1. Firebase 인증 파일 경로 확인 필요
2. API 일일 호출 제한 고려 (10페이지 제한)
3. 웹 크롤링 시 서버 부하 고려

## 📈 통계 기능
- 전체 채용공고 수
- 마감임박 (3일 이내)
- 신규 채용 (7일 이내)
- 등록기관 수

## 🔍 검색 키워드 (SEO)
- 고용, 채용, 일자리, 일터, 채용정보
- 공공기관 채용, 정부기관 채용, 지자체 채용
- 공무원 채용, 채용공고, 취업정보
- 구인구직, 공공일자리, 정규직, 계약직

## 📞 문의
프로젝트 관련 문의는 시스템 관리자에게 연락 바랍니다.

---
**Version 1.5 - Final Release**
*2025.09.06 확정*