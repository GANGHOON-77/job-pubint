# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import firebase_admin
from firebase_admin import credentials, firestore

# Firebase 초기화
cred = credentials.Certificate("job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# 기존 데이터 하나 업데이트
def update_sample_job():
    # idx가 290214인 job 데이터 가져오기
    docs = db.collection('recruitment_jobs').where('idx', '==', '290214').limit(1).stream()
    
    for doc in docs:
        job_data = doc.to_dict()
        job_id = doc.id
        
        # 상세 내용 생성
        detailed_content = f"""채용자격
{job_data.get('detail_content', '자격요건 정보 없음')}

경력사유
채용구분: {job_data.get('recruit_type', '정보없음')}
근무분야: {job_data.get('work_field', '정보없음')}
학력요건: {job_data.get('education', '정보없음')}

우리내용
우대조건: {job_data.get('preference', '별도 우대조건 없음')}
채용인원: {job_data.get('recruit_num', '0')}명
급여정보: {job_data.get('salary_info', '회사내규에 따름')}

전형절차/방법
근무지역: {job_data.get('work_region', '정보없음')}
고용형태: {job_data.get('employment_type', '정보없음')}
접수기간: {job_data.get('recruit_period', '정보없음')}

접수방법 및 문의처
채용기관: {job_data.get('dept_name', '정보없음')}
원본 공고: {job_data.get('src_url', '정보없음')}"""
        
        # 업데이트
        db.collection('recruitment_jobs').document(job_id).update({
            'detail_content': detailed_content
        })
        
        print(f"업데이트 완료: {job_data.get('title', '제목없음')}")
        print(f"상세내용 미리보기: {detailed_content[:200]}...")
        break

if __name__ == "__main__":
    update_sample_job()