@echo off
echo ====================================
echo 공공기관 채용정보 시스템 v1.4 시작
echo ====================================
echo.
echo [INFO] Firebase 연결 확인 중...
echo [INFO] 546건 채용공고 데이터 준비
echo [INFO] 서버 시작: http://localhost:8003
echo.
echo 브라우저에서 http://localhost:8003 접속하세요
echo 종료하려면 Ctrl+C를 누르세요
echo.

python server_confirmed_ui.py

pause