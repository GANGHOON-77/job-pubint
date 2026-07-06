#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firestore의 활성 채용공고를 기반으로 크롤러가 읽을 수 있는 정적 상세 페이지(jobs/{idx}/index.html)와
sitemap.xml을 생성한다. GitHub Actions에서 auto_update_jobs.py 실행 뒤 호출되어 결과물을 커밋한다.
"""

import os
import json
import shutil
import logging
from datetime import datetime, timedelta, timezone

import firebase_admin
from firebase_admin import credentials, firestore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SITE_URL = "https://public-job.co.kr"
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(REPO_ROOT, "jobs")
SITEMAP_PATH = os.path.join(REPO_ROOT, "sitemap.xml")
KST = timezone(timedelta(hours=9))

STATIC_PAGES = [
    ("/", "daily", "1.0"),
    ("/about.html", "monthly", "0.8"),
    ("/guide-apply-tips.html", "monthly", "0.6"),
    ("/guide-howto.html", "monthly", "0.6"),
    ("/contact.html", "monthly", "0.5"),
    ("/privacy.html", "yearly", "0.3"),
    ("/terms.html", "yearly", "0.3"),
]

EMPLOYMENT_TYPE_SCHEMA = {
    '정규직': 'FULL_TIME',
    '계약직': 'CONTRACTOR',
    '무기계약직': 'FULL_TIME',
    '비정규직': 'TEMPORARY',
    '청년인턴': 'INTERN',
    '청년인턴(체험형)': 'INTERN',
    '청년인턴(채용형)': 'INTERN',
}


def init_firestore():
    """auto_update_jobs.py와 동일한 우선순위로 Firebase 인증 정보를 로드한다."""
    if firebase_admin._apps:
        return firestore.client()

    local_override = os.getenv('LOCAL_FIREBASE_CRED_PATH')
    firebase_cred = os.getenv('FIREBASE_CREDENTIALS')

    if local_override:
        cred = credentials.Certificate(local_override)
        logger.info("로컬 지정 경로의 인증 정보 사용")
    elif firebase_cred:
        with open('/tmp/firebase_key_static.json', 'w') as f:
            f.write(firebase_cred)
        cred = credentials.Certificate('/tmp/firebase_key_static.json')
        logger.info("GitHub Actions 환경변수 인증 정보 사용")
    else:
        cred = credentials.Certificate(
            "파이어베이스 인증/job-pubint-firebase-adminsdk-fbsvc-1c4c2dbd08.json"
        )
        logger.info("기본 로컬 경로 인증 정보 사용")

    firebase_admin.initialize_app(cred)
    return firestore.client()


def esc(value):
    if value is None:
        return ''
    return (str(value)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def format_detail_content(text):
    if not text or not str(text).strip():
        return '<p>상세 내용은 원문 공고를 참고해 주세요.</p>'
    lines = [esc(line) for line in str(text).split('\n') if line.strip()]
    return ''.join(f'<p>{line}</p>' for line in lines)


def build_content_sections(job):
    """qualification/detail_content를 본문으로, procedure를 겹치지 않을 때만 별도 섹션으로 추가."""
    main_text = job.get('detail_content') or job.get('qualification') or job.get('preference')
    html = '<h2 style="font-size:18px; margin-bottom:10px; color:#1e293b;">상세 내용</h2>'
    html += format_detail_content(main_text)

    procedure = (job.get('procedure') or '').strip()
    if procedure and (not main_text or procedure[:40] not in main_text):
        html += '<h2 style="font-size:18px; margin:24px 0 10px; color:#1e293b;">전형절차</h2>'
        html += format_detail_content(procedure)

    return html


def normalize_job(doc_id, data):
    """홈페이지(index.html)의 Firestore 필드 fallback 로직과 동일하게 정규화한다.
    실제 운영 데이터는 auto_update_jobs.py 스키마(dept_name 등)가 아니라
    company/location/job_type/recruit_count/qualification/url 스키마로 저장되어 있다."""
    job = dict(data)
    job['idx'] = doc_id
    job['dept_name'] = data.get('dept_name') or data.get('company') or '기관명 없음'
    job['work_region'] = data.get('work_region') or data.get('location') or '지역 정보 없음'
    job['employment_type'] = data.get('employment_type') or data.get('job_type') or '고용형태 정보 없음'
    job['recruit_num'] = data.get('recruit_num') or data.get('recruit_count') or 1
    job['recruit_type'] = data.get('recruit_type') or data.get('ncs_name') or '채용구분 정보 없음'
    job['education'] = data.get('education') or '학력무관'
    reg_date = data.get('reg_date', '')
    end_date = data.get('end_date', '')
    job['recruit_period'] = data.get('recruit_period') or f"{reg_date} ~ {end_date}"
    job['detail_content'] = data.get('detail_content') or data.get('qualification')
    return job


def source_url(job):
    for key in ('url', 'src_url'):
        val = (job.get(key) or '').strip()
        if val:
            return val
    idx = job.get('idx', '')
    return f"https://job.alio.go.kr/recruitview.do?idx={idx}"


def build_job_json_ld(job, page_url):
    schema_employment = EMPLOYMENT_TYPE_SCHEMA.get(job.get('employment_type', ''), 'OTHER')
    valid_through = job.get('end_date')
    data = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": job.get('title', ''),
        "description": (job.get('detail_content') or job.get('qualification') or job.get('preference') or job.get('title', '')),
        "identifier": {
            "@type": "PropertyValue",
            "name": job.get('dept_name', ''),
            "value": job.get('idx', ''),
        },
        "datePosted": job.get('reg_date', ''),
        "employmentType": schema_employment,
        "hiringOrganization": {
            "@type": "Organization",
            "name": job.get('dept_name', ''),
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": job.get('work_region', ''),
                "addressCountry": "KR",
            },
        },
        "directApply": True,
        "url": page_url,
    }
    if valid_through:
        data["validThrough"] = f"{valid_through}T23:59:59+09:00"
    # 스크립트 태그 조기 종료 방지
    return json.dumps(data, ensure_ascii=False).replace('</', '<\\/')


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | 대한민국 공공일터 채용정보</title>
    <meta name="description" content="{description}">
    <meta name="robots" content="{robots}">
    <link rel="canonical" href="{canonical}">

    <meta property="og:title" content="{title} | 대한민국 공공일터 채용정보">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical}">
    <meta property="og:site_name" content="대한민국 공공일터 채용정보">

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;200;300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css" rel="stylesheet">

    <script type="application/ld+json">
    {json_ld}
    </script>

    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Pretendard Variable', 'Pretendard', -apple-system, BlinkMacSystemFont, 'Noto Sans KR', 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #f5f6fa 0%, #e8eaf0 100%);
            color: #2c3e50;
            line-height: 1.8;
            min-height: 100vh;
        }}
        .header {{ background: #ffffff; padding: 30px 0; border-bottom: 1px solid #e0e0e0; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
        .header-content {{ max-width: 900px; margin: 0 auto; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ font-size: 24px; font-weight: 700; color: #1565c0; }}
        .header a {{ color: #1565c0; text-decoration: none; font-weight: 600; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 40px 20px; }}
        .job-wrapper {{ background: white; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }}
        {closed_banner_style}
        h1.job-title {{ font-size: 28px; font-weight: 700; color: #1a202c; margin-bottom: 20px; }}
        .job-meta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; background: #f8fafc; border-radius: 12px; padding: 20px; margin-bottom: 30px; }}
        .job-meta div {{ font-size: 15px; color: #475569; }}
        .job-meta strong {{ color: #1e293b; }}
        .job-content {{ color: #334155; margin-bottom: 30px; }}
        .job-content p {{ margin-bottom: 12px; }}
        .source-link {{ display: inline-block; padding: 12px 22px; background: #1565c0; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; margin-right: 12px; }}
        .home-link {{ display: inline-block; padding: 12px 22px; background: #eef2f7; color: #1565c0; text-decoration: none; border-radius: 8px; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <h1>🏢 대한민국 공공일터 채용정보</h1>
            <a href="/">← 전체 채용정보 보기</a>
        </div>
    </div>
    <div class="container">
        <div class="job-wrapper">
            {closed_banner}
            <h1 class="job-title">{title}</h1>
            <div class="job-meta">
                <div><strong>기관명</strong><br>{dept_name}</div>
                <div><strong>근무지</strong><br>{work_region}</div>
                <div><strong>고용형태</strong><br>{employment_type}</div>
                <div><strong>채용구분</strong><br>{recruit_type}</div>
                <div><strong>모집인원</strong><br>{recruit_num}명</div>
                <div><strong>학력</strong><br>{education}</div>
                <div><strong>접수기간</strong><br>{recruit_period}</div>
            </div>
            <div class="job-content">
                {detail_content}
            </div>
            <a class="source-link" href="{source_url}" target="_blank" rel="noopener">원문 공고 바로가기 (첨부파일 포함)</a>
            <a class="home-link" href="/">전체 채용정보 목록</a>
        </div>
    </div>
</body>
</html>
"""

CLOSED_BANNER = (
    '<div style="background:#fef3c7; border-left:4px solid #f59e0b; padding:16px 20px; '
    'border-radius:8px; margin-bottom:24px; color:#92400e; font-weight:600;">'
    '⚠️ 마감된 채용공고입니다. 접수기간이 종료되어 더 이상 지원할 수 없습니다.</div>'
)


def render_job_page(job, closed=False):
    idx = job.get('idx', '')
    canonical = f"{SITE_URL}/jobs/{idx}/"
    title = esc(job.get('title', '제목 없음'))
    dept_name = esc(job.get('dept_name', '-'))
    description = esc(f"{job.get('dept_name', '')} - {job.get('title', '')} | {job.get('work_region', '')} {job.get('employment_type', '')} 채용공고")[:150]

    return PAGE_TEMPLATE.format(
        title=title,
        description=description,
        robots="noindex, follow" if closed else "index, follow",
        canonical=canonical,
        json_ld=build_job_json_ld(job, canonical),
        closed_banner_style="",
        closed_banner=CLOSED_BANNER if closed else "",
        dept_name=dept_name,
        work_region=esc(job.get('work_region', '-')),
        employment_type=esc(job.get('employment_type', '-')),
        recruit_type=esc(job.get('recruit_type', '-')),
        recruit_num=esc(job.get('recruit_num', 1)),
        education=esc(job.get('education', '-')),
        recruit_period=esc(job.get('recruit_period', '-')),
        detail_content=build_content_sections(job) if not closed else format_detail_content(None),
        source_url=esc(source_url(job)),
    )


def load_active_jobs(db):
    docs = db.collection('jobs').where('status', '==', 'active').stream()
    jobs = []
    skipped = []
    for doc in docs:
        data = doc.to_dict()
        # 나라일터 API의 실제 공고 idx(recrutPblntSn)는 항상 숫자다.
        # "test_001" 같은 테스트/더미 문서가 정적 페이지·sitemap에 노출되는 것을 막는다.
        if not str(doc.id).isdigit():
            skipped.append(doc.id)
            continue
        jobs.append(normalize_job(doc.id, data))
    if skipped:
        logger.warning(f"숫자가 아닌 idx 문서 {len(skipped)}건 제외 (테스트/더미 데이터로 추정): {skipped}")
    return jobs


def write_job_pages(jobs):
    os.makedirs(JOBS_DIR, exist_ok=True)
    active_ids = set()

    for job in jobs:
        idx = job.get('idx')
        if not idx:
            continue
        active_ids.add(str(idx))
        job_dir = os.path.join(JOBS_DIR, str(idx))
        os.makedirs(job_dir, exist_ok=True)
        with open(os.path.join(job_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(render_job_page(job, closed=False))

    # 만료(30일 경과, Firestore에서 이미 삭제됨)된 페이지는 지우지 않고
    # "마감됨" 배너를 추가해 이미 색인/공유된 링크가 깨지지 않도록 유지한다.
    if os.path.isdir(JOBS_DIR):
        for existing_idx in os.listdir(JOBS_DIR):
            if existing_idx in active_ids:
                continue
            job_file = os.path.join(JOBS_DIR, existing_idx, 'index.html')
            if not os.path.isfile(job_file):
                continue
            with open(job_file, 'r', encoding='utf-8') as f:
                content = f.read()
            if '마감된 채용공고입니다' in content:
                continue  # 이미 마감 처리됨
            closed_job = {'idx': existing_idx, 'title': '마감된 채용공고'}
            with open(job_file, 'w', encoding='utf-8') as f:
                f.write(render_job_page(closed_job, closed=True))
            logger.info(f"만료 처리: jobs/{existing_idx}")

    logger.info(f"채용공고 정적 페이지 {len(active_ids)}건 생성 완료")
    return active_ids


def write_sitemap(active_ids):
    now = datetime.now(KST).strftime('%Y-%m-%d')
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    for path, freq, priority in STATIC_PAGES:
        lines.append('  <url>')
        lines.append(f'    <loc>{SITE_URL}{path}</loc>')
        lines.append(f'    <lastmod>{now}</lastmod>')
        lines.append(f'    <changefreq>{freq}</changefreq>')
        lines.append(f'    <priority>{priority}</priority>')
        lines.append('  </url>')

    for idx in sorted(active_ids):
        lines.append('  <url>')
        lines.append(f'    <loc>{SITE_URL}/jobs/{idx}/</loc>')
        lines.append(f'    <lastmod>{now}</lastmod>')
        lines.append('    <changefreq>weekly</changefreq>')
        lines.append('    <priority>0.7</priority>')
        lines.append('  </url>')

    lines.append('</urlset>')

    with open(SITEMAP_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    logger.info(f"sitemap.xml 재생성 완료 ({len(STATIC_PAGES) + len(active_ids)}개 URL)")


def main():
    db = init_firestore()
    jobs = load_active_jobs(db)
    logger.info(f"활성 채용공고 {len(jobs)}건 로드")
    active_ids = write_job_pages(jobs)
    write_sitemap(active_ids)


if __name__ == "__main__":
    main()
