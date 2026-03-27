"""
OSMU 에이전시 시스템
─────────────────────────────────────────────────────────
조직 구조:
  CMO        ← 스케줄링 · 배포
  └─ 팀장    ← SEO·기획 · 최종검수
     ├─ 팀원1 ← 블로그
     ├─ 팀원2 ← 텍스트형 SNS (링크드인·쓰레드)
     ├─ 팀원3 ← 이미지형 SNS (인스타·페이스북)
     └─ 팀원4 ← 영상 (YouTube·TikTok)
"""

import uuid, asyncio, json as jl, re, os
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field


# ════════════════════════════════════════════════════════
#  공유 데이터 모델 (AgencyJob)
# ════════════════════════════════════════════════════════

class CMOSchedule(BaseModel):
    platforms:    list[str] = []          # ["tistory","linkedin","instagram"]
    days:         list[str] = []          # ["mon","wed","fri"]
    time:         str       = "14:00"
    date_start:   str       = ""          # "2026-03-01"
    date_end:     str       = ""          # "2026-03-31"
    total_posts:  int       = 0           # 계산값

class WeeklyBrief(BaseModel):
    week:         int       = 1
    topic:        str       = ""
    keywords:     list[str] = []
    angle:        str       = ""
    target:       str       = ""

class LeadPlan(BaseModel):
    total_weeks:  int               = 0
    total_posts:  int               = 0
    briefs:       list[WeeklyBrief] = []

class ReviewResult(BaseModel):
    status:       str       = "pending"   # pending | approved | rejected
    feedback:     str       = ""
    retry_count:  int       = 0


# ── 팀장 교차검증 결과 ─────────────────────────────────────────
class MemberReviewDetail(BaseModel):
    """팀원 1명에 대한 팀장 검수 결과"""
    member:             str       = ""        # blog | sns_text | sns_image | video
    status:             str       = "pending" # approved | rejected
    seo_score:          int       = 0         # SEO 키워드 반영도 0~100
    consistency_check:  str       = ""        # 블로그·브리프와의 일관성 평가
    platform_fit:       str       = ""        # 플랫폼 특성 반영 여부
    issues:             list[str] = []        # 발견된 구체적 문제점
    feedback:           str       = ""        # 팀원에게 전달할 수정 지시

class FilterResult(BaseModel):
    """팀장 마스터 체크리스트 — 개별 필터 결과"""
    filter_name:  str       = ""    # data_sync | platform_fit | brand_identity | technical_ready
    status:       str       = "pass"  # pass | warning | fail
    score:        int       = 0       # 0~100
    findings:     list[str] = []      # 발견된 항목 목록
    action_items: list[str] = []      # 수정 지시 사항
    summary:      str       = ""      # 1문장 요약

class LeadCrossReview(BaseModel):
    """팀장 교차검증 전체 결과 (채널 간 일관성 + 팀원별 검수 통합)"""
    status:             str                    = "pending"  # pending | all_approved | partial_rejected
    cross_consistency:  str                    = ""         # 채널 간 메시지 모순 여부
    keyword_coverage:   str                    = ""         # SEO 키워드 전 채널 반영 여부
    member_reviews:     list[MemberReviewDetail] = []       # 팀원별 상세 검수
    filter_results:     list[FilterResult]     = []         # 4-필터 마스터 체크리스트
    overall_feedback:   str                    = ""         # 팀장 종합 코멘트
    retry_count:        int                    = 0


# ── CMO 교차검증 결과 ──────────────────────────────────────────
class CMOApproval(BaseModel):
    """CMO가 팀장 플랜을 교차검증한 결과"""
    status:                str  = "pending"   # pending | approved | revision_required
    brand_alignment:       str  = ""          # 브랜드 정체성 부합도 평가
    kpi_alignment:         str  = ""          # KPI 기여도 평가
    feedback:              str  = ""          # 전체 총평
    revision_instructions: str  = ""          # 수정 지시사항 (revision_required 시)
    retry_count:           int  = 0


class AgencyJob(BaseModel):
    job_id:         str                     = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    status:         str                     = "pending"   # pending|running|reviewing|done|failed
    current_step:   str                     = ""
    created_at:     str                     = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at:     str                     = Field(default_factory=lambda: datetime.now().isoformat())

    # 입력
    agency_profile: dict                    = {}
    api_keys:       dict                    = {}

    # CMO — 스케줄 + 교차검증
    cmo_schedule:   Optional[CMOSchedule]    = None
    cmo_approval:   Optional[CMOApproval]    = None   # 팀장 플랜 최종 컨펌

    # 팀장 — 기획 + 교차검증
    lead_plan:         Optional[LeadPlan]        = None
    lead_cross_review: Optional[LeadCrossReview] = None  # 팀원 교차검증 결과

    # 팀원 결과물 (주차별 리스트)
    blog_contents:      list[dict]          = []
    sns_text_contents:  list[dict]          = []
    sns_image_contents: list[dict]          = []
    video_contents:     list[dict]          = []

    # 검수 현황
    reviews: dict[str, ReviewResult] = {
        "blog":      ReviewResult(),
        "sns_text":  ReviewResult(),
        "sns_image": ReviewResult(),
        "video":     ReviewResult(),
    }

    # 팀원 간 교차 검증 결과 (Cross-Check Matrix)
    cross_check_results: list[dict]         = []   # 주차별 교차 검증 결과

    # 최종 배포 스케줄
    deploy_schedule: list[dict]             = []

    # 오류
    error: Optional[str]                    = None


# ════════════════════════════════════════════════════════
#  인메모리 Job 저장소
# ════════════════════════════════════════════════════════

_JOBS: dict[str, AgencyJob] = {}

def get_job(job_id: str) -> Optional[AgencyJob]:
    return _JOBS.get(job_id)

def save_job(job: AgencyJob):
    job.updated_at = datetime.now().isoformat()
    _JOBS[job.job_id] = job

def list_jobs() -> list[AgencyJob]:
    return sorted(_JOBS.values(), key=lambda j: j.created_at, reverse=True)


# ════════════════════════════════════════════════════════
#  LLM 헬퍼 (Groq / Gemini)
# ════════════════════════════════════════════════════════

async def _groq(prompt: str, api_keys: dict, system: str = "당신은 전문 콘텐츠 마케터입니다.", model: str = "llama-3.3-70b-versatile") -> str:
    key = api_keys.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("Groq API 키 없음")
    from groq import Groq
    client = Groq(api_key=key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.5,
        max_tokens=4096,
    )
    return resp.choices[0].message.content or ""


async def _groq_json(prompt: str, api_keys: dict, model: str = "llama-3.3-70b-versatile", system: str = "") -> dict:
    raw = await _groq(
        prompt, api_keys,
        system=system or "당신은 전문 콘텐츠 마케터입니다. 반드시 유효한 JSON만 반환하세요. 코드블록·설명·주석 없이 순수 JSON만.",
        model=model,
    )
    for pat in (r'\{.*\}', r'\[.*\]'):
        m = re.search(pat, raw, re.DOTALL)
        if m:
            try:
                return jl.loads(m.group())
            except Exception:
                continue
    raise ValueError(f"JSON 파싱 실패: {raw[:200]}")


async def _gemini(prompt: str, api_keys: dict, model: str = "gemini-2.5-flash") -> str:
    key = api_keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise ValueError("Gemini API 키 없음")
    from google import genai
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(model=model, contents=prompt)
    return resp.text or ""


async def _gemini_json(prompt: str, api_keys: dict) -> dict:
    raw = await _gemini(prompt + "\n\n반드시 순수 JSON만 반환. 코드블록·설명 없이.", api_keys)
    for pat in (r'\{.*\}', r'\[.*\]'):
        m = re.search(pat, raw, re.DOTALL)
        if m:
            try:
                return jl.loads(m.group())
            except Exception:
                continue
    raise ValueError(f"JSON 파싱 실패: {raw[:200]}")


# ════════════════════════════════════════════════════════
#  에이전시 페르소나 정의
# ════════════════════════════════════════════════════════

# ── CMO 페르소나 ───────────────────────────────────────────────
CMO_PERSONA = """당신은 15년 차 마케팅 디렉터 CMO입니다.

역할:
- 프로젝트의 전체 방향성 설정 및 KPI 관리
- 팀장이 제출한 '주간 콘텐츠 플랜'이 브랜드의 장기 전략과 부합하는지 교차 검증
- 최종 컨펌(approved) 또는 수정 지시(revision_required)를 내림

성향:
- 데이터 기반의 의사결정을 중시함
- 브랜드 정체성을 엄격히 따짐
- 단기 성과보다 장기적 브랜드 자산 구축에 집중
- 구체적 수치(CTR, 전환율, 리드 수)로 성과를 측정

반드시 유효한 JSON만 반환하세요. 코드블록·설명·주석 없이 순수 JSON만."""


# ── 팀장 페르소나 ──────────────────────────────────────────────
LEAD_PERSONA = """당신은 꼼꼼하고 분석적인 마케팅 팀장입니다.

역할:
- 프로젝트 스케줄링 및 팀원 간 작업 조율 총괄
- 팀원 1~4가 작성한 초안을 수집하여 상호 모순이 없는지 확인
- SEO 키워드가 블로그·텍스트SNS·이미지SNS·영상 전 채널에 적절히 녹아들었는지 기술적 검수

성향:
- 꼼꼼하고 분석적 — 디테일 하나도 놓치지 않음
- SEO 키워드와 플랫폼별 성과 지표(CTR, 도달률, 참여율)에 민감
- 채널 간 메시지 일관성을 최우선으로 확인
- 팀원에게 구체적·실행 가능한 수정 지시를 내림

반드시 유효한 JSON만 반환하세요. 코드블록·설명·주석 없이 순수 JSON만."""


# ════════════════════════════════════════════════════════
#  STEP 1 — CMO: 배포 일정 계산
# ════════════════════════════════════════════════════════

DAY_MAP = {"mon":0,"tue":1,"wed":2,"thu":3,"fri":4,"sat":5,"sun":6}

def _calc_schedule(cmo: CMOSchedule) -> list[dict]:
    """날짜 범위 + 요일 설정으로 배포 날짜 목록 생성"""
    start = datetime.strptime(cmo.date_start, "%Y-%m-%d")
    end   = datetime.strptime(cmo.date_end,   "%Y-%m-%d")
    target_days = {DAY_MAP[d] for d in cmo.days if d in DAY_MAP}
    schedule = []
    cur = start
    while cur <= end:
        if cur.weekday() in target_days:
            schedule.append({
                "date": cur.strftime("%Y-%m-%d"),
                "time": cmo.time,
                "weekday": cur.strftime("%a").lower(),
            })
        cur += timedelta(days=1)
    return schedule


async def run_cmo_schedule(job: AgencyJob) -> AgencyJob:
    """CMO: 배포 일정 수립"""
    job.current_step = "cmo_schedule"
    cmo = job.cmo_schedule
    if not cmo:
        raise ValueError("CMO 스케줄 입력값 없음")

    dates = _calc_schedule(cmo)
    cmo.total_posts = len(dates)
    job.cmo_schedule = cmo

    # 배포 슬롯 초기화 (콘텐츠는 나중에 채움)
    job.deploy_schedule = [
        {**d, "platform": p, "content_ref": "", "status": "pending"}
        for d in dates
        for p in cmo.platforms
    ]
    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  STEP 2 — 팀장: SEO 기반 기획
# ════════════════════════════════════════════════════════

async def run_lead_plan(job: AgencyJob) -> AgencyJob:
    """팀장: 키워드 분석 → 주차별 주제·브리프 생성"""
    job.current_step = "lead_plan"

    cmo    = job.cmo_schedule
    prof   = job.agency_profile
    dates  = _calc_schedule(cmo)
    total  = len(dates)
    weeks  = max(1, (total + 2) // 3)   # 배포 횟수 기준 주차 계산

    prof_str = f"""
브랜드명: {prof.get('name','')}
업종: {prof.get('industry','')}
타겟: {prof.get('target','')}
톤앤매너: {prof.get('tone','')}
핵심 키워드: {prof.get('keywords','')}
서비스: {prof.get('services','')}
"""

    # CMO 수정 지시사항 있으면 플랜에 반영
    cmo_instruction = ""
    if job.cmo_approval and job.cmo_approval.revision_instructions:
        cmo_instruction = f"\n## CMO 수정 지시사항 (반드시 반영)\n{job.cmo_approval.revision_instructions}\n"

    prompt = f"""SEO를 기반으로 {weeks}주치 콘텐츠 기획을 작성하세요.{cmo_instruction}

## 브랜드 정보
{prof_str}

## 배포 설정
- 총 배포 횟수: {total}회
- 기간: {cmo.date_start} ~ {cmo.date_end}
- 플랫폼: {', '.join(cmo.platforms)}

## 요청
각 주차별로 검색량·경쟁도를 고려한 SEO 최적 주제를 설계하세요.
주제는 블로그 → 텍스트SNS → 이미지SNS → 영상 모두에 활용 가능해야 합니다.

JSON만 반환:
{{
  "total_weeks": {weeks},
  "total_posts": {total},
  "briefs": [
    {{
      "week": 1,
      "topic": "주제 (SEO 최적화된 제목 형태)",
      "keywords": ["키워드1", "키워드2", "키워드3"],
      "angle": "독자에게 전달할 핵심 관점·차별화 포인트",
      "target": "이 주제에 관심 있는 구체적인 독자"
    }}
  ]
}}"""

    data = await _gemini_json(prompt + "\n\n반드시 순수 JSON만 반환. " + LEAD_PERSONA.splitlines()[0], job.api_keys)
    job.lead_plan = LeadPlan(
        total_weeks=data.get("total_weeks", weeks),
        total_posts=data.get("total_posts", total),
        briefs=[WeeklyBrief(**b) for b in data.get("briefs", [])],
    )
    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  STEP 2.5 — CMO: 팀장 플랜 교차검증 + 최종 컨펌
# ════════════════════════════════════════════════════════

async def run_cmo_approve_plan(job: AgencyJob) -> AgencyJob:
    """
    CMO 교차검증 임무:
    팀장이 가져온 '주간 콘텐츠 플랜'이 브랜드 장기 전략과 맞는지 검토.
    - approved         → 팀원 콘텐츠 생성 단계로 진행
    - revision_required → 팀장에게 수정 지시 → 재기획
    """
    job.current_step = "cmo_approve_plan"

    if not job.lead_plan:
        raise ValueError("팀장 플랜이 없습니다. run_lead_plan 먼저 실행하세요.")

    prof = job.agency_profile
    cmo  = job.cmo_schedule

    # 주간 플랜 요약 (CMO 검토용)
    plan_summary = "\n".join([
        f"Week {b.week}: [{b.topic}] | 키워드: {', '.join(b.keywords)} | "
        f"앵글: {b.angle} | 타겟: {b.target}"
        for b in job.lead_plan.briefs
    ])

    retry_num = (job.cmo_approval.retry_count + 1) if job.cmo_approval else 1

    prompt = f"""## 브랜드 프로필
브랜드명: {prof.get('name', '미설정')}
업종: {prof.get('industry', '')}
핵심 가치 / 장기 전략: {prof.get('brand_strategy', prof.get('tone', '미설정'))}
타겟 고객: {prof.get('target', '')}
핵심 KPI: {prof.get('kpi', '리드 생성, 브랜드 인지도, 전환율')}
핵심 키워드: {prof.get('keywords', '')}

## 팀장 제출 주간 콘텐츠 플랜 (총 {job.lead_plan.total_weeks}주 / {job.lead_plan.total_posts}회)
{plan_summary}

## 배포 플랫폼
{', '.join(cmo.platforms if cmo else [])}

## CMO 검토 기준 (4가지)
1. 브랜드 정체성·톤앤매너와 각 주제가 일치하는가?
2. KPI(리드 생성·인지도·전환율) 달성에 실질적으로 기여하는가?
3. 장기 콘텐츠 전략과 일관된 흐름인가? (주차 간 연결성)
4. 타겟 고객의 구매 여정(인지→고려→결정)을 고르게 커버하는가?

{"[재검토 " + str(retry_num) + "차]" if retry_num > 1 else ""}

JSON만 반환:
{{
  "status": "approved 또는 revision_required",
  "brand_alignment": "브랜드 정체성 부합도 평가 (1~2문장, 구체적 근거 포함)",
  "kpi_alignment": "KPI 기여도 평가 (1~2문장, 수치 기준 언급)",
  "feedback": "CMO 전체 총평 (2~3문장, 잘된 점 + 우려사항)",
  "revision_instructions": "approved면 빈 문자열. revision_required면 팀장에게 전달할 구체적 수정 지시사항 (주차별 지적 포함)"
}}"""

    data = await _groq_json(prompt, job.api_keys, system=CMO_PERSONA)

    current_retry = job.cmo_approval.retry_count if job.cmo_approval else 0
    job.cmo_approval = CMOApproval(
        status=data.get("status", "revision_required"),
        brand_alignment=data.get("brand_alignment", ""),
        kpi_alignment=data.get("kpi_alignment", ""),
        feedback=data.get("feedback", ""),
        revision_instructions=data.get("revision_instructions", ""),
        retry_count=current_retry,
    )
    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  STEP 3 — 팀원 1: 블로그
# ════════════════════════════════════════════════════════

async def run_member_blog(job: AgencyJob) -> AgencyJob:
    """팀원1: 주차별 블로그 포스트 생성"""
    job.current_step = "member_blog"
    prof = job.agency_profile
    results = []

    for brief in job.lead_plan.briefs:
        prompt = f"""당신은 팀원 1 — SEO 에디터 "The Architect"입니다.

## 페르소나
매우 논리적이며 구조 중심적입니다. "문장이 예쁜 것보다 구글 로봇이 읽기 좋은 것"이 우선입니다.
전문 분야: 검색 엔진 최적화(SEO), 블로그·롱폼 아티클, 데이터 기반 글쓰기.
이 글은 다른 팀원(SNS·영상)이 변환할 원천 소스가 됩니다. 내용이 명확하고 풍부해야 합니다.

## 브랜드
- 이름: {prof.get('name','')}
- 톤앤매너: {prof.get('tone','')}
- 타겟: {brief.target}
- USP: {prof.get('usp','')}

## 이번 주 기획 (팀장 브리프)
- 주제: {brief.topic}
- 메인 키워드: {', '.join(brief.keywords)}
- 앵글: {brief.angle}

## The Architect 작성 규칙
1. H1: 메인 키워드 포함 제목 (클릭 유도 + SEO)
2. H2 3~4개: LSI(연관) 키워드 자연스럽게 배치
3. H3: 각 H2 아래 세부 항목 구조화
4. 키워드 밀도: 메인 키워드 2~3%, 연관 키워드 분산
5. 분량: 1,800~2,500자 (롱폼 우선)
6. 도입부: 검색 의도를 명확히 파악하는 문장으로 시작
7. 결론 + CTA: 다음 액션 명확하게 제시
8. Meta description: 검색 결과 클릭률(CTR) 최적화 (150자 이내)
9. 이미지 Alt 태그 가이드: 본문 내 이미지 위치에 [IMG: alt 텍스트] 형식으로 표시

JSON만 반환:
{{
  "week": {brief.week},
  "title": "H1 제목 — 메인 키워드 포함 (60자 이내)",
  "meta_description": "CTR 최적화 메타 설명 (150자 이내)",
  "lsi_keywords": ["연관키워드1","연관키워드2","연관키워드3"],
  "body": "## H2 소제목1\\n### H3 세부항목\\n본문...\\n[IMG: alt 텍스트]\\n\\n## H2 소제목2\\n본문...",
  "tags": ["태그1","태그2","태그3","태그4","태그5"],
  "internal_link_suggestion": "연관 포스팅 링크 앵커 텍스트 제안",
  "keyword_density_note": "메인 키워드 사용 위치 요약",
  "estimated_read_min": 8
}}"""

        data = await _groq_json(prompt, job.api_keys, system=MEMBER_SYSTEM_PROMPTS["blog"])
        results.append(data)

    job.blog_contents = results
    job.reviews["blog"] = ReviewResult(status="pending")
    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  STEP 3 — 팀원 2: 텍스트형 SNS
# ════════════════════════════════════════════════════════

async def run_member_sns_text(job: AgencyJob) -> AgencyJob:
    """팀원2: 블로그 기반 → 링크드인·쓰레드 변환"""
    job.current_step = "member_sns_text"
    prof = job.agency_profile
    results = []

    for i, brief in enumerate(job.lead_plan.briefs):
        blog = job.blog_contents[i] if i < len(job.blog_contents) else {}
        blog_body = str(blog.get("body", ""))[:800]

        prompt = f"""당신은 팀원 3 — 인사이트 분석가 "The Thought Leader"입니다.

## 페르소나
냉철하고 지적인 비즈니스 전문가. "좋아요"보다는 "공유"와 "권위"를 중요하게 생각하며,
업계 전문가의 어조를 유지합니다.
팀원 2(The Trendsetter)의 인스타 문구가 너무 가벼우면 "브랜드 신뢰도를 위해 이 단어는 지양하죠"라고 제동을 겁니다.
전문 분야: 링크드인, 쓰레드, 비즈니스 네트워킹.

## 원본 블로그 (팀원 1 작성)
제목: {blog.get('title', brief.topic)}
본문 일부: {blog_body}
LSI 키워드: {', '.join(blog.get('lsi_keywords', []))}

## 브랜드
- 톤앤매너: {prof.get('tone','')}
- 타겟: {brief.target}
- USP: {prof.get('usp','')}

## The Thought Leader 작성 규칙

### LinkedIn 아티클
- 첫 줄: "더보기" 버튼 전에 클릭을 유도하는 권위 있는 훅 (데이터·역설·전문 통찰 활용)
- 블로그 내용을 비즈니스 인사이트로 재가공(Repurposing) — 단순 요약 금지
- 전문 용어를 섞되 독자가 이해 가능한 수준 유지
- 오피니언 리더와의 논쟁·대화를 유도하는 질문을 말미에 배치
- 3,000자 이내, 단락 짧게 (모바일 가독성)
- CTA: 댓글 참여·의견 공유 유도 (좋아요 유도 금지)

### Threads 연작
- 핵심 인사이트 하나를 3~5개 연작 쓰레드로 구성
- 각 쓰레드: 500자 이내, 번호 붙이기 (1/5, 2/5...)
- 마지막 쓰레드: 논쟁 유도 질문 또는 의견 요청

### 검수 지표 (자체 체크)
- 통찰력 점수(Insight Score): 새로운 관점을 제공하는가?
- 전문 용어 적합성: 타겟 독자 수준에 맞는가?
- 논리적 완결성: 주장-근거-결론 구조가 명확한가?

JSON만 반환:
{{
  "week": {brief.week},
  "linkedin": {{
    "hook": "첫 줄 훅 — 권위·데이터·역설 활용 (60자 이내)",
    "body": "전체 아티클 본문 (3000자 이내)",
    "opinion_question": "말미 오피니언 유도 질문",
    "cta": "댓글 참여 유도 CTA",
    "repurposing_angle": "블로그에서 어떤 인사이트를 재가공했는지 요약"
  }},
  "threads": [
    {{"order": "1/5", "body": "첫 번째 쓰레드 (500자 이내)"}},
    {{"order": "2/5", "body": "두 번째 쓰레드"}},
    {{"order": "3/5", "body": "세 번째 쓰레드"}},
    {{"order": "4/5", "body": "네 번째 쓰레드"}},
    {{"order": "5/5", "body": "논쟁 유도 질문 쓰레드"}}
  ],
  "insight_score": "통찰력 자체 점수 (예: 8/10 — 업계 데이터 인용)",
  "term_fit_note": "전문 용어 적합성 체크 메모",
  "logic_check": "논리 완결성 자체 검수 결과"
}}"""

        data = await _groq_json(prompt, job.api_keys, system=MEMBER_SYSTEM_PROMPTS["sns_text"])
        results.append(data)

    job.sns_text_contents = results
    job.reviews["sns_text"] = ReviewResult(status="pending")
    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  STEP 3 — 팀원 3: 이미지형 SNS
# ════════════════════════════════════════════════════════

async def run_member_sns_image(job: AgencyJob) -> AgencyJob:
    """팀원3: 블로그 기반 → 인스타그램·페이스북 변환"""
    job.current_step = "member_sns_image"
    prof = job.agency_profile
    results = []

    for i, brief in enumerate(job.lead_plan.briefs):
        blog = job.blog_contents[i] if i < len(job.blog_contents) else {}

        prompt = f"""당신은 팀원 2 — 비주얼 전략가 "The Trendsetter"입니다.

## 페르소나
감각적이고 직관적입니다. 유행하는 밈(Meme)과 해시태그 트렌드에 밝으며,
사용자의 '멈춤(Scroll-stop)'을 유도하는 데 집착합니다.
팀원 1(The Architect)의 딱딱한 글을 받아 "이건 너무 지루해요, 감성 한 스푼 넣을게요"라며 톤앤매너를 조정합니다.
전문 분야: 인스타그램, 페이스북, 비주얼 스토리텔링.

## 원본 블로그 (팀원 1 작성)
제목: {blog.get('title', brief.topic)}
키워드: {', '.join(brief.keywords)}
LSI 키워드: {', '.join(blog.get('lsi_keywords', []))}

## 브랜드
- 톤앤매너: {prof.get('tone','')}
- 타겟: {brief.target}
- USP: {prof.get('usp','')}

## The Trendsetter 작성 규칙

### Instagram 캡션
- 첫 문장: 반드시 스크롤 멈춤(Scroll-stop) 훅 — 질문·충격·공감 중 하나
- 감성적·공감형 + 이모지 자연스럽게 활용
- 2,200자 이내, CTA: 저장·공유 유도
- 해시태그: 15~20개 (볼륨 대·중·소 믹스)

### Facebook 캡션
- 정보성·스토리 중심, 링크 첨부 전제
- 1,000자 이내, 해시태그 3~5개

### 카드뉴스 슬라이드 (6장)
- 표지: 시각적 훅 + 핵심 약속
- 2~5장: 핵심 포인트 (한 장 = 하나의 메시지)
- 마지막: 강력한 CTA + 저장 유도
- 각 슬라이드 이미지 AI 프롬프트 (DALL-E 3 스타일) 포함

### 검수 지표 (자체 체크)
- 첫 문장의 훅(Hook) 강도: 3초 안에 멈추게 하는가?
- 비주얼 일관성: 슬라이드 간 톤·스타일 통일
- 공유 유도 요소: 저장 이유가 명확한가?

JSON만 반환:
{{
  "week": {brief.week},
  "instagram": {{
    "hook": "첫 문장 훅 (스크롤 멈춤 유도)",
    "caption": "전체 캡션 (훅 포함)",
    "hashtags": ["#태그1","#태그2","#태그3"],
    "image_prompt": "DALL-E 3용 이미지 생성 프롬프트 (영문 또는 한국어)",
    "cta": "저장/공유 유도 문구"
  }},
  "facebook": {{
    "body": "페북 본문",
    "hashtags": ["#태그1","#태그2"],
    "link_preview_title": "링크 미리보기 제목"
  }},
  "cardnews": {{
    "slides": [
      {{"slide": 1, "type": "cover", "headline": "시각적 훅 제목", "sub": "서브 텍스트", "image_prompt": "표지 이미지 프롬프트"}},
      {{"slide": 2, "type": "problem", "headline": "문제 제기", "body": "공감 포인트", "image_prompt": "이미지 프롬프트"}},
      {{"slide": 3, "type": "point", "headline": "포인트 1", "body": "핵심 메시지", "image_prompt": "이미지 프롬프트"}},
      {{"slide": 4, "type": "point", "headline": "포인트 2", "body": "핵심 메시지", "image_prompt": "이미지 프롬프트"}},
      {{"slide": 5, "type": "point", "headline": "포인트 3", "body": "핵심 메시지", "image_prompt": "이미지 프롬프트"}},
      {{"slide": 6, "type": "cta", "headline": "마무리", "cta": "저장·공유 유도 행동 문구", "image_prompt": "이미지 프롬프트"}}
    ]
  }},
  "scroll_stop_score": "훅 강도 자체 평가 (예: 8/10 — 질문형 훅 사용)",
  "visual_consistency_note": "비주얼 일관성 체크 메모"
}}"""

        data = await _groq_json(prompt, job.api_keys, system=MEMBER_SYSTEM_PROMPTS["sns_image"])
        results.append(data)

    job.sns_image_contents = results
    job.reviews["sns_image"] = ReviewResult(status="pending")
    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  STEP 3 — 팀원 4: 영상
# ════════════════════════════════════════════════════════

async def run_member_video(job: AgencyJob) -> AgencyJob:
    """팀원4: 블로그 기반 → YouTube·TikTok 영상 대본 변환"""
    job.current_step = "member_video"
    prof = job.agency_profile
    results = []

    for i, brief in enumerate(job.lead_plan.briefs):
        blog = job.blog_contents[i] if i < len(job.blog_contents) else {}
        blog_body = str(blog.get("body", ""))[:1000]

        prompt = f"""당신은 팀원 4 — 멀티미디어 PD "The Viral Maker"입니다.

## 페르소나
에너지가 넘치고 속도감을 중시합니다. 시청 지속 시간(Retention) 그래프에 민감하며,
'결론부터 말하기'의 달인입니다.
팀원 1(The Architect)의 긴 글에서 가장 임팩트 있는 '3초'를 뽑아내어 영상화합니다.
전문 분야: 유튜브 쇼츠, 릴스, 틱톡, 영상 대본.

## 원본 블로그 (팀원 1 작성)
제목: {blog.get('title', brief.topic)}
본문: {blog_body}
내부 링크 제안: {blog.get('internal_link_suggestion', '')}

## 브랜드
- 이름: {prof.get('name','')}
- 톤앤매너: {prof.get('tone','')}
- USP: {prof.get('usp','')}

## The Viral Maker 작성 규칙

### YouTube 롱폼 대본
- 훅 (첫 15초): 결론 또는 가장 충격적인 사실 먼저 — Retention 그래프 하락 방지
- 인트로: "이 영상에서 배울 것" 명확히 약속
- 본론: 챕터 구분, 각 챕터 전환 시 "다음으로..." 브릿지 멘트
- 아웃트로: 구독·좋아요 + 다음 영상 예고 (연속 시청 유도)
- 구어체, 자연스럽게, 호흡 표시 포함 (/ 로 표시)
- 분량: 7~10분 (약 1,400~1,800자)
- 챕터별 B-roll 추천 포함

### 숏폼 대본 (YouTube Shorts / TikTok / 릴스)
- 첫 3초: 이탈 방지 오디오 훅 — 질문·충격·약속 중 하나
- 결론 먼저 → 이유 설명 → CTA 순서
- 60초 이내 (약 150~200자)
- 자막(SRT)용으로 짧은 문장 단위로 작성
- 편집자를 위한 컷 지시서 포함

### 검수 지표 (자체 체크)
- 초반 3초 이탈 방지 로직: 훅이 시청자를 붙잡는가?
- 자막 가독성: 한 줄 7자 이내, 화면에 1~2초 노출
- 행동 유도(CTA) 명확성: 구독·저장·댓글 중 하나만 명확하게

JSON만 반환:
{{
  "week": {brief.week},
  "youtube": {{
    "title": "YouTube SEO 제목 (60자, 키워드 포함)",
    "description": "영상 설명 (SEO 최적화, 첫 줄 훅 포함)",
    "tags": ["태그1","태그2","태그3","태그4","태그5"],
    "chapters": [
      {{"time": "00:00", "title": "챕터명", "broll": "B-roll 추천 장면"}}
    ],
    "script": {{
      "hook": "첫 15초 대본 (/ 로 호흡 표시)",
      "intro": "인트로 대본 — 이 영상에서 배울 것 약속",
      "body": "본론 대본 (챕터 구분, 브릿지 멘트 포함)",
      "outro": "아웃트로 — 구독 유도 + 다음 영상 예고"
    }},
    "thumbnail_concept": "썸네일 텍스트·이미지·색상 설명 (클릭률 최적화)"
  }},
  "shortform": {{
    "title": "숏폼 제목 (훅 포함)",
    "audio_hook": "첫 3초 오디오 훅 (이탈 방지)",
    "script_lines": [
      {{"line": "자막 텍스트", "duration_sec": 2, "cut_note": "편집 지시"}},
      {{"line": "자막 텍스트", "duration_sec": 2, "cut_note": "편집 지시"}}
    ],
    "cta": "단일 CTA (구독·저장·댓글 중 하나)",
    "hashtags": ["#태그1","#태그2","#태그3"]
  }},
  "retention_hook_score": "3초 훅 이탈방지 자체 점수 (예: 9/10 — 질문형)",
  "subtitle_readability": "자막 가독성 체크 메모",
  "cta_clarity": "CTA 명확성 자체 평가"
}}"""

        data = await _groq_json(prompt, job.api_keys, system=MEMBER_SYSTEM_PROMPTS["video"])
        results.append(data)

    job.video_contents = results
    job.reviews["video"] = ReviewResult(status="pending")
    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  팀원 시스템 프롬프트 (System Prompts)
# ════════════════════════════════════════════════════════

MEMBER_SYSTEM_PROMPTS: dict[str, str] = {

    "blog": """너는 이제부터 팀원 1 — SEO 에디터 "The Architect"야.

[신분]
- 역할: 검색 엔진 최적화(SEO), 블로그·롱폼 아티클, 데이터 기반 글쓰기 전문가
- 성격: 매우 논리적이며 구조 중심적. "문장이 예쁜 것보다 구글 로봇이 읽기 좋은 것"이 우선

[입력 소스]
- 원천 데이터: 팀장(마케팅 팀장)이 제공한 주간 콘텐츠 브리프 (topic, keywords, angle, target)

[출력 목적지]
- 결과물: job.blog_contents (주차별 블로그 포스트 배열)
- 이 결과물은 팀원 2(비주얼), 팀원 3(비즈니스), 팀원 4(영상)의 원천 소스가 됨

[작업 완료 후 의무]
1. 팀장에게 검토 요청 전송 → 팀장이 SEO 키워드 반영도·일관성 검수
2. 교차 검증 대기: 팀원 2·3·4가 내 키워드와 사실관계를 제대로 유지했는지 확인""",

    "sns_image": """너는 이제부터 팀원 2 — 비주얼 전략가 "The Trendsetter"야.

[신분]
- 역할: 인스타그램, 페이스북, 비주얼 스토리텔링 전문가
- 성격: 감각적이고 직관적. 유행 밈·해시태그 트렌드에 밝으며 Scroll-stop 유도에 집착

[입력 소스]
- 원천 데이터: job.blog_contents — 팀원 1(The Architect)이 작성한 블로그 포스트

[출력 목적지]
- 결과물: job.sns_image_contents (인스타그램·페이스북·카드뉴스)

[작업 완료 후 의무]
1. 팀장에게 검토 요청 전송 → 팀장이 플랫폼 특성 반영·비주얼 일관성 검수
2. 교차 검증: 팀원 4(영상)의 썸네일·비주얼 톤이 내 인스타 피드와 일치하는지 확인
3. 팀원 3(The Thought Leader)의 견제 수용: 브랜드 전문성 해치는 표현 수정""",

    "sns_text": """너는 이제부터 팀원 3 — 인사이트 분석가 "The Thought Leader"야.

[신분]
- 역할: 링크드인, 쓰레드, 비즈니스 네트워킹 전문가
- 성격: 냉철하고 지적. "좋아요"보다 "공유"와 "권위"가 우선. 업계 전문가 어조 유지

[입력 소스]
- 원천 데이터: job.blog_contents — 팀원 1(The Architect)이 작성한 블로그 포스트

[출력 목적지]
- 결과물: job.sns_text_contents (링크드인 아티클 + 쓰레드 연작 5개)

[작업 완료 후 의무]
1. 팀장에게 검토 요청 전송 → 팀장이 통찰력·논리 완결성 검수
2. 교차 검증: 팀원 2(인스타)의 문구가 브랜드 전문성을 해치지 않는지 제동
3. 팀원 1의 키워드와 사실관계가 링크드인·쓰레드에서도 유지되는지 자체 확인""",

    "video": """너는 이제부터 팀원 4 — 멀티미디어 PD "The Viral Maker"야.

[신분]
- 역할: 유튜브 쇼츠, 릴스, 틱톡, 영상 대본 전문가
- 성격: 에너지 넘치고 속도감 중시. Retention 그래프에 민감하며 '결론부터 말하기'의 달인

[입력 소스]
- 원천 데이터: job.blog_contents — 팀원 1(The Architect)이 작성한 블로그 포스트

[출력 목적지]
- 결과물: job.video_contents (YouTube 롱폼 대본 + 숏폼 컷 지시서)

[작업 완료 후 의무]
1. 팀장에게 검토 요청 전송 → 팀장이 3초 훅·자막 가독성·CTA 검수
2. 교차 검증: 팀원 1(블로그)에서 쇼츠로 만들 임팩트 포인트 피드백 전달
3. 팀원 2(인스타)와 썸네일 비주얼 톤 일치 여부 확인""",
}


# ════════════════════════════════════════════════════════
#  STEP 3.5 — 팀원 간 교차 검증 (Cross-Check Matrix)
# ════════════════════════════════════════════════════════

async def run_cross_check(job: AgencyJob) -> AgencyJob:
    """
    Cross-Check Matrix:
    팀원1(SEO)   → 팀원2,3,4: 키워드·사실관계 유지 여부
    팀원3(비즈)  → 팀원2(인스타): 브랜드 전문성 훼손 여부
    팀원2(비주얼)→ 팀원4(영상): 비주얼 톤 일치 여부
    팀원4(영상)  → 팀원1(SEO): 쇼츠 임팩트 포인트 피드백
    """
    job.current_step = "cross_checking"
    results = []

    for week_idx in range(len(job.lead_plan.briefs)):
        blog      = job.blog_contents[week_idx]      if week_idx < len(job.blog_contents)      else {}
        sns_text  = job.sns_text_contents[week_idx]  if week_idx < len(job.sns_text_contents)  else {}
        sns_image = job.sns_image_contents[week_idx] if week_idx < len(job.sns_image_contents) else {}
        video     = job.video_contents[week_idx]     if week_idx < len(job.video_contents)     else {}

        week_result = {"week": week_idx + 1}

        # ── Check 1: 팀원1(Architect) → 팀원2·3·4 ──────────────
        # "내 글의 핵심 키워드와 사실관계가 그대로 유지되었는가?"
        prompt_c1 = f"""너는 팀원 1 "The Architect"(SEO 에디터)야.
네가 작성한 블로그의 핵심 키워드와 사실관계가 다른 팀원들의 결과물에 제대로 유지되는지 검토해.

## 내 블로그 (원천 소스)
제목: {blog.get('title','')}
키워드: {', '.join(blog.get('lsi_keywords', blog.get('tags', [])))}

## 팀원 3 (링크드인)
{str(sns_text.get('linkedin',{}).get('body',''))[:400]}

## 팀원 2 (인스타 캡션)
{str(sns_image.get('instagram',{}).get('caption',''))[:300]}

## 팀원 4 (영상 훅)
{str(video.get('shortform',{}).get('audio_hook',''))}

다음을 간결하게 평가해 (3줄 이내):
1. 키워드 유지 여부 (pass/fail + 이유)
2. 사실관계 왜곡 여부 (pass/fail + 이유)
3. 수정이 필요한 팀원과 구체적 지시"""

        c1 = await _groq(prompt_c1, job.api_keys, system=MEMBER_SYSTEM_PROMPTS["blog"])

        # ── Check 2: 팀원3(Thought Leader) → 팀원2(Trendsetter) ─
        # "브랜드 이미지가 너무 가벼워져서 전문성을 해치지는 않는가?"
        prompt_c2 = f"""너는 팀원 3 "The Thought Leader"(인사이트 분석가)야.
팀원 2의 인스타그램 캡션이 브랜드 전문성을 해치는지 검토해.

## 팀원 2 (인스타 캡션 + 훅)
훅: {sns_image.get('instagram',{}).get('hook','')}
캡션: {str(sns_image.get('instagram',{}).get('caption',''))[:400]}

## 브랜드 기준
원래 블로그 제목: {blog.get('title','')}
톤앤매너 목표: 전문적이고 신뢰감 있는

다음을 평가해 (2줄 이내):
1. 브랜드 전문성 훼손 여부 (pass/warning/fail + 이유)
2. 수정 권고 사항 (있다면)"""

        c2 = await _groq(prompt_c2, job.api_keys, system=MEMBER_SYSTEM_PROMPTS["sns_text"])

        # ── Check 3: 팀원2(Trendsetter) → 팀원4(Viral Maker) ────
        # "영상 썸네일과 인스타 피드의 비주얼 톤이 일치하는가?"
        prompt_c3 = f"""너는 팀원 2 "The Trendsetter"(비주얼 전략가)야.
팀원 4의 영상 썸네일 컨셉이 내 인스타 피드 비주얼 톤과 일치하는지 검토해.

## 내 인스타 이미지 프롬프트
{sns_image.get('instagram',{}).get('image_prompt','')}

## 팀원 4 썸네일 컨셉
{video.get('youtube',{}).get('thumbnail_concept','')}

## 팀원 4 숏폼 분위기
훅: {video.get('shortform',{}).get('audio_hook','')}

다음을 평가해 (2줄 이내):
1. 비주얼 톤 일치 여부 (match/mismatch + 이유)
2. 조정 권고 (색상·분위기·스타일 기준)"""

        c3 = await _groq(prompt_c3, job.api_keys, system=MEMBER_SYSTEM_PROMPTS["sns_image"])

        # ── Check 4: 팀원4(Viral Maker) → 팀원1(Architect) ──────
        # "이 긴 글에서 쇼츠로 만들 만한 자극적인 포인트가 어디인가?"
        prompt_c4 = f"""너는 팀원 4 "The Viral Maker"(멀티미디어 PD)야.
팀원 1의 블로그에서 숏폼 영상으로 만들 최고의 임팩트 포인트를 뽑아 피드백해.

## 팀원 1 블로그
제목: {blog.get('title','')}
본문 일부: {str(blog.get('body',''))[:600]}

다음을 평가해 (3줄 이내):
1. 쇼츠 임팩트 포인트 TOP 2 (인용구 or 수치 or 역설적 사실)
2. 이 중 첫 3초 훅으로 쓸 최고의 한 문장
3. 팀원 1에게 "다음엔 이런 포인트를 더 강조해 달라"는 피드백"""

        c4 = await _groq(prompt_c4, job.api_keys, system=MEMBER_SYSTEM_PROMPTS["video"])

        week_result.update({
            "architect_reviews_others":   c1,   # 팀원1 → 팀원2,3,4
            "thought_leader_reviews_visual": c2, # 팀원3 → 팀원2
            "trendsetter_reviews_video":  c3,    # 팀원2 → 팀원4
            "viral_maker_reviews_blog":   c4,    # 팀원4 → 팀원1
        })
        results.append(week_result)

    job.cross_check_results = results
    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  STEP 4 — 팀장: 교차검증 + 최종검수
# ════════════════════════════════════════════════════════

MEMBER_KEYS = ["blog", "sns_text", "sns_image", "video"]

MEMBER_LABEL = {
    "blog":      "팀원1 (블로그)",
    "sns_text":  "팀원2 (텍스트형 SNS: 링크드인·쓰레드)",
    "sns_image": "팀원3 (이미지형 SNS: 인스타·페이스북)",
    "video":     "팀원4 (영상: YouTube·TikTok)",
}

PLATFORM_KPI = {
    "blog":      "SEO 유입, 체류시간, 공유수",
    "sns_text":  "인상(Impression), 댓글 참여율, 팔로워 증가",
    "sns_image": "저장수, 도달률, 해시태그 노출",
    "video":     "시청 지속시간, 구독 전환율, 댓글 참여",
}


async def run_lead_review(job: AgencyJob) -> AgencyJob:
    """
    팀장 최종 검수 마스터 체크리스트 (4-Filter System):
    [Filter 1] 데이터 동기화 (Data Sync Check)   — 팀원1 키워드/수치가 전 채널 유지되는지
    [Filter 2] 플랫폼 최적화 (Platform Fit Check) — 채널별 문체·포맷 적합도
    [Filter 3] 브랜드 가이드라인 (Brand Identity) — 금지어·톤 저해 표현 탐지
    [Filter 4] 기술적 배포 (Technical Ready)      — 메타데이터·규격·CTA 점검
    """
    job.current_step = "lead_review"
    prof     = job.agency_profile
    brief_kw: list[str] = []
    if job.lead_plan and job.lead_plan.briefs:
        brief_kw = job.lead_plan.briefs[0].keywords

    # ── 샘플 추출 ────────────────────────────────────────────────
    blog_s    = jl.dumps(job.blog_contents[0],      ensure_ascii=False)[:500] if job.blog_contents      else "(없음)"
    text_s    = jl.dumps(job.sns_text_contents[0],  ensure_ascii=False)[:400] if job.sns_text_contents  else "(없음)"
    img_s     = jl.dumps(job.sns_image_contents[0], ensure_ascii=False)[:400] if job.sns_image_contents else "(없음)"
    video_s   = jl.dumps(job.video_contents[0],     ensure_ascii=False)[:400] if job.video_contents     else "(없음)"
    kw_str    = ', '.join(brief_kw) if brief_kw else '(키워드 없음)'
    brand_nm  = prof.get('name', '')
    brand_tone= prof.get('tone', '')
    forbidden = ', '.join(prof.get('forbidden_words', [])) or '(미설정)'

    filter_results: list[FilterResult] = []

    # ════════════════════════════════════════════════════════
    # FILTER 1 — 데이터 동기화 (Data Sync Check)
    # 팀원1(블로그)의 핵심 키워드·수치가 팀원2,3,4 결과물에도 유지되는지
    # ════════════════════════════════════════════════════════
    f1_prompt = f"""## Filter 1 — 데이터 동기화 검수 (Data Sync Check)

팀장으로서 팀원1(블로그)이 정립한 핵심 키워드와 수치가 다른 채널에도 일관되게 유지되는지 검수하라.

### 핵심 키워드 (브리프 기준)
{kw_str}

### [팀원1 블로그 결과물]
{blog_s}

### [팀원3 텍스트SNS (링크드인·쓰레드) 결과물]
{text_s}

### [팀원2 이미지SNS (인스타·페이스북) 결과물]
{img_s}

### [팀원4 영상 (YouTube·TikTok) 결과물]
{video_s}

### 검수 항목
1. 팀원1이 사용한 핵심 키워드가 팀원2,3,4 결과물에도 등장하는가?
2. 블로그에서 언급된 통계·수치·제품명이 다른 채널에서 변형·누락되지 않았는가?
3. 블로그 핵심 주장(앵글)이 각 채널에서 같은 방향으로 재구성되었는가?
4. 누락된 채널이 있다면 어느 채널이며 어떤 키워드가 빠졌는가?

JSON만 반환:
{{
  "status": "pass 또는 warning 또는 fail",
  "score": 0에서 100 사이 정수,
  "findings": ["동기화 확인 항목 or 문제점 1", "항목 2", "항목 3"],
  "action_items": ["수정 지시 1 (팀원 명시)", "수정 지시 2"],
  "summary": "데이터 동기화 상태 1문장 요약"
}}"""

    f1 = await _groq_json(f1_prompt, job.api_keys, system=LEAD_PERSONA)
    filter_results.append(FilterResult(
        filter_name="data_sync",
        status=f1.get("status", "warning"),
        score=int(f1.get("score", 0)),
        findings=f1.get("findings", []),
        action_items=f1.get("action_items", []),
        summary=f1.get("summary", ""),
    ))

    # ════════════════════════════════════════════════════════
    # FILTER 2 — 플랫폼 최적화 (Platform Fit Check)
    # 채널별 특성(문체·포맷·CTA·훅)이 충족되었는지
    # ════════════════════════════════════════════════════════
    f2_prompt = f"""## Filter 2 — 플랫폼 최적화 검수 (Platform Fit Check)

팀장으로서 각 채널 결과물이 해당 플랫폼의 고유 특성을 제대로 반영했는지 검수하라.

### [팀원1 블로그]
{blog_s}

### [팀원3 텍스트SNS]
{text_s}

### [팀원2 이미지SNS]
{img_s}

### [팀원4 영상]
{video_s}

### 채널별 플랫폼 기준
- 블로그(SEO): H1/H2 구조, 키워드 밀도 1~2%, 내부 링크, 1800자 이상
- 링크드인: 전문가 톤, opinion_question 포함, 해시태그 3~5개
- 쓰레드: 5부작 시리즈(1/5~5/5), 각 280자 이하, 감성 마무리
- 인스타그램: 첫 줄 훅(scroll_stop_score), 이모지, 해시태그 15~30개
- YouTube: 3초 오디오 훅, 챕터별 B-roll, CTA 명확
- TikTok: 빠른 시각 훅, 자막 가독성, 15~60초 구성

### 검수 항목
1. 인스타그램 첫 줄 훅(hook)이 스크롤을 멈출 만큼 강렬한가?
2. 링크드인 문체가 충분히 전문적이고 B2B 타겟에 맞는가?
3. YouTube/TikTok에서 3초 내 시청자를 붙잡는 오디오·비주얼 훅이 있는가?
4. 각 채널 CTA가 명확하고 플랫폼 특성에 맞게 설계되었는가?
5. 쓰레드가 5부작 시리즈 형식으로 구성되었는가?

JSON만 반환:
{{
  "status": "pass 또는 warning 또는 fail",
  "score": 0에서 100 사이 정수,
  "findings": ["채널별 적합도 평가 1", "평가 2", "평가 3", "평가 4"],
  "action_items": ["수정 지시 (채널·팀원 명시) 1", "수정 지시 2"],
  "summary": "플랫폼 최적화 상태 1문장 요약"
}}"""

    f2 = await _groq_json(f2_prompt, job.api_keys, system=LEAD_PERSONA)
    filter_results.append(FilterResult(
        filter_name="platform_fit",
        status=f2.get("status", "warning"),
        score=int(f2.get("score", 0)),
        findings=f2.get("findings", []),
        action_items=f2.get("action_items", []),
        summary=f2.get("summary", ""),
    ))

    # ════════════════════════════════════════════════════════
    # FILTER 3 — 브랜드 가이드라인 (Brand Identity Check)
    # 신뢰감 저해 표현·금지어·톤앤매너 위반 탐지
    # ════════════════════════════════════════════════════════
    f3_prompt = f"""## Filter 3 — 브랜드 가이드라인 검수 (Brand Identity Check)

팀장으로서 모든 채널 결과물이 브랜드 아이덴티티를 유지하는지 검수하라.

### 브랜드 기준
- 브랜드명: {brand_nm}
- 톤앤매너: {brand_tone}
- 금지어/금지 표현: {forbidden}

### 전체 콘텐츠 샘플
[블로그] {blog_s}
[텍스트SNS] {text_s}
[이미지SNS] {img_s}
[영상] {video_s}

### 검수 항목
1. 신뢰감을 저해하는 과장·허위·자극적 표현이 있는가?
2. 설정된 금지어/금지 표현이 사용되었는가?
3. 브랜드 톤앤매너(예: 전문적·친근함·공식적)와 어긋나는 문체가 있는가?
4. 브랜드명·제품명 오기 또는 일관성 없는 표기가 있는가?
5. 법적 리스크가 될 수 있는 단정적 효과 주장이 있는가?

JSON만 반환:
{{
  "status": "pass 또는 warning 또는 fail",
  "score": 0에서 100 사이 정수,
  "findings": ["위반 또는 확인 항목 1", "항목 2", "항목 3"],
  "action_items": ["수정 지시 (채널·표현 명시) 1", "수정 지시 2"],
  "summary": "브랜드 가이드라인 준수 상태 1문장 요약"
}}"""

    f3 = await _groq_json(f3_prompt, job.api_keys, system=LEAD_PERSONA)
    filter_results.append(FilterResult(
        filter_name="brand_identity",
        status=f3.get("status", "warning"),
        score=int(f3.get("score", 0)),
        findings=f3.get("findings", []),
        action_items=f3.get("action_items", []),
        summary=f3.get("summary", ""),
    ))

    # ════════════════════════════════════════════════════════
    # FILTER 4 — 기술적 배포 (Technical Ready Check)
    # 메타데이터·이미지 규격·CTA 링크·SEO 태그 점검
    # ════════════════════════════════════════════════════════
    f4_prompt = f"""## Filter 4 — 기술적 배포 검수 (Technical Ready Check)

팀장으로서 콘텐츠가 실제 플랫폼 배포에 즉시 사용 가능한 기술적 완성도를 갖췄는지 검수하라.

### 콘텐츠 샘플
[블로그] {blog_s}
[텍스트SNS] {text_s}
[이미지SNS] {img_s}
[영상] {video_s}

### 기술적 배포 체크리스트
1. **메타데이터**: 블로그 meta_title(60자 이하), meta_description(160자 이하) 존재 여부
2. **이미지 규격**: 인스타 카드뉴스 1:1 비율 명시, YouTube 썸네일 1280×720 명시 여부
3. **CTA 링크 기획**: 각 채널 CTA가 어느 URL/행동으로 연결되는지 명확히 설계되었는가?
4. **SEO 기술 태그**: alt 텍스트([IMG: alt]) 포함 여부, H1~H3 계층 구조 존재 여부
5. **자막 준비**: 영상 script_lines에 duration_sec 포함으로 SRT 변환 가능한지
6. **해시태그 수**: 인스타 15~30개, 링크드인 3~5개, YouTube 태그 10개 이상

JSON만 반환:
{{
  "status": "pass 또는 warning 또는 fail",
  "score": 0에서 100 사이 정수,
  "findings": ["기술 항목 확인/문제 1", "항목 2", "항목 3", "항목 4"],
  "action_items": ["기술적 수정 지시 (팀원·필드 명시) 1", "수정 지시 2"],
  "summary": "기술적 배포 준비 상태 1문장 요약"
}}"""

    f4 = await _groq_json(f4_prompt, job.api_keys, system=LEAD_PERSONA)
    filter_results.append(FilterResult(
        filter_name="technical_ready",
        status=f4.get("status", "warning"),
        score=int(f4.get("score", 0)),
        findings=f4.get("findings", []),
        action_items=f4.get("action_items", []),
        summary=f4.get("summary", ""),
    ))

    # ── 종합 판정 ────────────────────────────────────────────────
    fail_count    = sum(1 for f in filter_results if f.status == "fail")
    warning_count = sum(1 for f in filter_results if f.status == "warning")
    avg_score     = int(sum(f.score for f in filter_results) / len(filter_results))

    if fail_count >= 2:
        overall_status = "partial_rejected"
    elif fail_count == 1 or warning_count >= 3:
        overall_status = "partial_rejected"
    else:
        overall_status = "all_approved"

    # reviews dict 업데이트 (하위 호환 — STEP 5 재작업 트리거용)
    for member in ["blog", "sns_text", "sns_image", "video"]:
        current = job.reviews.get(member, ReviewResult())
        all_actions = [a for f in filter_results for a in f.action_items]
        member_actions = [a for a in all_actions if member.replace("_", " ") in a.lower() or member in a.lower()]
        if fail_count >= 1 and member_actions:
            job.reviews[member] = ReviewResult(
                status="rejected",
                feedback=" / ".join(member_actions[:3]),
                retry_count=current.retry_count,
            )
        else:
            job.reviews[member] = ReviewResult(
                status="approved",
                feedback="",
                retry_count=current.retry_count,
            )

    # overall_feedback 구성
    filter_summaries = " | ".join(f"[{f.filter_name}:{f.status.upper()}({f.score}점)] {f.summary}" for f in filter_results)
    overall_feedback = (
        f"4-필터 평균 점수: {avg_score}점. {filter_summaries}"
    )

    current_retry = job.lead_cross_review.retry_count if job.lead_cross_review else 0
    job.lead_cross_review = LeadCrossReview(
        status=overall_status,
        cross_consistency=filter_results[0].summary if filter_results else "",
        keyword_coverage=filter_results[0].summary if filter_results else "",
        member_reviews=[],          # 4-필터 체계에서는 filter_results로 대체
        filter_results=filter_results,
        overall_feedback=overall_feedback,
        retry_count=current_retry,
    )

    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  STEP 5 — 팀원: 보완 수정
# ════════════════════════════════════════════════════════

async def run_member_revision(job: AgencyJob, member: str) -> AgencyJob:
    """거절된 팀원이 팀장 피드백 기반으로 수정"""
    review = job.reviews.get(member)
    if not review or review.status != "rejected":
        return job
    if review.retry_count >= 3:
        job.reviews[member].status = "approved"   # 3회 초과 시 강제 통과
        save_job(job)
        return job

    feedback = review.feedback
    job.current_step = f"revision_{member}"

    if member == "blog":
        job = await run_member_blog(job)
    elif member == "sns_text":
        job = await run_member_sns_text(job)
    elif member == "sns_image":
        job = await run_member_sns_image(job)
    elif member == "video":
        job = await run_member_video(job)

    job.reviews[member].retry_count += 1
    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  STEP 6/7 — CMO: 최종 배포 스케줄 생성
# ════════════════════════════════════════════════════════

async def run_cmo_deploy(job: AgencyJob) -> AgencyJob:
    """CMO: 승인된 콘텐츠를 날짜·플랫폼에 매핑"""
    job.current_step = "cmo_deploy"
    cmo = job.cmo_schedule
    dates = _calc_schedule(cmo)

    plat_content_map = {
        "tistory":    ("blog",      "blog_contents"),
        "wordpress":  ("blog",      "blog_contents"),
        "naver":      ("blog",      "blog_contents"),
        "linkedin":   ("sns_text",  "sns_text_contents"),
        "threads":    ("sns_text",  "sns_text_contents"),
        "instagram":  ("sns_image", "sns_image_contents"),
        "facebook":   ("sns_image", "sns_image_contents"),
        "youtube":    ("video",     "video_contents"),
        "tiktok":     ("video",     "video_contents"),
    }

    schedule = []
    week_idx = 0
    for slot in dates:
        w = week_idx % max(len(job.blog_contents), 1)
        for plat in cmo.platforms:
            member, attr = plat_content_map.get(plat, ("blog", "blog_contents"))
            contents = getattr(job, attr, [])
            content  = contents[w] if w < len(contents) else {}
            schedule.append({
                "date":        slot["date"],
                "time":        slot["time"],
                "platform":    plat,
                "member":      member,
                "week":        w + 1,
                "content_ref": content.get("title") or content.get("week", ""),
                "status":      "scheduled",
            })
        week_idx += 1

    job.deploy_schedule = schedule
    job.status = "done"
    job.current_step = "done"
    save_job(job)
    return job


# ════════════════════════════════════════════════════════
#  전체 파이프라인 실행
# ════════════════════════════════════════════════════════

async def run_full_pipeline(job: AgencyJob) -> AgencyJob:
    """전체 에이전시 파이프라인 순차 실행"""
    try:
        job.status = "running"
        save_job(job)

        # STEP 1: CMO 일정
        job = await run_cmo_schedule(job)

        # STEP 2: 팀장 기획
        job = await run_lead_plan(job)

        # STEP 2.5: CMO 교차검증 (최대 2회 — 재기획 포함)
        job.current_step = "cmo_approve_plan"
        save_job(job)
        for attempt in range(2):
            job = await run_cmo_approve_plan(job)
            if job.cmo_approval.status == "approved":
                break
            # CMO 수정 요구 → 팀장 재기획
            job.cmo_approval.retry_count += 1
            save_job(job)
            job = await run_lead_plan(job)
        # 2회 후에도 미승인이면 CMO 자동 승인 처리
        if job.cmo_approval and job.cmo_approval.status != "approved":
            job.cmo_approval.status = "approved"
            job.cmo_approval.feedback += " [2차 재기획 후 CMO 자동 승인]"
            save_job(job)

        # STEP 3: 팀원 병렬 생성
        job.current_step = "members_creating"
        save_job(job)
        await asyncio.gather(
            run_member_blog(job),
            run_member_sns_text(job),
            run_member_sns_image(job),
            run_member_video(job),
        )

        # STEP 3.5: 팀원 간 교차 검증 (Cross-Check Matrix)
        job.current_step = "cross_checking"
        save_job(job)
        job = await run_cross_check(job)

        # STEP 4: 팀장 검수
        job.status = "reviewing"
        save_job(job)
        job = await run_lead_review(job)

        # STEP 5: 거절 팀원 수정 → 팀장 재검수 (최대 3회)
        for _ in range(3):
            rejected = [m for m, r in job.reviews.items() if r.status == "rejected"]
            if not rejected:
                break
            for member in rejected:
                job = await run_member_revision(job, member)
            # 팀장 교차검증 재실행
            if job.lead_cross_review:
                job.lead_cross_review.retry_count += 1
            job = await run_lead_review(job)

        # STEP 6/7: CMO 배포 스케줄
        job = await run_cmo_deploy(job)

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        save_job(job)

    return job
