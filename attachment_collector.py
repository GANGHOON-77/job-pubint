# -*- coding: utf-8 -*-
import sys
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import time
import re

sys.stdout.reconfigure(encoding='utf-8')

class AttachmentCollector:
    """첨부파일 수집기"""
    
    def __init__(self, firebase_key_path):
        # Firebase 초기화
        if not firebase_admin._apps:
            cred = credentials.Certificate(firebase_key_path)
            firebase_admin.initialize_app(cred)
        
        self.db = firestore.client()
    
    def get_job_attachments(self, job_idx):
        """채용공고 페이지에서 첨부파일 정보 크롤링"""
        if not job_idx:
            return {}
        
        try:
            # 채용공고 상세 페이지 URL
            detail_url = f"https://job.alio.go.kr/recruitview.do?idx={job_idx}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(detail_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 첨부파일 정보 추출
            attachments = {
                'announcement': None,      # 공고문
                'application': None,       # 입사지원서
                'job_description': None,   # 직무기술서
                'others': [],              # 기타 첨부파일
                'unavailable_reason': None # 미접수사유
            }
            
            print(f"  🔍 {job_idx} 첨부파일 크롤링 중...")
            
            # 첨부파일 테이블 찾기
            tables = soup.find_all('table')
            for table in tables:
                table_text = table.get_text()
                if '첨부파일' in table_text or '공고문' in table_text or '지원서' in table_text:
                    rows = table.find_all('tr')
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            category_cell = cells[0]
                            file_cell = cells[1]
                            
                            category = category_cell.get_text(strip=True)
                            file_links = file_cell.find_all('a')
                            
                            # 파일 링크가 있는 경우
                            for file_link in file_links:
                                href = file_link.get('href', '')
                                file_name = file_link.get_text(strip=True)
                                
                                if 'fileNo=' in href or 'download' in href.lower():
                                    file_id = self.extract_file_id(href)
                                    
                                    if file_id:
                                        file_info = {
                                            'fileID': file_id,
                                            'name': file_name,
                                            'url': href
                                        }
                                        
                                        # 파일 유형 분류
                                        if '공고문' in category:
                                            attachments['announcement'] = file_info
                                            print(f"    📋 공고문: {file_name}")
                                        elif '입사지원서' in category or '지원서' in category:
                                            attachments['application'] = file_info
                                            print(f"    📝 입사지원서: {file_name}")
                                        elif '직무기술서' in category or '직무' in category:
                                            attachments['job_description'] = file_info
                                            print(f"    📄 직무기술서: {file_name}")
                                        elif '기타' in category or category == '' or len(category) < 3:
                                            attachments['others'].append(file_info)
                                            print(f"    📎 기타: {file_name}")
                                        else:
                                            attachments['others'].append(file_info)
                                            print(f"    📎 {category}: {file_name}")
                            
                            # 미접수사유 확인
                            if '미접수사유' in category or '미첨부' in category:
                                reason = file_cell.get_text(strip=True)
                                if reason and len(reason) > 3:
                                    attachments['unavailable_reason'] = reason
                                    print(f"    ❓ 미첨부사유: {reason}")
            
            # 첨부파일이 하나라도 있는지 확인
            has_files = (
                attachments['announcement'] or 
                attachments['application'] or 
                attachments['job_description'] or 
                attachments['others'] or 
                attachments['unavailable_reason']
            )
            
            if has_files:
                return attachments
            else:
                print(f"    ℹ️ 첨부파일 없음")
                return None
            
        except Exception as e:
            print(f"    ❌ 첨부파일 크롤링 실패: {e}")
            return None
    
    def extract_file_id(self, url):
        """URL에서 fileID 또는 fileNo 추출"""
        try:
            # fileNo= 형태 확인
            if 'fileNo=' in url:
                match = re.search(r'fileNo=([^&]+)', url)
                if match:
                    return match.group(1)
            
            # fileID= 형태 확인
            if 'fileID=' in url:
                match = re.search(r'fileID=([^&]+)', url)
                if match:
                    return match.group(1)
            
            # download 링크인 경우 전체 URL 반환
            if 'download' in url.lower():
                return url
                
        except Exception as e:
            print(f"    ⚠️ 파일 ID 추출 실패: {e}")
            
        return None
    
    def update_job_attachments(self, job_idx):
        """특정 공고의 첨부파일 정보를 Firebase에 업데이트"""
        try:
            # 첨부파일 정보 수집
            attachments = self.get_job_attachments(job_idx)
            
            if attachments:
                # Firebase 업데이트
                doc_ref = self.db.collection('jobs').document(str(job_idx))
                doc_ref.update({
                    'attachments': attachments,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                print(f"  ✅ Firebase 업데이트 완료: {job_idx}")
                return attachments
            else:
                print(f"  ℹ️ 업데이트할 첨부파일 없음: {job_idx}")
                return None
                
        except Exception as e:
            print(f"  ❌ Firebase 업데이트 실패 ({job_idx}): {e}")
            return None

    def check_missing_attachments(self, limit=50, offset=0):
        """첨부파일이 누락된 공고들 조회 (최신 30개만)"""
        try:
            print("🔍 첨부파일 누락 공고 검토 중...")
            
            # 공고 조회 (offset 적용)
            jobs_ref = self.db.collection('jobs').order_by('created_at', direction=firestore.Query.DESCENDING).offset(offset).limit(limit)
            docs = jobs_ref.stream()
            
            missing_jobs = []
            total_count = 0
            
            for doc in docs:
                total_count += 1
                job_data = doc.to_dict()
                job_idx = job_data.get('idx', doc.id)
                title = job_data.get('title', '제목없음')[:50]
                
                # 첨부파일 상태 확인
                attachments = job_data.get('attachments', {})
                
                has_attachments = (
                    attachments.get('announcement') or 
                    attachments.get('application') or 
                    attachments.get('job_description') or 
                    attachments.get('others', [])
                )
                
                unavailable_reason = attachments.get('unavailable_reason', '')
                collection_status = attachments.get('collection_status', '')
                
                # 누락된 경우 식별
                is_missing = False
                reason = ""
                
                if not attachments:
                    is_missing = True
                    reason = "첨부파일 데이터 없음"
                elif not has_attachments and not unavailable_reason:
                    is_missing = True
                    reason = "첨부파일 및 미첨부사유 없음"
                elif unavailable_reason == "Pending detailed collection":
                    is_missing = True
                    reason = "상세 수집 대기중"
                elif unavailable_reason == "Light collection mode":
                    is_missing = True
                    reason = "라이트 수집 모드"
                elif collection_status == "failed":
                    is_missing = True
                    reason = "수집 실패"
                elif not has_attachments and unavailable_reason and "파일 없음" in unavailable_reason:
                    # "파일 없음"이라고 되어있는 경우도 재검토
                    is_missing = True
                    reason = f"재검토 필요: {unavailable_reason}"
                
                if is_missing:
                    missing_jobs.append({
                        'idx': job_idx,
                        'title': title,
                        'reason': reason,
                        'created_at': job_data.get('created_at', ''),
                        'dept_name': job_data.get('dept_name', '')
                    })
                    print(f"  ❌ {job_idx}: {title} - {reason}")
                else:
                    print(f"  ✅ {job_idx}: {title}")
            
            print(f"\n📊 검토 결과:")
            print(f"  - 전체 검토: {total_count}개")
            print(f"  - 첨부파일 누락: {len(missing_jobs)}개")
            
            return missing_jobs
            
        except Exception as e:
            print(f"❌ 검토 실패: {e}")
            return []

    def batch_collect_attachments(self, job_ids):
        """누락된 공고들의 첨부파일 일괄 재수집"""
        print(f"🔄 {len(job_ids)}개 공고 첨부파일 재수집 시작...")
        print("=" * 60)
        
        success_count = 0
        fail_count = 0
        
        for i, job_idx in enumerate(job_ids, 1):
            print(f"\n[{i}/{len(job_ids)}] 📋 공고 {job_idx} 처리 중...")
            
            try:
                # 2초 지연 (서버 부하 방지)
                if i > 1:
                    time.sleep(2)
                
                result = self.update_job_attachments(job_idx)
                
                if result:
                    success_count += 1
                    print(f"  ✅ 성공: {job_idx}")
                else:
                    fail_count += 1
                    print(f"  ❌ 실패: {job_idx} - 첨부파일 없음")
                    
            except Exception as e:
                fail_count += 1
                print(f"  ❌ 오류: {job_idx} - {e}")
        
        print(f"\n📊 재수집 완료:")
        print(f"  ✅ 성공: {success_count}개")
        print(f"  ❌ 실패: {fail_count}개")
        print(f"  📈 성공률: {(success_count/(success_count+fail_count)*100):.1f}%")

    def check_specific_jobs(self, job_ids):
        """특정 공고들의 첨부파일 상태 확인"""
        print(f"🔍 지정된 {len(job_ids)}개 공고 첨부파일 상태 확인")
        print("=" * 60)
        
        for job_idx in job_ids:
            try:
                print(f"\n📋 공고 {job_idx} 확인 중...")
                
                # Firebase에서 해당 공고 조회
                doc_ref = self.db.collection('jobs').document(str(job_idx))
                doc = doc_ref.get()
                
                if not doc.exists:
                    print(f"  ❌ Firebase에 {job_idx} 공고가 없습니다")
                    continue
                
                job_data = doc.to_dict()
                title = job_data.get('title', '제목없음')
                dept_name = job_data.get('dept_name', '기관명없음')
                
                print(f"  제목: {title}")
                print(f"  기관: {dept_name}")
                
                # 첨부파일 상태 확인
                attachments = job_data.get('attachments', {})
                
                if not attachments:
                    print(f"  ❌ 첨부파일 데이터 없음")
                    continue
                
                has_attachments = (
                    attachments.get('announcement') or 
                    attachments.get('application') or 
                    attachments.get('job_description') or 
                    attachments.get('others', [])
                )
                
                unavailable_reason = attachments.get('unavailable_reason', '')
                collection_status = attachments.get('collection_status', '')
                
                print(f"  📎 첨부파일 상태:")
                
                if attachments.get('announcement'):
                    print(f"    ✅ 공고문: {attachments['announcement']['name']}")
                else:
                    print(f"    ❌ 공고문: 없음")
                
                if attachments.get('application'):
                    print(f"    ✅ 입사지원서: {attachments['application']['name']}")
                else:
                    print(f"    ❌ 입사지원서: 없음")
                
                if attachments.get('job_description'):
                    print(f"    ✅ 직무기술서: {attachments['job_description']['name']}")
                else:
                    print(f"    ❌ 직무기술서: 없음")
                
                if attachments.get('others'):
                    print(f"    ✅ 기타파일: {len(attachments['others'])}개")
                    for other in attachments['others']:
                        print(f"      - {other['name']}")
                else:
                    print(f"    ❌ 기타파일: 없음")
                
                if unavailable_reason:
                    print(f"    ❓ 미첨부사유: {unavailable_reason}")
                
                if collection_status:
                    print(f"    📊 수집상태: {collection_status}")
                
                # 누락 여부 판단
                is_missing = False
                
                if not has_attachments and not unavailable_reason:
                    is_missing = True
                    print(f"  🚨 상태: 첨부파일 누락")
                elif unavailable_reason in ["Pending detailed collection", "Light collection mode"]:
                    is_missing = True
                    print(f"  🚨 상태: 재수집 필요")
                elif collection_status == "failed":
                    is_missing = True
                    print(f"  🚨 상태: 수집 실패")
                else:
                    print(f"  ✅ 상태: 정상")
                
            except Exception as e:
                print(f"  ❌ 확인 실패: {e}")

if __name__ == "__main__":
    import os
    from datetime import datetime
    
    # 환경변수에서 Firebase 키 경로 가져오기 (GitHub Actions용)
    firebase_key_path = os.getenv('FIREBASE_KEY_PATH', "C:\\Users\\hoon7\\PycharmProjects\\public_int\\버전1.5_확정_20250906\\파이어베이스 인증\\job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
    
    collector = AttachmentCollector(firebase_key_path)
    
    # 오늘 날짜 기준으로 게시글 검색
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"🔍 {today} 등록일 게시글 첨부파일 누락 여부 검토")
    print("=" * 60)
    
    try:
        # reg_date로 오늘 게시글 검색
        jobs_ref = collector.db.collection('jobs').where('reg_date', '==', today)
        docs = jobs_ref.stream()
        
        today_jobs = []
        total_count = 0
        
        for doc in docs:
            total_count += 1
            job_data = doc.to_dict()
            job_idx = job_data.get('idx', doc.id)
            title = job_data.get('title', '제목없음')
            dept_name = job_data.get('dept_name', '기관명없음')
            
            # 첨부파일 상태 확인
            attachments = job_data.get('attachments', {})
            has_attachments = (
                attachments.get('announcement') or 
                attachments.get('application') or 
                attachments.get('job_description') or 
                attachments.get('others', [])
            )
            unavailable_reason = attachments.get('unavailable_reason', '')
            
            # 누락된 경우 판단
            is_missing = False
            reason = ""
            
            if not attachments:
                is_missing = True
                reason = "첨부파일 데이터 없음"
            elif not has_attachments and not unavailable_reason:
                is_missing = True
                reason = "첨부파일 및 미첨부사유 없음"
            elif unavailable_reason in ["Pending detailed collection", "Light collection mode"]:
                is_missing = True
                reason = "재수집 필요"
            elif unavailable_reason and "Request failed with status code 404" in unavailable_reason:
                is_missing = True
                reason = "404 오류 - 재수집 필요"
            elif unavailable_reason and "Attachment collection failed" in unavailable_reason:
                is_missing = True
                reason = "수집 실패 - 재수집 필요"
            
            today_jobs.append({
                'idx': job_idx,
                'title': title,
                'dept_name': dept_name,
                'is_missing': is_missing,
                'reason': reason,
                'reg_date': job_data.get('reg_date', '')
            })
            
            status = "❌" if is_missing else "✅"
            print(f"  {status} {job_idx}: {title[:50]} - {dept_name}")
            if is_missing:
                print(f"     사유: {reason}")
        
        print(f"\n📊 {today} 등록 게시글 통계:")
        print(f"  - 전체 게시글: {total_count}개")
        
        missing_jobs = [job for job in today_jobs if job['is_missing']]
        if missing_jobs:
            print(f"  - 첨부파일 누락: {len(missing_jobs)}개")
            print(f"  - 누락률: {(len(missing_jobs)/total_count*100):.1f}%")
            
            print(f"\n🎯 누락된 게시글 목록:")
            for i, job in enumerate(missing_jobs, 1):
                print(f"  {i}. [{job['idx']}] {job['title'][:50]}...")
                print(f"     기관: {job['dept_name']}")
                print(f"     사유: {job['reason']}")
                print()
            
            print(f"\n🚀 {len(missing_jobs)}개 공고 첨부파일 수집을 시작합니다...")
            missing_job_ids = [job['idx'] for job in missing_jobs]
            collector.batch_collect_attachments(missing_job_ids)
        else:
            print(f"  - 첨부파일 누락: 0개")
            print(f"\n✅ {today} 등록 게시글의 첨부파일이 모두 정상입니다!")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("reg_date 기준 검색에 실패했습니다.")