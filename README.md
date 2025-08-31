# 🏛️ 대한민국 공공기관 채용정보 포털

실시간 공공기관 채용정보를 제공하는 웹 포털로, GitHub Actions를 이용한 자동화 시스템을 구축했습니다.

## 🚀 주요 기능

### ✅ 실시간 자동화 시스템
- **5분마다 신규 채용공고 자동 수집**
- **30일 지난 공고 자동 삭제**
- **GitHub Actions 기반 무인 운영**

### ✅ 완전한 첨부파일 다운로드
- **실제 다운로드 링크** (fileNo 기반)
- **정확한 파일 분류**: 공고문, 입사지원서, 직무기술서, 기타
- **전체 커버리지**: 모든 공고 대상 완전 구축

### ✅ 사용자 친화적 UI
- **카드형 레이아웃**과 상세 모달
- **실시간 검색 및 필터링**
- **반응형 디자인**

## 🛠️ 기술 스택

- **Backend**: FastAPI + Firebase Firestore
- **Frontend**: Vanilla JavaScript + HTML5/CSS3
- **Automation**: GitHub Actions
- **Data Source**: 공공데이터포털 API + ALIO 크롤링

## 📁 프로젝트 구조

```
public_int/
├── .github/workflows/
│   └── auto-collect.yml      # GitHub Actions 워크플로우
├── index.html                # 메인 웹페이지
├── fastapi_server.py         # FastAPI 백엔드 서버
├── data_collector.py         # 데이터 수집 시스템
├── github_auto_collector.py  # GitHub Actions용 자동 수집기
├── requirements.txt          # Python 의존성
└── README.md                # 이 파일
```

## ⚙️ GitHub Actions 설정

### 1. Secrets 설정 (필수)

GitHub 저장소의 Settings > Secrets and variables > Actions에서 다음을 설정:

```
GOV_API_KEY: 공공데이터포털 API 키
FIREBASE_SERVICE_ACCOUNT: Firebase 서비스 계정 JSON (전체 내용)
```

### 2. Firebase 서비스 계정 키 생성

1. [Firebase Console](https://console.firebase.google.com) 접속
2. 프로젝트 설정 > 서비스 계정 탭
3. "새 비공개 키 생성" 클릭
4. 생성된 JSON 파일 내용을 `FIREBASE_SERVICE_ACCOUNT` Secret에 저장

### 3. 자동화 스케줄

```yaml
schedule:
  - cron: '*/5 * * * *'  # 매 5분마다 신규 데이터 수집
  - cron: '0 3 * * *'    # 매일 오전 3시 구 데이터 삭제
```

## 🚀 로컬 실행 방법

### 1. 환경 설정
```bash
pip install -r requirements.txt
```

### 2. Firebase 키 설정
- `info-gov-firebase-adminsdk-*.json` 파일을 프로젝트 루트에 배치

### 3. 서버 실행
```bash
uvicorn fastapi_server:app --host 0.0.0.0 --port 8001 --reload
```

### 4. 웹 접속
- http://localhost:8001

## 📊 자동화 시스템 특징

### 🔄 데이터 관리
- **자동 수집**: 5분마다 최신 3페이지 체크
- **자동 정리**: 30일 지난 공고 자동 삭제
- **중복 방지**: 기존 데이터와 비교하여 신규만 수집

### 📎 첨부파일 처리
- **실시간 크롤링**: 신규 공고 발견 시 첨부파일 정보 자동 수집
- **정확한 분류**: 공고문(A), 입사지원서(B), 직무기술서(C), 기타(Z)
- **안정적 처리**: 크롤링 실패 시에도 기본 데이터는 저장

### 🛡️ 안정성
- **에러 처리**: 모든 예외 상황 대응
- **배치 처리**: 대용량 데이터도 안전하게 처리
- **로그**: 상세한 실행 로그로 모니터링 가능

## 📈 모니터링

GitHub Actions 탭에서 실행 상황을 실시간으로 확인할 수 있습니다:

- ✅ **성공**: 신규 데이터 수집 완료
- ⚠️ **경고**: 신규 데이터 없음 (정상)
- ❌ **실패**: 오류 발생 (로그 확인 필요)

## 🔗 관련 링크

- **공공데이터포털**: https://data.go.kr
- **ALIO 채용정보**: https://job.alio.go.kr
- **Firebase Console**: https://console.firebase.google.com

---

**🏆 자동화된 공공기관 채용정보 포털 - GitHub Actions 기반 무인 운영 시스템**