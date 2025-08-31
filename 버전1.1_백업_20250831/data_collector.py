import requests
import json
import time
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from urllib.parse import urlencode, quote
import re
from bs4 import BeautifulSoup
import logging

class PublicJobCollector:
    def __init__(self, service_key, firebase_key_path=None):
        self.service_key = service_key
        self.base_url = "http://apis.data.go.kr/1051000/recruitment/list"
        
        # Firebase 초기화 (키 파일이 제공되면)
        self.db = None
        self.existing_job_ids = set()  # 기존 채용공고 ID 캐시
        
        if firebase_key_path:
            try:
                cred = credentials.Certificate(firebase_key_path)
                firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                print("Firebase 연결 성공")
                
                # 기존 데이터 ID 로드
                self.load_existing_job_ids()
                
            except Exception as e:
                print(f"Firebase 연결 실패: {e}")
    
    def load_existing_job_ids(self):
        """기존 Firebase 데이터의 ID 목록을 로드하여 중복 체크용 캐시 생성"""
        if not self.db:
            return
        
        try:
            print("기존 채용공고 ID 목록 로드 중...")
            
            # Firebase에서 모든 문서 ID만 가져오기 (최적화)
            collection_ref = self.db.collection('recruitment_jobs')
            
            # 배치로 가져오기 (성능 최적화)
            docs = collection_ref.select(['idx', 'updated_at']).get()
            
            for doc in docs:
                self.existing_job_ids.add(doc.id)
            
            print(f"기존 데이터 {len(self.existing_job_ids)}건 ID 로드 완료")
            
        except Exception as e:
            print(f"⚠️ 기존 데이터 로드 실패: {e}")
            self.existing_job_ids = set()
    
    def is_job_exists(self, job_idx):
        """채용공고 ID가 이미 존재하는지 확인"""
        return str(job_idx) in self.existing_job_ids
    
    def add_to_cache(self, job_idx):
        """새로운 채용공고 ID를 캐시에 추가"""
        self.existing_job_ids.add(str(job_idx))
    
    def needs_attachment_update(self, job_idx):
        """기존 데이터에 첨부파일 정보 업데이트가 필요한지 확인"""
        if not self.db:
            return False
        
        try:
            doc_ref = self.db.collection('recruitment_jobs').document(str(job_idx))
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            data = doc.to_dict()
            attachments = data.get('attachments')
            
            # attachments 필드가 없거나 빈 경우 업데이트 필요
            if not attachments:
                return True
            
            # attachments가 있지만 실제 파일 정보가 없는 경우 업데이트 필요
            if isinstance(attachments, dict):
                has_files = (
                    (attachments.get('announcement') and attachments['announcement'].get('fileID')) or
                    (attachments.get('application') and attachments['application'].get('fileID')) or
                    (attachments.get('job_description') and attachments['job_description'].get('fileID')) or
                    (attachments.get('others') and len(attachments['others']) > 0)
                )
                return not has_files
            
            return True
            
        except Exception as e:
            print(f"⚠️ 첨부파일 업데이트 체크 실패 (idx: {job_idx}): {e}")
            return False
    
    def fetch_job_data(self, num_rows=100, page_no=1):
        """API에서 채용 데이터 가져오기"""
        params = {
            'serviceKey': self.service_key,
            'numOfRows': str(num_rows),
            'pageNo': str(page_no),
            'returnType': 'JSON'
        }
        
        try:
            url = f"{self.base_url}?{urlencode(params)}"
            print(f"📡 API 호출: {url}")
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # API 응답 구조 확인 - 새로운 API 구조
            if 'result' in data and data['result']:
                items = data['result']
                total_count = data.get('totalCount', len(items))
                return items, total_count
                    
            print("⚠️ 응답에서 데이터를 찾을 수 없습니다")
            return [], 0
            
        except requests.exceptions.RequestException as e:
            print(f"❌ API 요청 실패: {e}")
            return [], 0
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 실패: {e}")
            print(f"응답 내용: {response.text[:500]}")
            return [], 0
        except Exception as e:
            print(f"❌ 예상치 못한 오류: {e}")
            return [], 0
    
    def clean_and_process_job(self, job_data):
        """채용 데이터 정리 및 처리"""
        try:
            # 필수 필드 매핑
            processed_job = {
                'idx': str(job_data.get('empmnsnIdx', '')),  # 채용공시번호
                'title': str(job_data.get('empmnsnTitle', '')).strip(),  # 채용제목
                'dept_name': str(job_data.get('deptName', '')).strip(),  # 기관명
                'work_region': str(job_data.get('workRegion', '')).strip(),  # 근무지
                'employment_type': self.map_employment_type(job_data.get('empmnsnType', '')),  # 고용형태
                'reg_date': self.parse_date(job_data.get('regDate', '')),  # 등록일
                'end_date': self.parse_date(job_data.get('endDate', '')),  # 마감일
                'recruit_num': self.parse_number(job_data.get('recruitNum', '0')),  # 채용인원
                'recruit_type': self.map_recruit_type(job_data.get('recruitType', '')),  # 채용형태
                
                # 추가 정보
                'ncs_category': str(job_data.get('ncsCategory', '')).strip(),  # NCS분류
                'education': str(job_data.get('education', '')).strip(),  # 학력정보
                'work_field': str(job_data.get('workField', '')).strip(),  # 근무분야
                'salary_info': str(job_data.get('salaryInfo', '회사내규에 따름')).strip(),  # 급여정보
                'preference': str(job_data.get('preference', '')).strip(),  # 우대조건
                'detail_content': str(job_data.get('detailContent', '')).strip(),  # 상세내용
                'contact_info': str(job_data.get('contactInfo', '')).strip(),  # 문의처
                'attachments': self.get_job_attachments(str(job_data.get('empmnsnIdx', ''))),  # 첨부파일 정보
                
                # 메타데이터
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'status': 'active',
                'source': 'moef_api'  # 기재부 API
            }
            
            # 데이터 검증
            if not processed_job['idx'] or not processed_job['title']:
                return None
            
            # 채용기간 생성
            if processed_job['reg_date'] and processed_job['end_date']:
                processed_job['recruit_period'] = f"{processed_job['reg_date']} ~ {processed_job['end_date']}"
            
            return processed_job
            
        except Exception as e:
            print(f"❌ 데이터 처리 실패: {e}")
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
            # 다양한 날짜 형식 처리
            date_str = str(date_str).strip()
            
            # YYYY-MM-DD 형식
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                return date_str[:10]
            
            # YYYYMMDD 형식
            if re.match(r'\d{8}', date_str):
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            # 기타 형식은 현재 날짜 반환
            return datetime.now().strftime('%Y-%m-%d')
            
        except Exception:
            return datetime.now().strftime('%Y-%m-%d')
    
    def parse_number(self, num_str):
        """숫자 파싱"""
        try:
            return int(re.sub(r'[^\d]', '', str(num_str))) if num_str else 1
        except:
            return 1
    
    def get_job_attachments(self, job_idx):
        """채용공고 페이지에서 첨부파일 정보 크롤링"""
        if not job_idx:
            return {}
        
        try:
            # 채용공고 상세 페이지 URL
            detail_url = f"https://job.alio.go.kr/recruitview.do?idx={job_idx}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(detail_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 첨부파일 정보 추출
            attachments = {
                'announcement': None,      # 공고문 (A)
                'application': None,       # 입사지원서 (B) 
                'job_description': None,   # 직무기술서 (C)
                'others': [],              # 기타 첨부파일 (Z)
                'unavailable_reason': None # 미접수사유
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
                                    
                                    # 파일 유형 분류
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
                            elif '미접수사유' in category and len(cells) >= 2:
                                reason = file_cell.get_text(strip=True)
                                if reason:
                                    attachments['unavailable_reason'] = reason
                    
                    break  # 첫 번째 관련 테이블만 처리
            
            return attachments
            
        except Exception as e:
            print(f"⚠️ 첨부파일 정보 추출 실패 (idx: {job_idx}): {e}")
            return {}
    
    def extract_file_id(self, url):
        """URL에서 fileID 또는 fileNo 추출"""
        try:
            # fileNo= 형태 확인 (새로운 형태)
            if 'fileNo=' in url:
                start = url.find('fileNo=') + 7
                end = url.find('&', start)
                if end == -1:
                    return url[start:]
                return url[start:end]
            # fileID= 형태 확인 (기존 형태)
            elif 'fileID=' in url:
                start = url.find('fileID=') + 7
                end = url.find('&', start)
                if end == -1:
                    return url[start:]
                return url[start:end]
        except:
            pass
        return None
    
    def filter_recent_jobs(self, jobs, days=30):
        """최근 N일 이내 공고만 필터링"""
        if not jobs:
            return []
        
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_jobs = []
        
        for job in jobs:
            try:
                if job.get('reg_date'):
                    reg_date = datetime.strptime(job['reg_date'], '%Y-%m-%d')
                    end_date = datetime.strptime(job['end_date'], '%Y-%m-%d') if job.get('end_date') else datetime.now() + timedelta(days=30)
                    
                    # 30일 이내 등록 && 마감일이 지나지 않음
                    if reg_date >= cutoff_date and end_date >= datetime.now():
                        filtered_jobs.append(job)
            except Exception as e:
                print(f"⚠️ 날짜 필터링 오류: {e}")
                continue
        
        return filtered_jobs
    
    def save_to_firebase(self, jobs):
        """Firebase에 데이터 저장 (배치 최적화)"""
        if not self.db:
            print("❌ Firebase가 연결되지 않았습니다")
            return False
        
        if not jobs:
            print("📝 저장할 데이터가 없습니다")
            return True
        
        try:
            collection_ref = self.db.collection('recruitment_jobs')
            saved_count = 0
            updated_count = 0
            skipped_count = 0
            
            # 배치 처리 (Firestore 배치 제한: 500개)
            batch_size = 400  # 안전한 크기로 설정
            
            for i in range(0, len(jobs), batch_size):
                batch_jobs = jobs[i:i + batch_size]
                batch = self.db.batch()
                
                print(f"📦 배치 {i//batch_size + 1} 처리 중... ({len(batch_jobs)}건)")
                
                for job in batch_jobs:
                    job_idx = job['idx']
                    doc_ref = collection_ref.document(job_idx)
                    
                    # _update_attachments_only 플래그 제거 (저장시 불필요)
                    update_attachments_only = job.pop('_update_attachments_only', False)
                    
                    # 중복 체크 (캐시 활용)
                    if job_idx in self.existing_job_ids:
                        if update_attachments_only:
                            # 첨부파일 정보만 업데이트
                            update_data = {
                                'attachments': job.get('attachments'),
                                'updated_at': datetime.now().isoformat()
                            }
                            batch.update(doc_ref, update_data)
                            print(f"  📎 첨부파일만 업데이트: {job_idx}")
                        else:
                            # 전체 데이터 업데이트
                            job['updated_at'] = datetime.now().isoformat()
                            batch.update(doc_ref, job)
                        updated_count += 1
                    else:
                        # 새로운 데이터는 생성
                        job['created_at'] = datetime.now().isoformat()
                        job['updated_at'] = datetime.now().isoformat()
                        batch.set(doc_ref, job)
                        saved_count += 1
                        
                        # 캐시에 추가
                        self.existing_job_ids.add(job_idx)
                
                # 배치 커밋
                try:
                    batch.commit()
                    print(f"  ✅ 배치 {i//batch_size + 1} 저장 완료")
                    time.sleep(0.1)  # Firebase 부하 방지
                except Exception as batch_error:
                    print(f"  ❌ 배치 {i//batch_size + 1} 저장 실패: {batch_error}")
                    # 개별 저장으로 폴백
                    for job in batch_jobs:
                        try:
                            doc_ref = collection_ref.document(job['idx'])
                            if job['idx'] in self.existing_job_ids:
                                doc_ref.update(job)
                                updated_count += 1
                            else:
                                doc_ref.set(job)
                                saved_count += 1
                                self.existing_job_ids.add(job['idx'])
                        except:
                            skipped_count += 1
            
            print(f"✅ Firebase 저장 완료:")
            print(f"   - 신규 저장: {saved_count}건")
            print(f"   - 업데이트: {updated_count}건")
            if skipped_count > 0:
                print(f"   - 실패/스킵: {skipped_count}건")
            
            return True
            
        except Exception as e:
            print(f"❌ Firebase 저장 실패: {e}")
            return False
    
    def get_collection_stats(self):
        """Firebase 컬렉션 통계 조회"""
        if not self.db:
            return None
        
        try:
            collection_ref = self.db.collection('recruitment_jobs')
            
            # 전체 문서 수
            total_docs = len(list(collection_ref.stream()))
            
            # 활성 상태 문서 수
            active_docs = len(list(collection_ref.where('status', '==', 'active').stream()))
            
            # 최근 업데이트된 문서 수 (오늘)
            today = datetime.now().date().isoformat()
            today_updated = len(list(
                collection_ref.where('updated_at', '>=', today).stream()
            ))
            
            return {
                'total': total_docs,
                'active': active_docs,
                'today_updated': today_updated
            }
            
        except Exception as e:
            print(f"⚠️ 통계 조회 실패: {e}")
            return None
    
    def collect_and_save(self, max_pages=10):
        """데이터 수집 및 저장 (중복 제거 포함)"""
        print("🚀 공공기관 채용정보 수집 시작")
        print(f"📋 기존 데이터 {len(self.existing_job_ids)}건 확인됨")
        
        all_jobs = []
        new_jobs_count = 0
        duplicate_count = 0
        page = 1
        consecutive_duplicates = 0  # 연속 중복 카운터
        
        while page <= max_pages:
            print(f"\n📄 페이지 {page} 처리 중...")
            
            jobs_data, total_count = self.fetch_job_data(num_rows=100, page_no=page)
            
            if not jobs_data:
                print("📭 더 이상 가져올 데이터가 없습니다")
                break
            
            # 데이터 처리 및 중복 체크
            processed_jobs = []
            page_new_count = 0
            page_duplicate_count = 0
            
            for job_data in jobs_data:
                # 기본 처리
                processed_job = self.clean_and_process_job(job_data)
                if not processed_job:
                    continue
                
                job_idx = processed_job['idx']
                
                # 중복 체크 및 첨부파일 정보 업데이트 체크
                if self.is_job_exists(job_idx):
                    # 기존 데이터에 첨부파일 정보가 있는지 확인
                    needs_attachment_update = self.needs_attachment_update(job_idx)
                    
                    if not needs_attachment_update:
                        duplicate_count += 1
                        page_duplicate_count += 1
                        print(f"  ⚠️ 중복 스킵: {job_idx} - {processed_job.get('title', 'No Title')[:30]}...")
                        continue
                    else:
                        print(f"  🔄 첨부파일 업데이트: {job_idx} - {processed_job.get('title', 'No Title')[:30]}...")
                        # 첨부파일 정보만 업데이트하는 경우로 표시
                        processed_job['_update_attachments_only'] = True
                
                # 새로운 데이터
                processed_jobs.append(processed_job)
                new_jobs_count += 1
                page_new_count += 1
                
                # 캐시에 추가 (다음 페이지에서 중복 체크할 수 있도록)
                self.add_to_cache(job_idx)
            
            print(f"✅ 페이지 {page} 결과: 신규 {page_new_count}건, 중복 {page_duplicate_count}건")
            
            # 전체 페이지가 중복이면 수집 중단 (효율성)
            if page_duplicate_count == len(jobs_data) and len(jobs_data) > 0:
                consecutive_duplicates += 1
                print(f"⚠️ 페이지 전체 중복 ({consecutive_duplicates}번째)")
                
                # 연속 3페이지가 모두 중복이면 수집 중단
                if consecutive_duplicates >= 3:
                    print("🛑 연속 중복 페이지가 많아 수집을 중단합니다")
                    break
            else:
                consecutive_duplicates = 0  # 중복이 아니면 카운터 리셋
            
            all_jobs.extend(processed_jobs)
            
            # 신규 데이터가 없으면 다음 페이지로 빠르게 이동
            if page_new_count == 0:
                time.sleep(0.5)  # 짧은 대기
            else:
                time.sleep(1)    # 정상 대기
                
            page += 1
        
        print(f"\n📊 수집 완료 통계:")
        print(f"   - 전체 처리: {new_jobs_count + duplicate_count}건")
        print(f"   - 신규 데이터: {new_jobs_count}건")
        print(f"   - 중복 스킵: {duplicate_count}건")
        
        if all_jobs:
            # 최근 30일 데이터만 필터링
            filtered_jobs = self.filter_recent_jobs(all_jobs, days=30)
            print(f"🔍 날짜 필터링: {len(filtered_jobs)}건 (전체 {len(all_jobs)}건)")
            
            if filtered_jobs:
                # Firebase에 저장
                if self.db:
                    self.save_to_firebase(filtered_jobs)
                
                # JSON 파일로도 백업 저장
                self.save_to_json(filtered_jobs)
            
            return filtered_jobs
        
        print("📝 신규 데이터가 없습니다")
        return []
    
    def save_to_json(self, jobs, filename=None):
        """JSON 파일로 저장"""
        if not filename:
            filename = f"recruitment_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'collected_at': datetime.now().isoformat(),
                    'total_count': len(jobs),
                    'jobs': jobs
                }, f, ensure_ascii=False, indent=2)
            
            print(f"💾 JSON 파일 저장 완료: {filename}")
            
        except Exception as e:
            print(f"❌ JSON 저장 실패: {e}")

def main():
    # API 키
    SERVICE_KEY = "1bmDITdGFoaDTSrbT6Uyz8bFdlIL3nydHgRu0xQtXO8SiHlCrOJKv+JNSythF12BiijhVB3qE96/4Jxr70zUNg=="
    
    # Firebase 키 파일 경로
    FIREBASE_KEY_PATH = "info-gov-firebase-adminsdk-9o52l-f6b59e8ae8.json"
    
    # 컬렉터 초기화
    collector = PublicJobCollector(SERVICE_KEY, FIREBASE_KEY_PATH)
    
    # 데이터 수집 및 저장
    jobs = collector.collect_and_save(max_pages=5)
    
    print(f"\n🎉 수집 완료! 총 {len(jobs)}건의 채용 정보를 처리했습니다.")

if __name__ == "__main__":
    main()