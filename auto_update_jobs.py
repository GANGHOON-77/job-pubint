#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import os
import sys
from datetime import datetime, timedelta, timezone
import firebase_admin
from firebase_admin import credentials, firestore
from urllib.parse import urlencode
import re
from bs4 import BeautifulSoup
import pytz
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutoJobUpdater:
    def __init__(self):
        """GitHub Actions용 자동 업데이터 초기화"""
        
        # 환경 변수에서 설정 로드 (보안 강화 - 하드코딩 제거)
        self.service_key = os.getenv('MOEF_API_KEY')
        if not self.service_key:
            logger.error("MOEF_API_KEY 환경변수가 설정되지 않았습니다.")
            sys.exit(1)
        self.base_url = "http://apis.data.go.kr/1051000/recruitment/list"
        
        # Firebase 초기화
        self.db = None
        self.existing_job_ids = set()
        self.init_firebase()
        
        # 한국 시간대 설정
        self.kr_tz = pytz.timezone('Asia/Seoul')
        
        logger.info("AutoJobUpdater 초기화 완료")
    
    def init_firebase(self):
        """Firebase 초기화 (GitHub Secrets에서 인증 정보 로드)"""
        try:
            # GitHub Actions에서 Firebase 인증 정보 로드
            firebase_cred = os.getenv('FIREBASE_CREDENTIALS')
            
            if firebase_cred:
                # JSON 문자열을 파일로 저장
                with open('/tmp/firebase_key.json', 'w') as f:
                    f.write(firebase_cred)
                cred_path = '/tmp/firebase_key.json'
            else:
                # 로컬 개발용 경로
                cred_path = "파이어베이스 인증/job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json"
            
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            
            self.db = firestore.client()
            self.load_existing_job_ids()
            logger.info("Firebase 연결 성공")
            
        except Exception as e:
            logger.error(f"Firebase 연결 실패: {e}")
            sys.exit(1)
    
    def load_existing_job_ids(self):
        """기존 채용공고 ID 목록을 로드"""
        try:
            collection_ref = self.db.collection('recruitment_jobs')
            docs = collection_ref.select(['idx']).get()
            
            self.existing_job_ids = set()
            for doc in docs:
                self.existing_job_ids.add(doc.id)
            
            logger.info(f"기존 채용공고 {len(self.existing_job_ids)}건 로드 완료")
            
        except Exception as e:
            logger.error(f"기존 데이터 로드 실패: {e}")
            self.existing_job_ids = set()
    
    def fetch_latest_jobs(self, max_pages=3):
        """최신 채용공고 조회 (신규 확인용)"""
        jobs_data = []
        
        for page in range(1, max_pages + 1):
            try:
                params = {
                    'serviceKey': self.service_key,
                    'numOfRows': '100',
                    'pageNo': str(page),
                    'returnType': 'JSON'
                }
                
                url = f"{self.base_url}?{urlencode(params)}"
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                if 'result' in data and data['result']:
                    page_jobs = data['result']
                    jobs_data.extend(page_jobs)
                    logger.info(f"페이지 {page}: {len(page_jobs)}건 조회")
                else:
                    logger.warning(f"페이지 {page}: 데이터 없음")
                    break
                
                time.sleep(1)  # API 호출 간격
                
            except Exception as e:
                logger.error(f"페이지 {page} 조회 실패: {e}")
                continue
        
        logger.info(f"총 {len(jobs_data)}건의 채용공고 조회 완료")
        return jobs_data
    
    def is_new_job(self, job_idx):
        """신규 채용공고인지 확인"""
        return str(job_idx) not in self.existing_job_ids
    
    def process_job_data(self, job_data):
        """채용공고 데이터 처리 및 상세정보 수집"""
        try:
            job_idx = str(job_data.get('recrutPblntSn', ''))
            if not job_idx:
                return None
            
            # 기본 정보 처리
            processed_job = {
                'idx': job_idx,
                'title': str(job_data.get('recrutPbancTtl', '')).strip(),
                'dept_name': str(job_data.get('instNm', '')).strip(),
                'work_region': str(job_data.get('workRgnNmLst', '')).strip(),
                'employment_type': self.map_employment_type(job_data.get('hireTypeNmLst', '')),
                'reg_date': self.parse_date(job_data.get('pbancBgngYmd', '')),
                'end_date': self.parse_date(job_data.get('pbancEndYmd', '')),
                'recruit_num': self.parse_number(job_data.get('recrutNope', '0')),
                'recruit_type': self.map_recruit_type(job_data.get('recrutSeNm', '')),
                'ncs_category': str(job_data.get('ncsCdNmLst', '')).strip(),
                'education': str(job_data.get('acbgCondNmLst', '')).strip(),
                'work_field': str(job_data.get('ncsCdNmLst', '')).strip(),
                'salary_info': '회사내규에 따름',
                'preference': str(job_data.get('prefCondCn', '')).strip(),
                'src_url': str(job_data.get('srcUrl', '')),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'status': 'active',
                'source': 'moef_api'
            }
            
            # 상세 내용 수집
            processed_job['detail_content'] = self.get_detailed_content(job_data)
            
            # 첨부파일 정보 수집
            processed_job['attachments'] = self.get_job_attachments(job_idx)
            
            # 채용기간 생성
            if processed_job['reg_date'] and processed_job['end_date']:
                processed_job['recruit_period'] = f"{processed_job['reg_date']} ~ {processed_job['end_date']}"
            
            return processed_job
            
        except Exception as e:
            logger.error(f"채용공고 처리 실패 (idx: {job_idx}): {e}")
            return None
    
    def map_employment_type(self, emp_type):
        """고용형태 매핑"""
        type_map = {
            'R1010': '정규직',
            'R1020': '계약직',
            'R1030': '무기계약직',
            'R1040': '비정규직',
            'R1050': '청년인턴',
            'R1060': '청년인턴(체험형)',
            'R1070': '청년인턴(채용형)',
        }
        return type_map.get(str(emp_type), str(emp_type))
    
    def map_recruit_type(self, recruit_type):
        """채용구분 매핑"""
        type_map = {
            'R2010': '신입',
            'R2020': '경력',
            'R2030': '신입+경력',
            'R2040': '외국인 전형',
        }
        return type_map.get(str(recruit_type), str(recruit_type))
    
    def parse_date(self, date_str):
        """날짜 파싱"""
        if not date_str:
            return None
        
        try:
            date_str = str(date_str).strip()
            
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                return date_str[:10]
            
            if re.match(r'\d{8}', date_str):
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            return datetime.now().strftime('%Y-%m-%d')
            
        except Exception:
            return datetime.now().strftime('%Y-%m-%d')
    
    def parse_number(self, num_str):
        """숫자 파싱"""
        try:
            return int(re.sub(r'[^\d]', '', str(num_str))) if num_str else 1
        except:
            return 1
    
    def get_detailed_content(self, job_data):
        """채용공고 상세 내용 스크래핑"""
        job_idx = str(job_data.get('recrutPblntSn', ''))
        if not job_idx:
            return str(job_data.get('aplyQlfcCn', '')).strip()
        
        try:
            detail_url = f"https://job.alio.go.kr/recruitview.do?idx={job_idx}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(detail_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 상세 내용 추출 선택자들
            possible_selectors = [
                'div[class*="content"]',
                'div.recruitView_left',
                'div.recruit_view_left',
                'div.detail_content',
                'div.content_left',
                'div.left_content',
                '.recruitview_left',
                '.recruit-view-left',
                'div[class*="left"]',
                'div[class*="detail"]'
            ]
            
            detail_content = ""
            for selector in possible_selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        text = element.get_text(separator='\n', strip=True)
                        if text and len(text) > 50:
                            detail_content = text
                            break
                    if detail_content:
                        break
            
            if not detail_content or len(detail_content.strip()) < 10:
                detail_content = str(job_data.get('aplyQlfcCn', '')).strip()
            
            return detail_content
            
        except Exception as e:
            logger.error(f"상세 내용 스크래핑 실패 (idx: {job_idx}): {e}")
            return str(job_data.get('aplyQlfcCn', '')).strip()
    
    def get_job_attachments(self, job_idx):
        """첨부파일 정보 크롤링"""
        if not job_idx:
            return {}
        
        try:
            detail_url = f"https://job.alio.go.kr/recruitview.do?idx={job_idx}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(detail_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            attachments = {
                'announcement': None,
                'application': None,
                'job_description': None,
                'others': [],
                'unavailable_reason': None
            }
            
            # 첨부파일 테이블 찾기
            tables = soup.find_all('table')
            for table in tables:
                if '첨부파일' in table.get_text() or '공고문' in table.get_text():
                    rows = table.find_all('tr')
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            category_cell = cells[0]
                            file_cell = cells[1]
                            
                            category = category_cell.get_text(strip=True)
                            file_link = file_cell.find('a')
                            
                            if file_link:
                                href = file_link.get('href', '')
                                file_name = file_link.get_text(strip=True)
                                
                                if 'fileNo=' in href:
                                    file_id = self.extract_file_id(href)
                                    
                                    if '공고문' in category:
                                        attachments['announcement'] = {
                                            'fileID': file_id,
                                            'name': file_name,
                                            'type': 'A'
                                        }
                                    elif '입사지원서' in category:
                                        attachments['application'] = {
                                            'fileID': file_id,
                                            'name': file_name,
                                            'type': 'B'
                                        }
                                    elif '직무기술서' in category:
                                        attachments['job_description'] = {
                                            'fileID': file_id,
                                            'name': file_name,
                                            'type': 'C'
                                        }
                                    elif '기타' in category:
                                        attachments['others'].append({
                                            'fileID': file_id,
                                            'name': file_name,
                                            'type': 'Z'
                                        })
                    break
            
            return attachments
            
        except Exception as e:
            logger.error(f"첨부파일 추출 실패 (idx: {job_idx}): {e}")
            return {}
    
    def extract_file_id(self, url):
        """URL에서 파일 ID 추출"""
        try:
            if 'fileNo=' in url:
                start = url.find('fileNo=') + 7
                end = url.find('&', start)
                if end == -1:
                    return url[start:]
                return url[start:end]
            elif 'fileID=' in url:
                start = url.find('fileID=') + 7
                end = url.find('&', start)
                if end == -1:
                    return url[start:]
                return url[start:end]
        except:
            pass
        return None
    
    def save_to_firebase(self, job):
        """단일 채용공고를 Firebase에 저장"""
        try:
            collection_ref = self.db.collection('recruitment_jobs')
            doc_ref = collection_ref.document(job['idx'])
            
            doc_ref.set(job)
            self.existing_job_ids.add(job['idx'])
            
            logger.info(f"Firebase 저장 완료: {job['idx']} - {job['title'][:30]}")
            return True
            
        except Exception as e:
            logger.error(f"Firebase 저장 실패 (idx: {job['idx']}): {e}")
            return False
    
    def check_and_collect_new_jobs(self):
        """신규 채용공고 확인 및 수집 (매 5분마다 실행)"""
        logger.info("=== 신규 채용공고 확인 시작 ===")
        
        # 최신 채용공고 조회
        latest_jobs = self.fetch_latest_jobs(max_pages=2)
        
        new_jobs = []
        for job_data in latest_jobs:
            job_idx = str(job_data.get('recrutPblntSn', ''))
            if not job_idx:
                continue
            
            # 신규 채용공고인지 확인
            if self.is_new_job(job_idx):
                processed_job = self.process_job_data(job_data)
                if processed_job:
                    new_jobs.append(processed_job)
                    logger.info(f"신규 발견: {job_idx} - {processed_job['title'][:30]}")
        
        # 신규 채용공고 저장
        saved_count = 0
        for job in new_jobs:
            if self.save_to_firebase(job):
                saved_count += 1
        
        logger.info(f"신규 채용공고 수집 완료: {saved_count}건 저장")
        return saved_count
    
    def cleanup_old_jobs(self):
        """30일 경과한 채용공고 삭제 (매일 새벽 0시 실행)"""
        logger.info("=== 30일 경과 채용공고 정리 시작 ===")
        
        try:
            # 30일 전 날짜 계산 (한국 시간 기준)
            kr_now = datetime.now(self.kr_tz)
            cutoff_date = (kr_now - timedelta(days=30)).strftime('%Y-%m-%d')
            
            logger.info(f"삭제 기준일: {cutoff_date} 이전 등록 게시글")
            
            collection_ref = self.db.collection('recruitment_jobs')
            
            # 30일 이전 등록된 문서들 조회
            query = collection_ref.where('reg_date', '<', cutoff_date)
            old_docs = query.get()
            
            deleted_count = 0
            batch_size = 400
            
            # 배치로 삭제 처리
            for i in range(0, len(old_docs), batch_size):
                batch_docs = old_docs[i:i + batch_size]
                batch = self.db.batch()
                
                for doc in batch_docs:
                    batch.delete(doc.reference)
                    deleted_count += 1
                
                batch.commit()
                logger.info(f"배치 {i//batch_size + 1} 삭제 완료: {len(batch_docs)}건")
                
                time.sleep(0.1)  # Firebase 부하 방지
            
            # 캐시 업데이트
            self.load_existing_job_ids()
            
            logger.info(f"30일 경과 채용공고 정리 완료: {deleted_count}건 삭제")
            return deleted_count
            
        except Exception as e:
            logger.error(f"30일 경과 채용공고 정리 실패: {e}")
            return 0

def main():
    """메인 실행 함수"""
    
    # 실행 모드 확인 (환경 변수로 제어)
    mode = os.getenv('UPDATE_MODE', 'new_jobs')  # 'new_jobs' 또는 'cleanup'
    
    updater = AutoJobUpdater()
    
    if mode == 'new_jobs':
        # 신규 채용공고 확인 및 수집
        result = updater.check_and_collect_new_jobs()
        logger.info(f"신규 채용공고 수집 결과: {result}건")
        
    elif mode == 'cleanup':
        # 30일 경과 채용공고 정리
        result = updater.cleanup_old_jobs()
        logger.info(f"30일 경과 채용공고 정리 결과: {result}건 삭제")
        
    else:
        logger.error(f"알 수 없는 실행 모드: {mode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
