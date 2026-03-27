"""
Marketing Route - FastAPI 메인
AI 마케팅 네비게이터 API 서버
"""

import uuid
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from backend.models.schemas import (
    ContentRequest, PipelineJob, LinkChainConfig,
    ApprovalStatus, PublishRequest, Stage4Output,
    ApiTier, TIER_LABELS, TIER_FEATURES,
    AgencyProfile, SEOPlanRequest, SEOPlanResult, ContentBrief,
    BlogRequest, BlogResult, BlogPost, BlogPlatform,
    VideoRequest, VideoResult, VideoSection, VideoType,
    ConvertRequest, ConvertResult,
    CardNewsRequest, CardNewsResult, CardNewsSlide,
    CardNewsPlanRequest, CardNewsPlanResult, SlideOutline,
    SNSRequest, SNSResult, SNSPost, SNSPlatform,
    SEOKeywordItem, SEOQuickRequest, SEOQuickResult,
    SEOAnalyzeRequest, SEOAnalyzeResult, SEOTrendPoint,
    SEOSuggestRequest, SEOSuggestResult,
    SEOExpandRequest, SEOExpandResult,
    SEOBulkRequest, SEOBulkResult,
    SEOCrawlRequest, SEOCrawlResult, SEOTechCheck,
    SEOGapRequest, SEOGapResult,
    SEOMetaRequest, SEOMetaResult,
    GSCConnectRequest, GSCReport, GSCRow,
)
from backend.pipeline import (
    stage1_input,
    stage2_osmu,
    stage3_visual,
    stage4_review,
    stage5_publish,
)
from backend import agency as _agency

app = FastAPI(
    title="Marketing Route",
    description="AI 마케팅 네비게이터 - 멀티채널 콘텐츠 자동화 플랫폼",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 인메모리 Job 저장소 (MVP용 - 추후 Supabase/Airtable로 교체)
jobs: dict[str, PipelineJob] = {}

# 정적 파일 서빙
BASE_DIR = Path(__file__).resolve().parent.parent
_outputs_dir = BASE_DIR / "outputs"
_outputs_dir.mkdir(exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(_outputs_dir)), name="outputs")


# ── 헬스 체크 ─────────────────────────────────────────────────

@app.get("/ui", include_in_schema=False)
def serve_ui():
    """브라우저에서 /ui 접속 시 대시보드 반환"""
    return FileResponse(str(BASE_DIR / "frontend" / "index.html"))

@app.get("/")
def root():
    return {"status": "ok", "service": "Marketing Route v0.1"}


# ── 에이전시 프로필 (학습) ─────────────────────────────────────
_agency_profile: AgencyProfile = AgencyProfile()   # 인메모리 (MVP)

@app.get("/agency", response_model=AgencyProfile)
def get_agency():
    return _agency_profile

@app.post("/agency", response_model=AgencyProfile)
def save_agency(profile: AgencyProfile):
    global _agency_profile
    _agency_profile = profile
    return _agency_profile


# ── SEO 기획 ──────────────────────────────────────────────────
@app.post("/seo/plan", response_model=SEOPlanResult)
async def seo_plan(req: SEOPlanRequest):
    """키워드 기반 콘텐츠 기획 — 주제 선정 + 후킹 앵글 + 콘텐츠 캘린더"""
    import os, re, json

    profile = req.agency_profile or _agency_profile
    gemini_key = (req.api_keys or {}).get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")

    # 보이스 DNA 섹션 (중첩 f-string 방지)
    if profile.brand_voice_dna:
        dna = profile.brand_voice_dna
        voice_dna_section = (
            "보이스 DNA:\n"
            "- 문장 스타일: " + dna.get('sentence_style', '') + "\n"
            "- 제목 패턴: " + dna.get('title_pattern', '') + "\n"
            "- 자주 쓰는 표현: " + ', '.join(dna.get('tone_keywords', [])) + "\n"
            "- 피해야 할 표현: " + ', '.join(dna.get('avoid', [])) + "\n"
            "- 한 줄 요약: " + dna.get('summary', '')
        )
    else:
        voice_dna_section = ""

    if profile.brand_voice_samples:
        sample_lines = "\n".join(f"- {s}" for s in profile.brand_voice_samples[:3])
        voice_sample_section = "보이스 샘플:\n" + sample_lines
    else:
        voice_sample_section = ""

    prompt = f"""당신은 B2B 멀티플랫폼 콘텐츠 기획 전문가입니다.
하나의 키워드/주제로 블로그·링크드인·인스타그램·쓰레드·카드뉴스·유튜브에 배포할 콘텐츠를 기획하세요.
같은 핵심 메시지를 각 플랫폼에 맞는 형식으로 재구성하는 OSMU 전략입니다.

키워드: {req.keyword}
에이전시: {profile.agency_name} / 업종: {profile.industry}
서비스: {profile.services}
타겟: {profile.target_audience}
톤앤매너: {profile.tone_and_manner}
콘텐츠 기둥: {', '.join(profile.content_pillars)}
{voice_dna_section}
{voice_sample_section}

JSON 형식으로만 반환 (다른 텍스트 없이):
{{
  "search_intent": "검색 의도 한 줄 요약",
  "recommended_topics": ["주제1", "주제2", "주제3", "주제4", "주제5"],
  "hook_angles": ["후킹앵글1", "후킹앵글2", "후킹앵글3"],
  "competitor_patterns": ["경쟁사패턴1", "경쟁사패턴2"],
  "content_calendar": [
    {{"week": 1, "topic": "주제", "platform": "blog", "format": "longform"}},
    {{"week": 1, "topic": "주제", "platform": "linkedin", "format": "shortpost"}},
    {{"week": 2, "topic": "주제", "platform": "instagram", "format": "card_news"}}
  ],
  "content_briefs": {{
    "blog": {{
      "topic": "블로그 글 제목 (SEO 최적화)",
      "summary": "블로그 글의 핵심 내용 2~3문장 요약",
      "key_points": ["핵심포인트1", "핵심포인트2", "핵심포인트3"],
      "angle": "독자가 얻는 가치/관점"
    }},
    "linkedin": {{
      "topic": "링크드인 포스트 제목",
      "summary": "비즈니스 인사이트 중심 2~3문장 요약",
      "key_points": ["인사이트1", "인사이트2"],
      "angle": "전문가 관점의 비즈니스 가치"
    }},
    "instagram": {{
      "topic": "인스타그램 캡션 첫줄 (후킹)",
      "summary": "비주얼 콘텐츠용 핵심 메시지",
      "key_points": ["포인트1", "포인트2", "포인트3"],
      "angle": "감성/비주얼 소구점"
    }},
    "threads": {{
      "topic": "쓰레드 첫 글 (호기심 유발)",
      "summary": "대화형 짧은 시리즈 주제",
      "key_points": ["스레드1", "스레드2", "스레드3"],
      "angle": "대화를 유도하는 질문/반전"
    }},
    "card_news": {{
      "topic": "카드뉴스 전체 제목",
      "summary": "슬라이드로 나눌 핵심 내용 요약",
      "key_points": ["슬라이드주제1", "슬라이드주제2", "슬라이드주제3", "슬라이드주제4", "슬라이드주제5"],
      "angle": "인포그래픽 소구점",
      "recommended_slide_count": 7
    }},
    "youtube": {{
      "topic": "유튜브 영상 제목",
      "summary": "영상 구성 핵심 내용 요약",
      "key_points": ["챕터1", "챕터2", "챕터3"],
      "angle": "시청자가 배울 것"
    }}
  }}
}}"""

    result_text, _err = await _gemini_text(prompt, {"gemini_api_key": gemini_key}, req.tier)
    if _err:
        result_text = json.dumps({
            "search_intent": f"{_err}",
            "recommended_topics": [f"{req.keyword} 도입 사례", f"{req.keyword} B2B 전략", f"{req.keyword} ROI", f"{req.keyword} 트렌드 2026", f"{req.keyword} 성공 사례"],
            "hook_angles": [f"숫자형: 5가지 {req.keyword}", f"질문형: {req.keyword} 준비됐나요?", f"결과형: {req.keyword}로 CTR 300%"],
            "competitor_patterns": ["리스트형 제목 CTR 높음", "질문형 오프닝 효과적"],
            "content_calendar": [
                {"week": 1, "topic": f"{req.keyword} 완벽 가이드", "platform": "blog", "format": "longform"},
                {"week": 1, "topic": f"{req.keyword} 인사이트", "platform": "linkedin", "format": "shortpost"},
                {"week": 2, "topic": f"{req.keyword} 핵심 3가지", "platform": "instagram", "format": "card_news"},
            ]
        })

    match = re.search(r'\{.*\}', result_text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return SEOPlanResult(
                keyword=req.keyword,
                search_intent=data.get("search_intent", ""),
                recommended_topics=data.get("recommended_topics", []),
                hook_angles=data.get("hook_angles", []),
                competitor_patterns=data.get("competitor_patterns", []),
                content_calendar=data.get("content_calendar", []),
                content_briefs=data.get("content_briefs", {}),
            )
        except Exception:
            pass
    return SEOPlanResult(keyword=req.keyword, search_intent="파싱 실패 — Raw: " + result_text[:200])


# ── SEO 키워드 도구 ────────────────────────────────────────────

async def _gemini_text(prompt: str, api_keys: dict, tier: str = "tier1") -> tuple[str, str | None]:
    """Gemini 호출 후 텍스트 반환 (google.genai SDK)"""
    import os
    key = api_keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")
    if not key:
        return "", "Gemini API 키가 없습니다. API 설정에서 키를 입력하고 저장해주세요."
    try:
        from google import genai
        client = genai.Client(api_key=key)
        model_name = "gemini-2.5-flash" if tier in ("tier2", "tier3") else "gemini-2.5-flash"
        resp = client.models.generate_content(model=model_name, contents=prompt)
        return resp.text or "", None
    except Exception as e:
        err_str = str(e)
        if "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
            return "", "❌ Gemini API 키가 유효하지 않습니다."
        if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
            return "", "❌ Gemini 일일 할당량 초과(429). 내일 다시 시도하거나 새 키를 발급받으세요."
        return "", f"Gemini 오류: {err_str[:150]}"


async def _gemini_json(prompt: str, api_keys: dict, tier: str = "tier1"):
    """Gemini 호출 후 JSON 파싱 공통 헬퍼 (google.genai SDK)"""
    import re, json as jl, os
    key = api_keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")
    if not key:
        return None, "Gemini API 키가 없습니다. API 설정에서 키를 입력하고 저장해주세요."
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        model_name = "gemini-2.5-flash" if tier in ("tier2", "tier3") else "gemini-2.5-flash"
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        raw = resp.text
    except Exception as e:
        err_str = str(e)
        if "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
            return None, "❌ Gemini API 키가 유효하지 않습니다. API 설정에서 새 키를 입력하세요."
        if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
            return None, "❌ Gemini 일일 할당량 초과(429). 내일 다시 시도하거나 새 키를 발급받으세요."
        if "PERMISSION_DENIED" in err_str or "403" in err_str:
            return None, "❌ Gemini API 권한 없음(403). 키가 비활성화됐거나 서비스가 꺼져있습니다."
        return None, f"Gemini 오류: {err_str[:200]}"
    # JSON 파싱
    if not raw:
        return None, "Gemini가 빈 응답을 반환했습니다."
    for pat in (r'\[.*\]', r'\{.*\}'):
        m = re.search(pat, raw, re.DOTALL)
        if m:
            try:
                return jl.loads(m.group()), None
            except Exception:
                continue
    # response_mime_type=application/json이면 raw 자체가 JSON일 수 있음
    try:
        return jl.loads(raw), None
    except Exception:
        pass
    return None, f"JSON 파싱 실패: {raw[:200]}"


async def _groq_json(prompt: str, api_keys: dict, model: str = "llama-3.3-70b-versatile"):
    """Groq 호출 후 JSON 파싱 공통 헬퍼 — SEO·기획 전용"""
    import re, json as jl, os
    key = api_keys.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
    if not key:
        return None, "Groq API 키가 없습니다. API 설정에서 키를 입력하고 저장해주세요."
    try:
        from groq import Groq
        client = Groq(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 한국 SEO·콘텐츠 전략 전문가입니다. 반드시 유효한 JSON만 반환하세요. 코드블록(```json 등), 설명, 주석 없이 순수 JSON만."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=4096,
        )
        raw = resp.choices[0].message.content or ""
    except Exception as e:
        err_str = str(e)
        if "401" in err_str or "invalid_api_key" in err_str.lower():
            return None, "❌ Groq API 키가 유효하지 않습니다."
        if "429" in err_str or "rate_limit" in err_str.lower():
            return None, "❌ Groq 요청 한도 초과. 잠시 후 다시 시도해주세요."
        if "decommissioned" in err_str.lower() or "model_not_found" in err_str.lower():
            return None, f"❌ Groq 모델 오류: {err_str[:100]}"
        return None, f"Groq 오류: {err_str[:200]}"
    # JSON 파싱
    if not raw:
        return None, "Groq가 빈 응답을 반환했습니다."
    for pat in (r'\{.*\}', r'\[.*\]'):
        m = re.search(pat, raw, re.DOTALL)
        if m:
            try:
                return jl.loads(m.group()), None
            except Exception:
                continue
    try:
        return jl.loads(raw), None
    except Exception:
        pass
    return None, f"JSON 파싱 실패: {raw[:200]}"


@app.post("/seo/quick", response_model=SEOQuickResult)
async def seo_quick(req: SEOQuickRequest):
    """간편 키워드 조회 — 여러 키워드 빠른 비교"""
    kws = req.keywords[:20]
    kws_str = '\n'.join(f'- {k}' for k in kws)
    prompt = f"""다음 키워드들을 SEO 관점에서 빠르게 분석하세요.
※ 월 검색량은 한국 기준 AI 추정값입니다.

키워드 목록:
{kws_str}

JSON 배열로만 반환 (다른 텍스트 없이):
[
  {{
    "keyword": "키워드",
    "intent": "정보형 | 거래형 | 탐색형 | 비교형",
    "competition": "low | medium | high",
    "monthly_search": "예: 10,000~30,000",
    "recommended": true,
    "notes": "마케팅 활용 한 줄 코멘트"
  }}
]
총 {len(kws)}개 모두 포함하세요."""

    data, err = await _groq_json(prompt, req.api_keys or {})
    if data and isinstance(data, list):
        return SEOQuickResult(items=[SEOKeywordItem(**{k:v for k,v in item.items() if k in SEOKeywordItem.model_fields}) for item in data])
    return SEOQuickResult(items=[SEOKeywordItem(keyword=k, notes=err or "분석 실패") for k in kws])


@app.post("/seo/analyze", response_model=SEOAnalyzeResult)
async def seo_analyze(req: SEOAnalyzeRequest):
    """키워드 상세 분석 — 연관키워드·클러스터·트렌드·스마트블록·콘텐츠기획"""
    profile = req.agency_profile or _agency_profile
    keys    = req.api_keys or {}
    compare = ', '.join(req.compare_keywords) if req.compare_keywords else '없음'
    months  = min(req.trend_period * 12, 24)

    # 페르소나별 키워드 전략 힌트
    persona_type = getattr(profile, 'persona_type', '') or ''
    persona_hint = ''
    if persona_type == 'startup':
        persona_hint = '\n[모드: B2B 스타트업] 의사결정자(CEO·마케터·팀장) 타겟. 전문성·신뢰·ROI 강조 키워드. LinkedIn에 어울리는 업계 용어 포함.'
    elif persona_type == 'sidehustle':
        persona_hint = '\n[모드: N잡러/부업] 네이버·티스토리 애드센스 수익화 목적. 고단가 키워드, 롱테일 정보성(~하는법, ~이란, ~추천) 위주.'
    elif persona_type == 'local':
        persona_hint = '\n[모드: 로컬 소상공인] 지역명+업종 조합, 네이버 지역검색 최적화. 감성적·생활밀착형 키워드.'

    industry   = profile.industry or ''
    target     = getattr(profile, 'target_audience', '') or ''
    services   = getattr(profile, 'services', '') or ''
    main_kws   = ', '.join(getattr(profile, 'main_keywords', []) or [])
    context    = getattr(req, 'context', '') or ''

    prompt = f"""당신은 한국 SEO 전문가입니다. 실제 검색 유입에 도움이 되는 구체적인 키워드를 추출하세요.

## 분석 대상
- 핵심 주제: {req.keyword}
{f'- 추가 맥락: {context}' if context else ''}
- 업종: {industry or '미설정'}
- 타겟 독자: {target or '미설정'}
- 서비스/상품: {services or '미설정'}
- 브랜드 키워드: {main_kws or '없음'}
{persona_hint}

## 키워드 생성 원칙
1. **한국 검색 패턴 기반** (네이버·구글 실제 검색어 스타일)
2. **의도별 다양성 확보**:
   - 정보성: "~이란", "~하는방법", "~원인", "~장점단점", "~차이"
   - 상업성: "~추천", "~비교", "~순위", "~후기", "~가격"
   - 롱테일: 3단어 이상, 매우 구체적 의도
3. **monthly_est는 반드시 정수** (예: 12000, 3500, 800) — 범위 금지
4. 핵심 주제와 직접 연관된 키워드만 생성. 잡다한 것 제외.
5. **recommended_topics는 실제 포스팅 제목 형태** (예: "B2B 콘텐츠 마케팅 완벽 가이드 2024")

JSON만 반환 (코드블록 없이):
{{
  "search_intent": "이 주제를 검색하는 사람의 핵심 의도 (2~3문장)",
  "related_keywords": [
    {{"keyword": "구체적인 키워드", "relevance": 95, "monthly_est": 15000, "competition": "low", "intent": "정보|상업|롱테일"}},
    ... (총 {min(req.related_count, 30)}개, 의도별 골고루)
  ],
  "clusters": [
    {{"name": "정보성 키워드", "keywords": ["kw1", "kw2", "kw3", "kw4"]}},
    {{"name": "상업성 키워드", "keywords": ["kw1", "kw2", "kw3"]}},
    {{"name": "롱테일 키워드", "keywords": ["kw1", "kw2", "kw3"]}},
    ... (총 {min(req.cluster_count, 8)}개)
  ],
  "trend_data": [
    {{"period": "YYYY-MM", "value": 75}},
    ... (최근 {months}개월, value 0-100)
  ],
  "smart_block": [
    {{"rank": 1, "title": "실제 검색 결과에 뜰 법한 인기글 제목", "type": "블로그|카페|뉴스|지식인", "engagement": "높음|보통|낮음"}},
    ... (5개)
  ],
  "recommended_topics": [
    "실제 포스팅 제목처럼 구체적으로",
    ... (5개, 채널별로 다르게)
  ],
  "hook_angles": ["차별화 앵글1 — 구체적으로", "앵글2", "앵글3"],
  "content_briefs": {{
    "blog":      {{"topic": "...", "summary": "...", "key_points": ["...", "...", "..."], "angle": "..."}},
    "linkedin":  {{"topic": "...", "summary": "...", "key_points": ["...", "..."], "angle": "..."}},
    "instagram": {{"topic": "...", "summary": "...", "key_points": ["...", "...", "..."], "angle": "..."}},
    "threads":   {{"topic": "...", "summary": "...", "key_points": ["...", "...", "..."], "angle": "..."}},
    "card_news": {{"topic": "...", "summary": "...", "key_points": ["...", "...", "...", "...", "..."], "angle": "...", "recommended_slide_count": 7}},
    "youtube":   {{"topic": "...", "summary": "...", "key_points": ["...", "...", "..."], "angle": "..."}}
  }}
}}"""

    data, err = await _groq_json(prompt, keys)
    if data and isinstance(data, dict):
        trend = [SEOTrendPoint(**p) for p in data.get("trend_data", [])]
        return SEOAnalyzeResult(
            keyword=req.keyword,
            search_intent=data.get("search_intent", ""),
            related_keywords=data.get("related_keywords", []),
            clusters=data.get("clusters", []),
            trend_data=trend,
            smart_block=data.get("smart_block", []),
            content_briefs=data.get("content_briefs", {}),
            recommended_topics=data.get("recommended_topics", []),
            hook_angles=data.get("hook_angles", []),
        )
    raise HTTPException(status_code=500, detail=err or "분석 실패")


@app.post("/seo/suggest", response_model=SEOSuggestResult)
async def seo_suggest(req: SEOSuggestRequest):
    """키워드 추천 — 블로그/마케팅/SNS/유튜브 맞춤"""
    profile = req.agency_profile or _agency_profile
    keys    = req.api_keys or {}
    type_guide = {
        "blog": "SEO 롱테일, 정보성, 경쟁도 낮은 블로그 포스팅용",
        "marketing": "구매 의도 높은 광고/랜딩페이지용",
        "sns": "바이럴 가능성 높은 SNS 콘텐츠용",
        "youtube": "유튜브 검색 최적화, 조회수 높은 영상 제목용",
    }.get(req.content_type, "마케팅 콘텐츠용")

    prompt = f"""SEO 키워드 추천 전문가로서 맞춤형 키워드를 추천하세요.
기준 키워드: {req.base_keyword}
업종: {req.industry or profile.industry or '미설정'}
콘텐츠 유형: {req.content_type} ({type_guide})
추천 개수: {req.suggest_count}개
추가 필터: {req.filters}
※ 검색량은 AI 추정값.

JSON 배열로만 반환:
[
  {{
    "keyword": "추천 키워드",
    "score": 85,
    "reason": "추천 이유 (한 줄)",
    "monthly_est": "예: 2,000~8,000",
    "competition": "low|medium|high",
    "content_fit": "이 키워드로 만들 콘텐츠 아이디어 한 줄"
  }}
]
총 {req.suggest_count}개."""

    data, err = await _groq_json(prompt, keys)
    if data and isinstance(data, list):
        return SEOSuggestResult(base_keyword=req.base_keyword, keywords=data)
    return SEOSuggestResult(base_keyword=req.base_keyword, keywords=[])


@app.post("/seo/expand", response_model=SEOExpandResult)
async def seo_expand(req: SEOExpandRequest):
    """키워드 확장 — 씨앗 키워드에서 마케팅 키워드 발굴"""
    keys = req.api_keys or {}
    strategy_guide = {
        "broad":    "광범위 확장 — 관련 상위/하위 개념 모두",
        "question": "질문형 확장 — '~하는 방법', '~이란', '왜 ~' 등 의문형",
        "modifier": "수식어 확장 — '최고의', '무료', '2026', 'B2B' 등 수식어 조합",
        "lsi":      "LSI 의미론적 확장 — 동의어, 유사어, 관련 개념",
        "longtail": "롱테일 확장 — 구체적이고 긴 형태의 구체화 키워드",
    }.get(req.strategy, "광범위 확장")

    prompt = f"""키워드 확장 전문가로서 씨앗 키워드를 확장하세요.
씨앗 키워드: {req.seed_keyword}
확장 전략: {req.strategy} ({strategy_guide})

JSON 배열로만 반환 (30개):
[
  {{
    "keyword": "확장 키워드",
    "type": "확장 유형 분류",
    "relevance": 90,
    "monthly_est": "예: 500~3,000"
  }}
]"""

    data, err = await _groq_json(prompt, keys)
    if data and isinstance(data, list):
        return SEOExpandResult(seed_keyword=req.seed_keyword, strategy=req.strategy, expanded=data)
    return SEOExpandResult(seed_keyword=req.seed_keyword, strategy=req.strategy, expanded=[])


@app.post("/seo/bulk", response_model=SEOBulkResult)
async def seo_bulk(req: SEOBulkRequest):
    """대량 키워드 분석 — 최대 50개 키워드 일괄 처리"""
    import asyncio
    keys = req.api_keys or {}
    kws  = req.keywords[:50]

    async def batch_analyze(chunk: list[str]) -> list[dict]:
        kws_str = '\n'.join(f'- {k}' for k in chunk)
        prompt = f"""다음 키워드들을 SEO 분석하세요. ※ AI 추정값.

{kws_str}

JSON 배열로만 반환 (키워드 개수={len(chunk)}개, 모두 포함):
[
  {{
    "keyword": "키워드",
    "intent": "정보형|거래형|탐색형|비교형",
    "competition": "low|medium|high",
    "monthly_search": "범위",
    "recommended": true,
    "notes": "한 줄 코멘트"
  }}
]"""
        data, _ = await _groq_json(prompt, keys)
        return data if isinstance(data, list) else [{"keyword": k, "intent": "", "competition": "medium", "monthly_search": "—", "recommended": False, "notes": "분석 실패"} for k in chunk]

    # 10개씩 배치 처리
    batches = [kws[i:i+10] for i in range(0, len(kws), 10)]
    results = await asyncio.gather(*[batch_analyze(b) for b in batches])
    all_items = [item for batch in results for item in batch]

    items = []
    for raw in all_items:
        try:
            items.append(SEOKeywordItem(**{k: v for k, v in raw.items() if k in SEOKeywordItem.model_fields}))
        except Exception:
            items.append(SEOKeywordItem(keyword=raw.get("keyword", "?"), notes="파싱 오류"))

    return SEOBulkResult(items=items, total=len(items))


# ── SEO Phase1: 크롤러 헬퍼 ───────────────────────────────────

async def _crawl_url(url: str) -> dict:
    """URL 크롤링 → {title, meta, h1[], h2[], h3[], body_text, images_total, images_no_alt}"""
    import httpx
    from bs4 import BeautifulSoup
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    }
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # 스크립트/스타일 제거
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    title       = (soup.find("title") or soup.new_tag("x")).get_text(strip=True)
    meta_tag    = soup.find("meta", attrs={"name": "description"}) or \
                  soup.find("meta", attrs={"property": "og:description"})
    meta_desc   = (meta_tag or {}).get("content", "") if meta_tag else ""
    h1s = [t.get_text(strip=True) for t in soup.find_all("h1")]
    h2s = [t.get_text(strip=True) for t in soup.find_all("h2")]
    h3s = [t.get_text(strip=True) for t in soup.find_all("h3")]
    imgs        = soup.find_all("img")
    no_alt      = sum(1 for i in imgs if not i.get("alt", "").strip())
    body_text   = " ".join(soup.get_text(" ", strip=True).split())

    return {
        "title": title, "meta_description": meta_desc,
        "h1": h1s, "h2": h2s, "h3": h3s,
        "images_total": len(imgs), "images_no_alt": no_alt,
        "body_text": body_text,
    }


def _tech_checks(crawled: dict, keyword: str) -> list[SEOTechCheck]:
    """크롤링 결과 → 기술적 SEO 체크리스트"""
    checks = []
    title = crawled.get("title", "")
    meta  = crawled.get("meta_description", "")
    h1s   = crawled.get("h1", [])
    body  = crawled.get("body_text", "")
    imgs_total  = crawled.get("images_total", 0)
    imgs_no_alt = crawled.get("images_no_alt", 0)

    # Title 길이
    tl = len(title)
    checks.append(SEOTechCheck(
        item="Title 태그 길이", value=f"{tl}자",
        status="ok" if 30 <= tl <= 60 else "warn" if tl < 30 else "error",
        advice="" if 30 <= tl <= 60 else ("너무 짧습니다 (30자 이상 권장)" if tl < 30 else "너무 깁니다 (60자 이하 권장, 검색결과에서 잘림)"),
    ))

    # Meta description 길이
    ml = len(meta)
    checks.append(SEOTechCheck(
        item="Meta Description", value=f"{ml}자" if ml else "없음",
        status="ok" if 80 <= ml <= 160 else "error" if ml == 0 else "warn",
        advice="" if 80 <= ml <= 160 else ("Meta description이 없습니다 — CTR에 직접 영향" if ml == 0 else "권장 범위(80~160자)를 벗어났습니다"),
    ))

    # H1 개수
    h1_count = len(h1s)
    checks.append(SEOTechCheck(
        item="H1 태그", value=f"{h1_count}개",
        status="ok" if h1_count == 1 else "warn" if h1_count == 0 else "error",
        advice="" if h1_count == 1 else ("H1이 없습니다 — 핵심 키워드를 H1에 포함하세요" if h1_count == 0 else f"H1이 {h1_count}개입니다 — 1개만 사용하세요"),
    ))

    # 이미지 Alt 누락
    if imgs_total > 0:
        checks.append(SEOTechCheck(
            item="이미지 Alt 태그", value=f"누락 {imgs_no_alt}/{imgs_total}",
            status="ok" if imgs_no_alt == 0 else "warn" if imgs_no_alt <= imgs_total * 0.3 else "error",
            advice="" if imgs_no_alt == 0 else f"{imgs_no_alt}개 이미지에 Alt 텍스트가 없습니다 — 이미지 SEO 및 접근성에 영향",
        ))

    # 키워드 밀도
    if keyword and body:
        kw_lower  = keyword.lower()
        body_lower = body.lower()
        word_count = len(body.split())
        kw_count   = body_lower.count(kw_lower)
        density    = round(kw_count / max(word_count, 1) * 100, 2) if word_count else 0
        checks.append(SEOTechCheck(
            item=f"키워드 밀도 ({keyword})", value=f"{density}% ({kw_count}회/{word_count}단어)",
            status="ok" if 0.5 <= density <= 3.0 else "warn" if density < 0.5 else "error",
            advice="" if 0.5 <= density <= 3.0 else ("키워드가 너무 적습니다 (0.5% 이상 권장)" if density < 0.5 else "키워드 과다 사용(3% 초과) — 스팸으로 인식될 수 있음"),
        ))

    # 본문 길이
    wc = len(body.split())
    checks.append(SEOTechCheck(
        item="본문 분량", value=f"약 {wc:,}단어",
        status="ok" if wc >= 800 else "warn" if wc >= 400 else "error",
        advice="" if wc >= 800 else ("최소 800단어 이상 권장 (긴 글이 상위 노출에 유리)" if wc < 800 else ""),
    ))

    return checks


@app.post("/seo/crawl", response_model=SEOCrawlResult)
async def seo_crawl(req: SEOCrawlRequest):
    """URL 크롤링 + 기술적 SEO 진단"""
    try:
        crawled = await _crawl_url(req.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"크롤링 실패: {str(e)[:150]}")

    body     = crawled["body_text"]
    wc       = len(body.split())
    kw_lower = req.target_keyword.lower()
    kw_count = body.lower().count(kw_lower) if kw_lower else 0
    density  = round(kw_count / max(wc, 1) * 100, 2) if wc else 0
    checks   = _tech_checks(crawled, req.target_keyword)

    # Groq로 본문 요약 + 상위 키워드 추출
    summary, top_kws = "", []
    if req.api_keys and req.api_keys.get("groq_api_key"):
        snippet = body[:3000]
        prompt = f"""다음 웹페이지 본문을 분석하세요.

본문 (앞부분): {snippet}

JSON만 반환:
{{
  "content_summary": "이 페이지의 핵심 내용 2~3문장 요약",
  "top_keywords": ["자주 등장하는 주요 키워드 10개"]
}}"""
        data, _ = await _groq_json(prompt, req.api_keys)
        if data:
            summary = data.get("content_summary", "")
            top_kws = data.get("top_keywords", [])

    return SEOCrawlResult(
        url=req.url,
        title=crawled["title"],
        meta_description=crawled["meta_description"],
        h1=crawled["h1"], h2=crawled["h2"][:10], h3=crawled["h3"][:15],
        images_total=crawled["images_total"],
        images_no_alt=crawled["images_no_alt"],
        word_count=wc,
        keyword_density=density,
        tech_checks=checks,
        content_summary=summary,
        top_keywords=top_kws,
    )


@app.post("/seo/gap", response_model=SEOGapResult)
async def seo_gap(req: SEOGapRequest):
    """경쟁사 URL vs 내 키워드 Gap 분석"""
    urls = req.competitor_urls[:3]
    crawled_list = []
    for u in urls:
        try:
            c = await _crawl_url(u)
            crawled_list.append(c)
        except Exception:
            pass

    if not crawled_list:
        raise HTTPException(status_code=400, detail="크롤링에 성공한 경쟁사 URL이 없습니다.")

    # 경쟁사 구조 요약
    comp_summaries = []
    for i, c in enumerate(crawled_list):
        h_structure = ", ".join(c["h2"][:8] + c["h3"][:5])
        body_snippet = c["body_text"][:1500]
        comp_summaries.append(f"[경쟁사{i+1}] 제목: {c['title']}\nH구조: {h_structure}\n본문: {body_snippet}")

    comp_text = "\n\n".join(comp_summaries)

    prompt = f"""당신은 SEO 전략가입니다. 경쟁사 콘텐츠를 분석하고 Gap을 찾으세요.

## 내 타겟 키워드
{req.my_keyword}

## 내 콘텐츠 아이디어
{req.my_idea or '(미입력)'}

## 경쟁사 콘텐츠 구조
{comp_text}

## 분석 요청
1. 경쟁사에 있는데 내 아이디어에 없는 키워드/주제
2. 경쟁사에 있는데 내 콘텐츠에 없는 섹션/구조
3. 내가 경쟁사보다 더 잘 다룰 수 있는 부분
4. 추가하면 좋을 섹션 (우선순위 포함)
5. 내 콘텐츠의 현재 경쟁력 점수 (0~100)

JSON만 반환:
{{
  "missing_keywords": ["경쟁사에 있고 내게 없는 키워드 10개"],
  "missing_sections": ["추가해야 할 섹션명 5개"],
  "my_advantages": ["내가 더 잘 다룰 수 있는 포인트 3개"],
  "recommended_additions": [
    {{"section": "섹션명", "reason": "추가 이유", "priority": "high|medium|low"}}
  ],
  "overall_score": 65
}}"""

    data, err = await _groq_json(prompt, req.api_keys or {})
    if not data:
        raise HTTPException(status_code=500, detail=err or "Gap 분석 실패")

    return SEOGapResult(
        my_keyword=req.my_keyword,
        competitors_analyzed=len(crawled_list),
        missing_keywords=data.get("missing_keywords", []),
        missing_sections=data.get("missing_sections", []),
        my_advantages=data.get("my_advantages", []),
        recommended_additions=data.get("recommended_additions", []),
        overall_score=data.get("overall_score", 0),
    )


@app.post("/seo/meta", response_model=SEOMetaResult)
async def seo_meta(req: SEOMetaRequest):
    """SEO Title / Meta Description 자동 생성"""
    prompt = f"""당신은 SEO 카피라이터입니다. 클릭률(CTR)을 높이는 Title과 Description을 작성하세요.

## 입력 정보
- 타겟 키워드: {req.target_keyword}
- 콘텐츠 요약: {req.content_summary or '(미입력)'}
- 브랜드명: {req.brand_name or '(없음)'}
- URL: {req.url or '(없음)'}

## 작성 규칙
Title:
- 반드시 타겟 키워드를 앞쪽에 배치
- 50~60자 (한글 기준)
- 숫자, 연도, 강한 형용사 활용
- 클릭을 유도하는 표현

Description:
- 타겟 키워드 자연스럽게 포함
- 120~155자 (한글 기준)
- 핵심 가치 + CTA (예: "지금 확인하세요")
- 중복 없이 Title과 다른 정보 제공

JSON만 반환:
{{
  "title_candidates": [
    {{"title": "제목1", "length": 52, "score": 90, "reason": "키워드 앞 배치 + 숫자 활용"}},
    {{"title": "제목2", "length": 48, "score": 85, "reason": "질문형으로 클릭 유도"}},
    {{"title": "제목3", "length": 55, "score": 80, "reason": "연도 + 가이드 형식"}}
  ],
  "description_candidates": [
    {{"description": "설명1", "length": 140, "score": 92, "reason": "핵심 혜택 + CTA 포함"}},
    {{"description": "설명2", "length": 135, "score": 87, "reason": "문제-해결 구조"}},
    {{"description": "설명3", "length": 128, "score": 82, "reason": "수치 활용"}}
  ],
  "og_title": "SNS 공유용 OG Title",
  "og_description": "SNS 공유용 OG Description (100자 내외)"
}}"""

    data, err = await _groq_json(prompt, req.api_keys or {})
    if not data:
        raise HTTPException(status_code=500, detail=err or "Meta 생성 실패")

    return SEOMetaResult(
        target_keyword=req.target_keyword,
        title_candidates=data.get("title_candidates", []),
        description_candidates=data.get("description_candidates", []),
        og_title=data.get("og_title", ""),
        og_description=data.get("og_description", ""),
    )


# ── SEO Phase2: Google Search Console ─────────────────────────

_gsc_cache: dict = {}   # site_url → GSCReport (인메모리 캐시)

@app.post("/seo/gsc/connect", response_model=GSCReport)
async def gsc_connect(req: GSCConnectRequest):
    """Google Search Console — Service Account 연동"""
    import json as jl
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        sa_info = jl.loads(req.service_account_json)
        creds   = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
        )
        service = build("searchconsole", "v1", credentials=creds)

        # 최근 28일 데이터
        import datetime
        end   = datetime.date.today().isoformat()
        start = (datetime.date.today() - datetime.timedelta(days=28)).isoformat()

        body = {
            "startDate": start, "endDate": end,
            "dimensions": ["query"],
            "rowLimit": 100,
        }
        resp = service.searchanalytics().query(siteUrl=req.site_url, body=body).execute()
        rows = resp.get("rows", [])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"GSC 연동 실패: {str(e)[:200]}")

    gsc_rows = []
    total_clicks = total_impressions = 0
    for r in rows:
        gsc_rows.append(GSCRow(
            query=r["keys"][0],
            clicks=r.get("clicks", 0),
            impressions=r.get("impressions", 0),
            ctr=round(r.get("ctr", 0) * 100, 2),
            position=round(r.get("position", 0), 1),
        ))
        total_clicks      += r.get("clicks", 0)
        total_impressions += r.get("impressions", 0)

    avg_ctr      = round(total_clicks / max(total_impressions, 1) * 100, 2)
    avg_position = round(sum(r.position for r in gsc_rows) / max(len(gsc_rows), 1), 1)

    # CTR 낮은 기회 감지 (노출 많은데 CTR 낮음)
    opportunities = [
        {"query": r.query, "impressions": r.impressions, "position": r.position,
         "ctr": r.ctr, "advice": "Meta 재작성으로 CTR 개선 가능"}
        for r in sorted(gsc_rows, key=lambda x: x.impressions, reverse=True)
        if r.ctr < 3.0 and r.impressions > 50
    ][:10]

    report = GSCReport(
        site_url=req.site_url,
        date_range=f"{start} ~ {end}",
        total_clicks=total_clicks,
        total_impressions=total_impressions,
        avg_ctr=avg_ctr,
        avg_position=avg_position,
        top_queries=gsc_rows[:20],
        opportunities=opportunities,
    )
    _gsc_cache[req.site_url] = report
    return report


@app.post("/seo/gsc/upload")
async def gsc_csv_upload(file: bytes = None, site_url: str = ""):
    """GSC CSV 수동 업로드 분석 (파일 없이 JSON으로도 가능)"""
    # 프론트에서 CSV 텍스트를 JSON body로 전달
    raise HTTPException(status_code=501, detail="CSV 업로드는 프론트엔드에서 처리합니다.")


@app.post("/seo/gsc/analyze_csv")
async def gsc_analyze_csv(req: dict):
    """GSC CSV 데이터(텍스트) 분석"""
    csv_text   = req.get("csv_text", "")
    api_keys   = req.get("api_keys", {})
    site_url   = req.get("site_url", "내 사이트")

    if not csv_text:
        raise HTTPException(status_code=400, detail="CSV 데이터가 없습니다.")

    import csv, io
    rows = []
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            # GSC 기본 export 컬럼: 쿼리, 클릭수, 노출수, CTR, 게재순위
            query       = row.get("쿼리") or row.get("query") or row.get("Top queries") or ""
            clicks      = int(str(row.get("클릭수") or row.get("clicks") or 0).replace(",", "") or 0)
            impressions = int(str(row.get("노출수") or row.get("impressions") or 0).replace(",", "") or 0)
            ctr_raw     = str(row.get("CTR") or row.get("ctr") or "0%").replace("%", "").replace(",", ".")
            ctr         = round(float(ctr_raw or 0), 2)
            position    = round(float(str(row.get("게재순위") or row.get("position") or 0).replace(",", ".") or 0), 1)
            if query:
                rows.append(GSCRow(query=query, clicks=clicks, impressions=impressions, ctr=ctr, position=position))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV 파싱 실패: {str(e)}")

    if not rows:
        raise HTTPException(status_code=400, detail="파싱된 데이터가 없습니다. GSC 내보내기 형식을 확인하세요.")

    total_clicks      = sum(r.clicks for r in rows)
    total_impressions = sum(r.impressions for r in rows)
    avg_ctr           = round(total_clicks / max(total_impressions, 1) * 100, 2)
    avg_position      = round(sum(r.position for r in rows) / max(len(rows), 1), 1)

    # 기회 감지: 노출 많고 CTR 낮은 쿼리
    opportunities = [
        {"query": r.query, "impressions": r.impressions, "position": r.position,
         "ctr": r.ctr, "advice": "Meta 재작성으로 CTR 개선 가능"}
        for r in sorted(rows, key=lambda x: x.impressions, reverse=True)
        if r.ctr < 3.0 and r.impressions > 20
    ][:10]

    # Groq로 인사이트 생성
    top5 = "\n".join(f"{r.query}: 클릭{r.clicks} 노출{r.impressions} CTR{r.ctr}% 순위{r.position}" for r in rows[:10])
    insights = []
    if api_keys.get("groq_api_key"):
        prompt = f"""다음 Google Search Console 데이터를 분석하고 SEO 개선 인사이트를 제공하세요.

상위 쿼리:
{top5}

평균 CTR: {avg_ctr}% / 평균 순위: {avg_position}

JSON만 반환:
{{
  "insights": [
    {{"type": "기회|문제|트렌드", "title": "인사이트 제목", "description": "구체적인 설명과 개선 방법"}}
  ]
}}"""
        data, _ = await _groq_json(prompt, api_keys)
        if data:
            insights = data.get("insights", [])

    report = GSCReport(
        site_url=site_url,
        date_range="업로드된 CSV 기준",
        total_clicks=total_clicks,
        total_impressions=total_impressions,
        avg_ctr=avg_ctr,
        avg_position=avg_position,
        top_queries=rows[:20],
        opportunities=opportunities,
        low_ctr_pages=[],
    )
    _gsc_cache[site_url] = report
    return {**report.model_dump(), "insights": insights}


@app.get("/seo/gsc/status")
async def gsc_status():
    """연동된 GSC 사이트 목록"""
    return {"connected_sites": list(_gsc_cache.keys())}


# ── Tier 안내 API ──────────────────────────────────────────────

@app.get("/config/tiers")
def get_tiers():
    """사용 가능한 API Tier 목록과 각 기능/비용 정보 반환"""
    return {
        tier.value: {
            "label": TIER_LABELS[tier],
            "features": TIER_FEATURES[tier],
        }
        for tier in ApiTier
    }


@app.get("/config/tiers/{tier_id}")
def get_tier_detail(tier_id: str):
    """특정 Tier 상세 정보 조회"""
    try:
        tier = ApiTier(tier_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 tier: {tier_id}. (tier1 / tier2 / tier3)")
    return {
        "tier": tier.value,
        "label": TIER_LABELS[tier],
        "features": TIER_FEATURES[tier],
        "checklist": _tier_checklist(tier),
    }


@app.post("/config/test_key")
async def test_api_key(body: dict):
    """API 키 유효성 실시간 테스트 — Gemini / Groq"""
    import httpx, json as _json

    key_type = body.get("type", "gemini")          # "gemini" | "groq"
    api_key  = body.get("api_key", "").strip()

    if not api_key:
        raise HTTPException(status_code=400, detail="api_key 가 비어있습니다.")

    # ── Gemini 테스트 (google.genai SDK) ──────────────────────────
    if key_type == "gemini":
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents="한 단어로만 답해: OK"
            )
            text = resp.text or ""
            return {"ok": True, "message": f"✅ Gemini 연결 성공 — 응답: {text.strip()[:40]}"}
        except Exception as e:
            err_str = str(e)
            if "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
                return {"ok": False, "message": "❌ API 키가 유효하지 않습니다. 키를 다시 확인해주세요.", "raw": err_str[:300]}
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                return {"ok": False, "message": "❌ 일일 할당량 초과(429). 내일 다시 시도하거나 새 키를 발급받으세요.", "raw": err_str[:300]}
            if "PERMISSION_DENIED" in err_str or "403" in err_str:
                return {"ok": False, "message": f"❌ 권한 없음(403) — API가 활성화되지 않았거나 서비스 비활성화.", "raw": err_str[:300]}
            return {"ok": False, "message": f"❌ 오류: {err_str[:200]}", "raw": err_str[:300]}

    # ── Groq 테스트 ────────────────────────────────────────────
    if key_type == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": "한 단어로만: OK"}],
            "max_tokens": 10,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, json=payload, headers=headers)
            data = r.json()
            if r.status_code == 200:
                text = data["choices"][0]["message"]["content"]
                return {"ok": True, "message": f"✅ Groq 연결 성공 — 응답: {text.strip()[:40]}"}
            elif r.status_code == 401:
                return {"ok": False, "message": "❌ 인증 실패 (401) — API 키를 확인하세요"}
            elif r.status_code == 429:
                return {"ok": False, "message": "❌ 할당량 초과 (429) — Groq 무료 한도 초과"}
            else:
                err = data.get("error", {}).get("message", "")
                return {"ok": False, "message": f"❌ HTTP {r.status_code} — {err[:80]}"}
        except Exception as e:
            return {"ok": False, "message": f"❌ 연결 실패 — {str(e)[:80]}"}

    raise HTTPException(status_code=400, detail=f"지원하지 않는 key_type: {key_type}")


def _tier_checklist(tier: ApiTier) -> dict:
    """Tier별 .env에 설정해야 할 항목 안내"""
    base = {"GEMINI_API_KEY": "필수", "GROQ_API_KEY": "필수"}
    if tier == ApiTier.TIER_1:
        return {**base, "비고": "나머지 API 키 불필요. Pollinations.ai + data.go.kr 사용"}
    if tier == ApiTier.TIER_2:
        return {
            **base,
            "GOOGLE_TTS_API_KEY": "필수 (결제수단 등록 필요)",
            "HF_API_TOKEN": "필수",
            "MAKE_WEBHOOK_*": "Make.com 웹훅 URL 등록",
            "DATA_GO_KR_KEY": "권장",
        }
    return {
        **base,
        "GOOGLE_TTS_API_KEY": "필수",
        "HF_API_TOKEN": "필수",
        "SERP_API_KEY": "필수 (Tier3 핵심)",
        "MAKE_WEBHOOK_*": "Make.com Core 플랜 웹훅 URL",
    }


# ── 블로그 플랫폼별 생성 ───────────────────────────────────────

BLOG_PLATFORM_PROMPTS = {
    BlogPlatform.NAVER: """
당신은 네이버 블로그 SEO 전문 작가입니다.
네이버 검색 알고리즘에 최적화된 블로그 글을 작성하세요.

주제: {topic}
에이전시: {agency}
톤앤매너: {tone}
타겟: {target}
언어: {language}

네이버 최적화 요구사항:
- 제목: 핵심 키워드 포함, 30자 이내, 클릭 유도 후킹
- 본문: 1500~2000자, 짧은 단락(3~4줄), 소제목(##) 5개 이상
- 키워드 밀도: 핵심 키워드 5~7회 자연스럽게 반복
- 글 하단: 이웃추가/공감 유도 CTA
- 해시태그: 10개 (네이버 검색 최적화)
- 메타설명: 80자 이내 요약

JSON 형식으로만 반환:
{{"title":"...","body":"...","meta_description":"...","hashtags":["#..."],"cta":"..."}}
""",
    BlogPlatform.TISTORY: """
당신은 티스토리 SEO 블로그 전문 작가입니다.

주제: {topic}
에이전시: {agency}
톤앤매너: {tone}
타겟: {target}
언어: {language}

티스토리 최적화 요구사항:
- 제목: SEO 키워드 포함, 구체적 수치/결과 포함
- 본문: 1200~1800자, 구글/다음 SEO 최적화
- 구성: 목차(TOC) → 서론 → 본론(H2 3개) → 결론
- 내부 링크 유도 문장 포함
- 해시태그: 5개
- 메타설명: 검색 결과 미리보기용 160자 이내

JSON 형식으로만 반환:
{{"title":"...","body":"...","meta_description":"...","hashtags":["#..."],"cta":"..."}}
""",
    BlogPlatform.WORDPRESS: """
당신은 워드프레스 SEO 콘텐츠 전문 작가입니다.

주제: {topic}
에이전시: {agency}
톤앤매너: {tone}
타겟: {target}
언어: {language}

워드프레스 최적화 요구사항:
- 제목: Yoast SEO 기준, 핵심 키워드 앞배치, 60자 이내
- 본문: 1000~1500자, H2/H3 계층 구조, 첫 문단에 키워드 포함
- 이미지 alt 텍스트 설명 포함 (이미지 삽입 위치 [IMAGE] 표시)
- 내부/외부 링크 유도 포함
- 해시태그: 5개 (카테고리/태그용)
- 메타설명: 155자 이내 Yoast 기준

JSON 형식으로만 반환:
{{"title":"...","body":"...","meta_description":"...","hashtags":["#..."],"cta":"..."}}
""",
}

VIDEO_PROMPTS = {
    VideoType.SHORTFORM: """
당신은 숏폼 영상 전문 대본 작가입니다.
30~60초 바이럴 숏폼 대본을 작성하세요.

주제: {topic}
에이전시: {agency}
타겟: {target}
언어: {language}

구성 (총 60초):
[훅] 0~3초: 엄지손가락을 멈추게 하는 충격적 첫 문장 (질문 or 반전)
[본론1] 4~20초: 핵심 포인트 1
[본론2] 21~40초: 핵심 포인트 2 + 데이터/사례
[본론3] 41~55초: 핵심 포인트 3
[클로징] 56~60초: 구독/좋아요/링크 CTA

규칙:
- 각 섹션은 [레이블] 형식으로 구분
- 자막용으로 한 문장씩 줄바꿈
- 이모지 1~2개 활용
- 마크다운 없이 plain text
""",
    VideoType.LONGFORM: """
당신은 유튜브 롱폼 영상 전문 대본 작가입니다.
5~10분 분량 정보성 유튜브 영상 대본을 작성하세요.

주제: {topic}
에이전시: {agency}
타겟: {target}
언어: {language}

구성:
[인트로] 0~30초: 시청자 후킹 + 영상에서 얻을 것 예고
[섹션1] 챕터1: 배경/문제 제기 (1~2분)
[섹션2] 챕터2: 핵심 내용 1 + 사례 (2~3분)
[섹션3] 챕터3: 핵심 내용 2 + 데이터 (2~3분)
[섹션4] 챕터4: 실전 적용 팁 (1~2분)
[아웃트로] 요약 + 구독/다음 영상 유도 CTA (30초)

규칙:
- 각 섹션은 [레이블] 형식으로 구분
- 자연스러운 구어체
- 자막용으로 한 문장씩 줄바꿈
- 마크다운 없이 plain text
""",
}


async def _llm_generate(prompt: str, api_keys: dict, tier: str = "tier1") -> str:
    """Gemini API 호출 공통 함수 (google.genai SDK)"""
    text, err = await _gemini_text(prompt, api_keys, tier)
    if err:
        return f'{{"error": "{err}"}}'
    return text


@app.post("/cardnews/plan", response_model=CardNewsPlanResult)
async def plan_cardnews(req: CardNewsPlanRequest):
    """주제 분석 → AI 카드뉴스 장수 추천 + 슬라이드 구성 제안"""
    import re, json as jsonlib

    profile = req.agency_profile or _agency_profile
    keys    = req.api_keys or {}
    gemini_key = keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")

    prompt = f"""당신은 SNS 카드뉴스 기획 전문가입니다.
아래 주제를 분석하여 최적의 카드뉴스 슬라이드 수와 구성을 추천하세요.

주제: {req.topic}
에이전시: {profile.agency_name} / 업종: {profile.industry}
타겟: {profile.target_audience or "일반 비즈니스 독자"}

[슬라이드 수 기준]
- 3~4장: 단일 핵심 메시지, 짧고 강렬한 홍보
- 5~6장: 일반 정보 콘텐츠, 브랜드 스토리
- 7~8장: 튜토리얼/단계 안내, 비교 분석
- 9~10장: 심층 분석, 인포그래픽, 케이스 스터디

JSON 형식으로만 반환:
{{
  "recommended_count": 7,
  "reasoning": "이 주제를 선택한 이유 (2~3문장)",
  "slide_outline": [
    {{"index": 1, "title": "커버 제목", "type": "cover"}},
    {{"index": 2, "title": "슬라이드 제목", "type": "content"}},
    {{"index": 3, "title": "슬라이드 제목", "type": "content"}},
    {{"index": 7, "title": "마무리 CTA", "type": "cta"}}
  ]
}}"""

    raw, _err = await _gemini_text(prompt, {"gemini_api_key": gemini_key}, req.tier)
    if _err:
        return CardNewsPlanResult(
            topic=req.topic, recommended_count=6,
            reasoning=f"AI 연결 실패 ({_err}). 주제 성격상 6장을 기본 추천합니다.",
            slide_outline=[
                SlideOutline(index=1, title="커버", type="cover"),
                SlideOutline(index=2, title="핵심 포인트 1", type="content"),
                SlideOutline(index=3, title="핵심 포인트 2", type="content"),
                SlideOutline(index=4, title="핵심 포인트 3", type="content"),
                SlideOutline(index=5, title="핵심 포인트 4", type="content"),
                SlideOutline(index=6, title="CTA 마무리", type="cta"),
            ]
        )

    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            data = jsonlib.loads(match.group())
            outlines = [SlideOutline(**s) for s in data.get("slide_outline", [])]
            return CardNewsPlanResult(
                topic=req.topic,
                recommended_count=data.get("recommended_count", 6),
                reasoning=data.get("reasoning", ""),
                slide_outline=outlines,
            )
        except Exception:
            pass
    raise HTTPException(status_code=500, detail="카드뉴스 기획 파싱 실패")


# ── SNS 플랫폼별 생성 ─────────────────────────────────────────

_SNS_PROMPTS = {
    SNSPlatform.LINKEDIN: """당신은 링크드인 B2B 콘텐츠 전문 작가입니다.
비즈니스 의사결정자를 대상으로 인사이트 중심 포스트를 작성하세요.

주제: {topic}
핵심 내용 요약: {summary}
에이전시: {agency}
타겟: {target}
톤앤매너: {tone}

링크드인 최적화 요구사항:
- 첫 줄: 스크롤을 멈추게 하는 후킹 문장 (숫자/질문/반전)
- 본문: 3~5개 단락, 각 단락 2~3줄, 줄간격 활용
- 데이터/사례/구체적 수치 포함
- 마지막: 토론 유도 질문 또는 CTA
- 총 800~1500자, 이모지 최소화 (3개 이내)
- 해시태그: 5개 (업계/전문 키워드)

JSON 형식으로만 반환:
{{"title": "첫 줄 후킹 문장", "body": "전체 포스트 본문", "hashtags": ["#태그1", "#태그2", "#태그3", "#태그4", "#태그5"], "cta": "마무리 CTA 문구"}}""",

    SNSPlatform.INSTAGRAM: """당신은 인스타그램 비즈니스 계정 콘텐츠 전문 작가입니다.
비주얼 중심 플랫폼에 최적화된 캡션을 작성하세요.

주제: {topic}
핵심 내용 요약: {summary}
에이전시: {agency}
타겟: {target}
톤앤매너: {tone}

인스타그램 최적화 요구사항:
- 첫 줄(프리뷰): 2줄 이내, 클릭 유도 문장 (이모지 활용)
- 본문: 핵심 내용을 짧은 bullet 또는 줄바꿈으로 구성
- 이모지: 적극 활용 (단락당 1~2개)
- 캡션 총 150~300자 (너무 길면 안 읽힘)
- 해시태그: 20~30개 (관련 키워드 최대화)
- 마지막: 저장/링크 클릭 유도 CTA

JSON 형식으로만 반환:
{{"title": "첫 줄 후킹", "body": "전체 캡션 본문", "hashtags": ["#태그1", "#태그2"], "cta": "CTA 문구"}}""",

    SNSPlatform.THREADS: """당신은 쓰레드(Threads) 플랫폼 전문 콘텐츠 작가입니다.
대화를 유도하는 짧고 흥미로운 시리즈형 글을 작성하세요.

주제: {topic}
핵심 내용 요약: {summary}
에이전시: {agency}
타겟: {target}
톤앤매너: {tone}

쓰레드 최적화 요구사항:
- 1번 글: 호기심을 자극하는 질문 또는 반전 문장 (100자 이내)
- 2~4번 글: 핵심 내용을 짧게 나눠서 연결 (각 150자 이내)
- 마지막 글: 의견 묻기 또는 저장 유도
- 구어체, 친근한 말투, 이모지 적극 활용
- 각 글은 "---" 로 구분
- 해시태그: 3~5개만 (마지막 글에만)

JSON 형식으로만 반환:
{{"title": "첫 번째 글 (후킹)", "body": "전체 시리즈 글 (--- 구분)", "hashtags": ["#태그1", "#태그2", "#태그3"], "cta": "마지막 CTA"}}""",
}


@app.post("/sns/generate", response_model=SNSResult)
async def generate_sns(req: SNSRequest):
    """SNS 플랫폼별 전용 콘텐츠 생성 (링크드인/인스타그램/쓰레드)"""
    import re, json as jsonlib

    profile = req.agency_profile or _agency_profile
    keys    = req.api_keys or {}

    prompt = _SNS_PROMPTS[req.platform].format(
        topic   = req.topic,
        summary = req.seo_summary or req.topic,
        agency  = f"{profile.agency_name} / {profile.industry}",
        target  = profile.target_audience or "기업 의사결정자",
        tone    = profile.tone_and_manner or "전문적이고 신뢰감 있는",
    )

    raw = await _llm_generate(prompt, keys)

    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            d = jsonlib.loads(match.group())
            body = d.get("body", "")
            return SNSResult(
                topic=req.topic,
                platform=req.platform,
                post=SNSPost(
                    platform=req.platform,
                    title=d.get("title", ""),
                    body=body,
                    hashtags=d.get("hashtags", []),
                    cta=d.get("cta", ""),
                    char_count=len(body),
                )
            )
        except Exception:
            pass

    return SNSResult(
        topic=req.topic,
        platform=req.platform,
        post=SNSPost(platform=req.platform, body=raw[:2000], char_count=len(raw[:2000]))
    )


@app.post("/blog/generate", response_model=BlogResult)
async def generate_blog(req: BlogRequest):
    """블로그 플랫폼별 최적화 글 생성 (네이버/티스토리/워드프레스)"""
    import asyncio, json, re
    profile = req.agency_profile or _agency_profile
    keys = req.api_keys or {}

    async def gen_one(platform: BlogPlatform) -> BlogPost:
        prompt_tpl = BLOG_PLATFORM_PROMPTS[platform]
        prompt = prompt_tpl.format(
            topic=req.topic,
            agency=f"{profile.agency_name} / {profile.industry}",
            tone=profile.tone_and_manner or "전문적이고 신뢰감 있는",
            target=profile.target_audience or "기업 의사결정자",
            language=req.language,
        )
        raw = await _llm_generate(prompt, keys)
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                d = json.loads(match.group())
                body = d.get("body", "")
                return BlogPost(
                    platform=platform,
                    title=d.get("title", ""),
                    body=body,
                    meta_description=d.get("meta_description", ""),
                    hashtags=d.get("hashtags", []),
                    cta=d.get("cta", ""),
                    word_count=len(body),
                )
            except Exception:
                pass
        return BlogPost(platform=platform, title="[파싱 실패]", body=raw[:2000], word_count=len(raw[:2000]))

    posts = await asyncio.gather(*[gen_one(p) for p in req.platforms])
    return BlogResult(topic=req.topic, posts=list(posts))


# ── 카드뉴스 생성 (최대 10장) ──────────────────────────────────

_CARD_NEWS_PROMPT = """당신은 SNS 카드뉴스 전문 콘텐츠 작가입니다.
아래 주제로 인스타그램/링크드인에 최적화된 카드뉴스 슬라이드를 작성하세요.

주제: {topic}
슬라이드 수: {slide_count}장
언어: {language}
에이전시: {agency}
타겟: {target}
톤앤매너: {tone}

[슬라이드 구성 규칙]
- 1번 슬라이드: 후킹 커버 — 제목(20자 이내) + 부제(30자 이내), 스크롤을 멈추게 하는 문장
- 2번~{last_content}번 슬라이드: 핵심 내용 — 제목(15자 이내) + 본문(40자 이내)
- {slide_count}번 슬라이드: CTA 마무리 — 저장/팔로우/댓글 유도

반드시 아래 JSON 형식으로만 반환 (다른 텍스트 없이):
{{
  "hook_title": "카드뉴스 전체 제목",
  "slides": [
    {{"index": 1, "title": "커버 제목", "body": "부제 또는 요약", "is_cta": false}},
    {{"index": 2, "title": "슬라이드 제목", "body": "핵심 내용", "is_cta": false}},
    ...
    {{"index": {slide_count}, "title": "마무리", "body": "CTA 문구", "is_cta": true}}
  ],
  "hashtags": ["#태그1", "#태그2", "#태그3", "#태그4", "#태그5"],
  "cta": "댓글/저장/팔로우 유도 문구"
}}"""


@app.post("/cardnews/generate", response_model=CardNewsResult)
async def generate_cardnews(req: CardNewsRequest):
    """카드뉴스 슬라이드 생성 (3~10장 선택 가능)"""
    import re, json as jsonlib

    profile = req.agency_profile or _agency_profile
    keys    = req.api_keys or {}
    gemini_key = keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")

    prompt = _CARD_NEWS_PROMPT.format(
        topic        = req.topic,
        slide_count  = req.slide_count,
        last_content = req.slide_count - 1,
        language     = req.language,
        agency       = profile.agency_name or "미설정",
        target       = profile.target_audience or "일반 비즈니스 독자",
        tone         = profile.tone_and_manner or "전문적이고 신뢰감 있는",
    )

    raw, _err = await _gemini_text(prompt, {"gemini_api_key": gemini_key}, req.tier)
    if _err:
        raise HTTPException(status_code=500, detail=f"LLM 오류: {_err}")

    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise HTTPException(status_code=500, detail=f"응답 파싱 실패: {raw[:300]}")

    try:
        data = jsonlib.loads(match.group())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JSON 파싱 실패: {e}")

    slides = [
        CardNewsSlide(
            index  = s.get("index", i + 1),
            title  = s.get("title", ""),
            body   = s.get("body", ""),
            is_cta = s.get("is_cta", False),
        )
        for i, s in enumerate(data.get("slides", []))
    ]

    return CardNewsResult(
        topic       = req.topic,
        slide_count = req.slide_count,
        hook_title  = data.get("hook_title", ""),
        slides      = slides,
        hashtags    = data.get("hashtags", []),
        cta         = data.get("cta", ""),
    )


# ── 영상 대본 생성 ─────────────────────────────────────────────

@app.post("/video/generate", response_model=VideoResult)
async def generate_video(req: VideoRequest):
    """숏폼 / 롱폼 영상 대본 생성 + SRT + CapCut JSON"""
    import re, json as jsonlib
    profile = req.agency_profile or _agency_profile
    keys = req.api_keys or {}

    prompt = VIDEO_PROMPTS[req.video_type].format(
        topic=req.topic,
        agency=f"{profile.agency_name} / {profile.industry}",
        target=profile.target_audience or "기업 의사결정자",
        language=req.language,
    )

    raw = await _llm_generate(prompt, keys)

    # 섹션 파싱 ([레이블] 형식)
    sections: list[VideoSection] = []
    lines = raw.split('\n')
    current_label, current_lines = "", []
    dur_map = {"훅":5,"인트로":30,"본론1":20,"본론2":20,"본론3":15,"클로징":10,
               "섹션1":90,"섹션2":150,"섹션3":150,"섹션4":90,"아웃트로":30}

    for line in lines:
        m = re.match(r'\[([^\]]+)\]', line)
        if m:
            if current_label and current_lines:
                lbl = current_label.split(']')[0].strip()
                sections.append(VideoSection(label=f"[{lbl}]", text='\n'.join(current_lines).strip(), duration_sec=dur_map.get(lbl, 30)))
            current_label = m.group(1)
            current_lines = [line[m.end():].strip()] if line[m.end():].strip() else []
        elif line.strip():
            current_lines.append(line.strip())
    if current_label and current_lines:
        sections.append(VideoSection(label=f"[{current_label}]", text='\n'.join(current_lines).strip(), duration_sec=dur_map.get(current_label, 30)))

    script_plain = re.sub(r'\[[^\]]+\]\s*', '', raw).strip()

    # SRT 생성
    srt_lines, t = [], 0
    for i, line in enumerate([l for l in raw.split('\n') if l.strip()]):
        e = t + 3
        srt_lines.append(f"{i+1}\n{_srt(t)} --> {_srt(e)}\n{line.strip()}\n")
        t = e
    srt_content = "\n".join(srt_lines)

    # CapCut JSON
    capcut = {
        "version": "1.0", "topic": req.topic, "type": req.video_type.value,
        "tracks": [
            {"type": "text", "segments": [{"index": i, "text": s.text[:100], "start_ms": i*3000, "end_ms": (i+1)*3000} for i, s in enumerate(sections)]},
            {"type": "subtitle", "source": "subtitle.srt"},
        ],
        "metadata": {"resolution": "1080x1920" if req.video_type == VideoType.SHORTFORM else "1920x1080", "fps": 30}
    }

    # 제목 추출 (첫 줄 또는 인트로 섹션)
    title_line = next((s.text.split('\n')[0] for s in sections if '훅' in s.label or '인트로' in s.label), req.topic)

    # 썸네일 생성 (요청 시)
    thumbnails = []
    if req.generate_thumbnails:
        import urllib.parse
        prompts_th = [
            f"YouTube thumbnail {req.video_type.value}, {req.topic}, bold title, high contrast",
            f"viral thumbnail {req.topic}, eye-catching colors, professional",
            f"B2B content thumbnail {req.topic}, minimalist corporate design",
        ]
        async with __import__('httpx').AsyncClient(timeout=20.0) as client:
            for i, p in enumerate(prompts_th):
                url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(p)}&width=1280&height=720&nologo=true"
                thumbnails.append({"index": i+1, "url": url, "prompt": p})

    return VideoResult(
        topic=req.topic,
        video_type=req.video_type,
        title=title_line[:80],
        sections=sections,
        full_script=raw,
        script_plain=script_plain,
        srt_content=srt_content,
        capcut_json=capcut,
        thumbnails=thumbnails,
    )


def _srt(sec: int) -> str:
    h, r = divmod(sec, 3600); m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d},000"


# ── 롱폼 → 숏폼 변환 ──────────────────────────────────────────

_STRATEGY_LABELS = {
    "hook_first": "훅 우선 — 첫 3초 임팩트 극대화",
    "key_point":  "핵심 포인트 — 가장 중요한 1가지만",
    "story":      "스토리 — 문제→해결 구조로 압축",
    "list":       "리스트 — Top 3 요약형",
}
_PLATFORM_LABELS = {
    "youtube_shorts":  "YouTube Shorts",
    "instagram_reels": "Instagram Reels",
    "tiktok":          "TikTok",
}

_CONVERT_PROMPT = """당신은 숏폼 영상 대본 전문 작가입니다.
아래 롱폼 콘텐츠를 {platform} 용 {duration}초 숏폼 대본으로 변환하세요.

[원본 콘텐츠]
{source}

[변환 설정]
- 플랫폼: {platform_label}
- 목표 길이: {duration}초 (약 {word_count}자 분량)
- 추출 전략: {strategy_label}
- 언어: {language}
- 에이전시: {agency}

[작성 규칙]
- [훅]: 첫 3초 안에 시청자를 멈추게 하는 충격/질문/반전 문장
- [본론]: 핵심 메시지 1~2가지 (전략에 따라 구성)
- [클로징]: 구독/좋아요/저장 유도 CTA
- 각 줄은 자막으로 읽히도록 짧게 (15자 이내 권장)
- 마크다운 없이 plain text

반드시 아래 JSON 형식으로만 반환 (다른 텍스트 없이):
{{
  "title": "숏폼 제목 (60자 이내)",
  "sections": [
    {{"label": "[훅]",    "text": "대사 내용", "duration_sec": 5}},
    {{"label": "[본론]",  "text": "대사 내용", "duration_sec": {body_sec}}},
    {{"label": "[클로징]","text": "대사 내용", "duration_sec": 5}}
  ],
  "caption_lines": ["자막 라인1", "자막 라인2", "..."]
}}"""


@app.post("/video/convert", response_model=ConvertResult)
async def convert_to_shortform(req: ConvertRequest):
    """롱폼 콘텐츠(블로그/영상대본) → 숏폼 대본 변환"""
    import re, json as jsonlib

    profile = req.agency_profile or _agency_profile
    keys = req.api_keys or {}
    gemini_key = keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")

    # 자 수 기준: 한국어 1초 ≈ 4~5자
    word_count = req.duration_sec * 4
    body_sec   = max(5, req.duration_sec - 10)

    prompt = _CONVERT_PROMPT.format(
        source        = req.source_text[:6000],  # 토큰 제한
        platform      = req.platform,
        platform_label= _PLATFORM_LABELS.get(req.platform, req.platform),
        duration      = req.duration_sec,
        word_count    = word_count,
        strategy_label= _STRATEGY_LABELS.get(req.strategy, req.strategy),
        body_sec      = body_sec,
        language      = req.language,
        agency        = f"{profile.agency_name} / {profile.industry}" if profile.agency_name else "미설정",
    )

    raw = ""
    raw, _err = await _gemini_text(prompt, {"gemini_api_key": gemini_key}, req.tier)
    if _err:
        raise HTTPException(status_code=500, detail=f"LLM 오류: {_err}")

    # JSON 파싱
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise HTTPException(status_code=500, detail=f"응답 파싱 실패: {raw[:300]}")

    try:
        data = jsonlib.loads(match.group())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JSON 파싱 실패: {e}")

    sections = [
        VideoSection(
            label       = s.get("label", ""),
            text        = s.get("text", ""),
            duration_sec= s.get("duration_sec", 10),
        )
        for s in data.get("sections", [])
    ]

    full_script  = "\n\n".join(f"{s.label}\n{s.text}" for s in sections)
    script_plain = "\n".join(s.text for s in sections)

    # SRT 생성
    caption_lines = data.get("caption_lines", script_plain.split('\n'))
    caption_lines = [l.strip() for l in caption_lines if l.strip()]
    srt_blocks, t = [], 0
    for i, line in enumerate(caption_lines):
        e = t + 3
        srt_blocks.append(f"{i+1}\n{_srt(t)} --> {_srt(e)}\n{line}\n")
        t = e
    srt_content = "\n".join(srt_blocks)

    return ConvertResult(
        platform      = req.platform,
        duration_sec  = req.duration_sec,
        strategy      = req.strategy,
        title         = data.get("title", ""),
        sections      = sections,
        full_script   = full_script,
        script_plain  = script_plain,
        caption_lines = caption_lines,
        srt_content   = srt_content,
    )


# ── [1~3단계] 콘텐츠 생성 파이프라인 실행 ─────────────────────

@app.post("/pipeline/start", response_model=PipelineJob)
async def start_pipeline(request: ContentRequest, background_tasks: BackgroundTasks):
    """
    Stage 1~3 자동 실행:
    1. 트렌드 수집 → 2. OSMU 텍스트 생성 → 3. TTS/썸네일 생성
    완료 후 /pipeline/{job_id} 로 결과 확인
    """
    job_id = str(uuid.uuid4())[:8]
    job = PipelineJob(job_id=job_id, request=request, current_stage=0)
    jobs[job_id] = job

    background_tasks.add_task(_run_pipeline, job_id, request)
    return job


async def _run_pipeline(job_id: str, request: ContentRequest):
    job = jobs[job_id]
    try:
        # Stage 1
        job.current_stage = 1
        job.stage1 = await stage1_input.run(request)

        # Stage 2
        job.current_stage = 2
        job.stage2 = await stage2_osmu.run(request, job.stage1)

        # Stage 3
        job.current_stage = 3
        job.stage3 = await stage3_visual.run(
            job.stage2, job_id,
            lang=request.language,
            tier=request.tier,
            hf_token=request.api_keys.resolve("hf_api_token"),
            tts_key=request.api_keys.resolve("google_tts_api_key"),
        )

        job.current_stage = 4  # 검수 대기
    except Exception as e:
        job.error = str(e)
        print(f"[Pipeline Error] job_id={job_id} stage={job.current_stage} error={e}")


@app.get("/pipeline/{job_id}", response_model=PipelineJob)
def get_job(job_id: str):
    """파이프라인 진행 상태 및 결과 조회"""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    return job


# ── [4단계] 검수 및 링크 체인 설정 ────────────────────────────

@app.post("/pipeline/{job_id}/review", response_model=PipelineJob)
async def run_review(
    job_id: str,
    blog_url: str = "",
    sns_links: dict = {},
    link_config: LinkChainConfig = LinkChainConfig(),
):
    """
    Stage 4: 링크 체인 삽입 및 검수 대기 상태 생성.
    마케터가 대시보드에서 blog_url, sns_links(링크드인/인스타 등)를 입력 후 호출.
    """
    job = jobs.get(job_id)
    if not job or not job.stage2:
        raise HTTPException(status_code=400, detail="Stage 2 완료 후 호출해주세요.")

    job.stage4 = await stage4_review.run(
        stage2=job.stage2,
        stage3=job.stage3,
        link_config=link_config,
        blog_url=blog_url,
        sns_links=sns_links,
    )
    return job


@app.post("/pipeline/{job_id}/approve", response_model=PipelineJob)
def approve_job(job_id: str):
    """검수 승인 (마케터 대시보드에서 '승인' 버튼)"""
    job = jobs.get(job_id)
    if not job or not job.stage4:
        raise HTTPException(status_code=400, detail="Stage 4 완료 후 승인 가능합니다.")
    job.stage4.status = ApprovalStatus.APPROVED
    return job


@app.post("/pipeline/{job_id}/reject", response_model=PipelineJob)
def reject_job(job_id: str, reason: str = ""):
    """검수 반려"""
    job = jobs.get(job_id)
    if not job or not job.stage4:
        raise HTTPException(status_code=400, detail="Stage 4 완료 후 반려 가능합니다.")
    job.stage4.status = ApprovalStatus.REJECTED
    job.stage4.review_notes = reason
    return job


# ── [5단계] 배포 트리거 ────────────────────────────────────────

@app.post("/pipeline/{job_id}/publish", response_model=PipelineJob)
async def publish_job(job_id: str, publish_request: PublishRequest):
    """
    Stage 5: Make.com 웹훅으로 승인된 콘텐츠 배포.
    승인(approved) 상태에서만 실행 가능.
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if not job.stage4 or job.stage4.status != ApprovalStatus.APPROVED:
        raise HTTPException(status_code=400, detail="승인 완료 후 배포 가능합니다.")

    job.publish_results = await stage5_publish.run(
        request=publish_request,
        stage2=job.stage2,
        stage4=job.stage4,
    )
    job.current_stage = 5
    return job


# ── 유틸리티 ──────────────────────────────────────────────────

@app.get("/jobs")
def list_pipeline_jobs():
    """전체 파이프라인 Job 목록 (대시보드용)"""
    return [
        {
            "job_id": j.job_id,
            "topic": j.request.topic,
            "stage": j.current_stage,
            "status": j.stage4.status if j.stage4 else "processing",
            "error": j.error,
        }
        for j in jobs.values()
    ]


# ════════════════════════════════════════════════════════
#  에이전시 API  (CMO → 팀장 → 팀원 1~4)
# ════════════════════════════════════════════════════════

@app.post("/agency/run")
async def agency_run(req: dict, background_tasks: BackgroundTasks):
    """전체 에이전시 파이프라인 백그라운드 실행

    Body:
      agency_profile: {name, industry, target, tone, keywords, services}
      api_keys:       {groq_api_key, gemini_api_key}
      cmo_schedule:   {platforms, days, time, date_start, date_end}
    """
    try:
        cmo = _agency.CMOSchedule(**req.get("cmo_schedule", {}))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"cmo_schedule 형식 오류: {e}")

    job = _agency.AgencyJob(
        agency_profile=req.get("agency_profile", {}),
        api_keys=req.get("api_keys", {}),
        cmo_schedule=cmo,
    )
    _agency.save_job(job)
    background_tasks.add_task(_agency.run_full_pipeline, job)
    return {"job_id": job.job_id, "status": job.status, "message": "에이전시 파이프라인 시작됨. /agency/status/{job_id} 로 진행 상황을 확인하세요."}


@app.post("/agency/cmo/schedule")
async def agency_cmo_schedule(req: dict):
    """CMO: 배포 일정 수립 (단독)"""
    try:
        cmo = _agency.CMOSchedule(**req.get("cmo_schedule", {}))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"cmo_schedule 형식 오류: {e}")

    job = _agency.AgencyJob(
        agency_profile=req.get("agency_profile", {}),
        api_keys=req.get("api_keys", {}),
        cmo_schedule=cmo,
    )
    job = await _agency.run_cmo_schedule(job)
    return job


@app.post("/agency/lead/plan")
async def agency_lead_plan(req: dict):
    """팀장: SEO 기획 (단독)
    기존 job_id 제공 시 해당 Job 이어서 실행.
    없으면 CMO 스케줄까지 자동 생성 후 기획 수행.
    """
    job_id = req.get("job_id")
    job = _agency.get_job(job_id) if job_id else None

    if not job:
        try:
            cmo = _agency.CMOSchedule(**req.get("cmo_schedule", {}))
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"cmo_schedule 형식 오류: {e}")
        job = _agency.AgencyJob(
            agency_profile=req.get("agency_profile", {}),
            api_keys=req.get("api_keys", {}),
            cmo_schedule=cmo,
        )
        job = await _agency.run_cmo_schedule(job)
    else:
        # api_keys 업데이트 허용
        if req.get("api_keys"):
            job.api_keys = req["api_keys"]

    job = await _agency.run_lead_plan(job)
    return job


@app.post("/agency/member/blog")
async def agency_member_blog(req: dict):
    """팀원1: 블로그 생성 (단독)"""
    job = _agency.get_job(req.get("job_id", ""))
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다. /agency/lead/plan 을 먼저 실행하세요.")
    if req.get("api_keys"):
        job.api_keys = req["api_keys"]
    job = await _agency.run_member_blog(job)
    return job


@app.post("/agency/member/sns/text")
async def agency_member_sns_text(req: dict):
    """팀원2: 텍스트형 SNS 생성 (단독)"""
    job = _agency.get_job(req.get("job_id", ""))
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if req.get("api_keys"):
        job.api_keys = req["api_keys"]
    job = await _agency.run_member_sns_text(job)
    return job


@app.post("/agency/member/sns/image")
async def agency_member_sns_image(req: dict):
    """팀원3: 이미지형 SNS 생성 (단독)"""
    job = _agency.get_job(req.get("job_id", ""))
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if req.get("api_keys"):
        job.api_keys = req["api_keys"]
    job = await _agency.run_member_sns_image(job)
    return job


@app.post("/agency/member/video")
async def agency_member_video(req: dict):
    """팀원4: 영상 대본 생성 (단독)"""
    job = _agency.get_job(req.get("job_id", ""))
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if req.get("api_keys"):
        job.api_keys = req["api_keys"]
    job = await _agency.run_member_video(job)
    return job


@app.post("/agency/lead/review")
async def agency_lead_review(req: dict):
    """팀장: 최종검수 (단독)"""
    job = _agency.get_job(req.get("job_id", ""))
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if req.get("api_keys"):
        job.api_keys = req["api_keys"]
    job = await _agency.run_lead_review(job)
    return job


@app.get("/agency/status/{job_id}")
async def agency_status(job_id: str):
    """에이전시 Job 진행 상태 조회"""
    job = _agency.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    return job


@app.get("/agency/jobs")
async def agency_jobs():
    """에이전시 Job 전체 목록"""
    return [
        {
            "job_id":       j.job_id,
            "status":       j.status,
            "current_step": j.current_step,
            "created_at":   j.created_at,
            "updated_at":   j.updated_at,
            "error":        j.error,
            "weeks":        j.lead_plan.total_weeks if j.lead_plan else 0,
            "posts":        j.lead_plan.total_posts if j.lead_plan else 0,
        }
        for j in _agency.list_jobs()
    ]


# ═══════════════════════════════════════════════════════
# 외부 플랫폼 연결 테스트
# ═══════════════════════════════════════════════════════

@app.post("/platform/test/{platform}")
async def platform_test(platform: str, req: dict):
    """외부 플랫폼 연결 테스트"""
    import httpx

    async def _test_naver(cfg):
        cid = cfg.get("client_id", "")
        sec = cfg.get("client_secret", "")
        if not cid or not sec:
            return False, "Client ID 또는 Client Secret이 없습니다."
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                "https://openapi.naver.com/v1/search/blog.json",
                params={"query": "test", "display": 1},
                headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec},
            )
        return r.status_code == 200, f"HTTP {r.status_code}"

    async def _test_wordpress(cfg):
        url = cfg.get("site_url", "").rstrip("/")
        user = cfg.get("username", "")
        pw   = cfg.get("app_password", "")
        if not url or not user or not pw:
            return False, "사이트 URL, 사용자명, 앱 비밀번호가 필요합니다."
        import base64
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{url}/wp-json/wp/v2/users/me",
                            headers={"Authorization": f"Basic {token}"})
        return r.status_code == 200, f"HTTP {r.status_code}"

    async def _test_tistory(cfg):
        token = cfg.get("access_token", "")
        blog  = cfg.get("blog_name", "").replace("https://","").replace(".tistory.com","")
        if not token or not blog:
            return False, "Access Token과 블로그 주소가 필요합니다."
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                "https://www.tistory.com/apis/blog/info",
                params={"access_token": token, "output": "json"},
            )
        return r.status_code == 200, f"HTTP {r.status_code}"

    async def _test_meta(cfg):
        token = cfg.get("access_token", "")
        if not token:
            return False, "Page Access Token이 없습니다."
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get("https://graph.facebook.com/v19.0/me",
                            params={"access_token": token})
        ok = r.status_code == 200 and "id" in r.json()
        return ok, r.json().get("name", f"HTTP {r.status_code}")

    async def _test_ga4(cfg):
        if not cfg.get("measurement_id") or not cfg.get("property_id"):
            return False, "Measurement ID와 Property ID가 필요합니다."
        if not cfg.get("service_account"):
            return False, "Service Account JSON이 없습니다."
        return True, "자격증명 저장됨 (실제 검증은 첫 데이터 조회 시)"

    async def _test_gsc(cfg):
        if not cfg.get("site_url") or not cfg.get("service_account"):
            return False, "사이트 URL과 Service Account JSON이 필요합니다."
        return True, "자격증명 저장됨 (실제 검증은 첫 데이터 조회 시)"

    testers = {
        "naver": _test_naver,
        "wordpress": _test_wordpress,
        "tistory": _test_tistory,
        "meta": _test_meta,
        "ga4": _test_ga4,
        "gsc": _test_gsc,
    }

    if platform not in testers:
        # 미지원 플랫폼은 자격증명 저장 확인만
        required = {
            "linkedin": ["client_id", "client_secret"],
            "threads":  ["access_token", "user_id"],
            "youtube":  ["client_id", "client_secret", "channel_id"],
            "tiktok":   ["app_key", "app_secret", "access_token"],
        }.get(platform, [])
        missing = [k for k in required if not req.get(k)]
        if missing:
            return {"success": False, "message": f"필수 항목 누락: {', '.join(missing)}"}
        return {"success": True, "message": "자격증명 저장됨 (OAuth 연동은 추후 지원)"}

    try:
        ok, msg = await testers[platform](req)
        return {"success": ok, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── SEO 외부 API ────────────────────────────────────────────────────────────────────────────────

class SeoApiTestRequest(BaseModel):
    service: str
    credentials: dict = {}

@app.post("/seo/api/test")
async def seo_api_test(req: SeoApiTestRequest):
    """​SEO API 연결 테스트"""
    import httpx, hmac, hashlib, base64, time

    svc = req.service
    creds = req.credentials

    if svc == "naver_datalab":
        cid = creds.get("client_id", "")
        sec = creds.get("client_secret", "")
        if not cid or not sec:
            return {"ok": False, "error": "Client ID / Client Secret을 입력해 주세요."}
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.post(
                    "https://openapi.naver.com/v1/datalab/search",
                    headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec, "Content-Type": "application/json"},
                    json={"startDate":"2024-01-01","endDate":"2024-01-31","timeUnit":"month","keywordGroups":[{"groupName":"test","keywords":["마케팅"]}]},
                )
            if r.status_code == 200:
                return {"ok": True}
            elif r.status_code == 401:
                return {"ok": False, "error": "인증 실패 — Client ID/Secret을 확인하세요."}
            else:
                return {"ok": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif svc == "naver_searchad":
        api_key = creds.get("api_key", "")
        secret_key = creds.get("secret_key", "")
        customer_id = creds.get("customer_id", "")
        if not api_key or not secret_key or not customer_id:
            return {"ok": False, "error": "API Key / Secret Key / Customer ID를 모두 입력해 주세요."}
        try:
            timestamp = str(int(time.time() * 1000))
            method = "GET"
            path = "/ncc/campaigns"
            sign_str = f"{timestamp}.{method}.{path}"
            signature = base64.b64encode(
                hmac.new(secret_key.encode(), sign_str.encode(), hashlib.sha256).digest()
            ).decode()
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(
                    f"https://api.naver.com{path}",
                    headers={"X-Timestamp": timestamp, "X-API-KEY": api_key, "X-Customer": customer_id, "X-Signature": signature},
                )
            if r.status_code in (200, 204):
                return {"ok": True}
            elif r.status_code == 401:
                return {"ok": False, "error": "인증 실패 — API Key/Secret을 확인하세요."}
            else:
                return {"ok": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif svc == "gsc":
        if not creds.get("client_id") or not creds.get("client_secret") or not creds.get("site_url"):
            return {"ok": False, "error": "Client ID / Client Secret / 사이트 URL을 모두 입력해 주세요."}
        return {"ok": True, "note": "자격증명이 저장되었습니다. 실제 검증은 첫 조회 시 진행됩니다."}

    return {"ok": False, "error": "알 수 없는 서비스입니다."}


class SeoKeywordFindRequest(BaseModel):
    query: str
    count: int = 20
    naver_datalab: dict = {}
    naver_searchad: dict = {}

@app.post("/seo/keywords/find")
async def seo_keywords_find(req: SeoKeywordFindRequest):
    """키워드 발굴 — 네이버 API 우선, 없으면 Groq AI fallback"""
    import httpx

    keywords = []
    source = "AI 추정값 (API 미연결)"

    # 네이버 데이터랩으로 트렌드 키워드 수집
    dl = req.naver_datalab
    if dl.get("client_id") and dl.get("client_secret"):
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.post(
                    "https://openapi.naver.com/v1/datalab/search",
                    headers={"X-Naver-Client-Id": dl["client_id"], "X-Naver-Client-Secret": dl["client_secret"], "Content-Type": "application/json"},
                    json={
                        "startDate": "2024-10-01", "endDate": "2025-03-31", "timeUnit": "month",
                        "keywordGroups": [{"groupName": req.query, "keywords": [req.query]}]
                    },
                )
            if r.status_code == 200:
                source = "네이버 데이터랩"
        except Exception:
            pass

    # Groq AI로 키워드 추청 (항상 실행하여 풍부한 결과 제공)
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        try:
            prompt = f"""주제: "{req.query}"
다음 JSON 형식으로 SEO 키워드 {req.count}개를 추천하세요. 한국 시장 기준, 실제 검색될 법한 키워드로:
{{"keywords": [{{"keyword": "키워드", "monthly_search": 숫자, "difficulty": "낙음|보통|높음", "intent": "정보|구매|비교"}}]}}"""
            result = await _groq_json(prompt, groq_key)
            if isinstance(result, dict) and "keywords" in result:
                keywords = result["keywords"]
                if source == "AI 추정값 (API 미연결)":
                    source = "AI 추정값"
                else:
                    source = "네이버 데이터랩 + AI 분석"
        except Exception:
            pass

    if not keywords:
        keywords = [{"keyword": req.query + " 방법", "monthly_search": 0, "difficulty": "보통", "intent": "정보"}]

    return {"keywords": keywords[:req.count], "source": source}


class SeoTrendRequest(BaseModel):
    keywords: list[str]
    period: str = "3m"
    naver_datalab: dict = {}

@app.post("/seo/trends/analyze")
async def seo_trends_analyze(req: SeoTrendRequest):
    """트렌드 분석 — Google Trends(pytrends) + 네이버 데이터랩"""
    import httpx
    from datetime import datetime, timedelta

    keywords = req.keywords[:3]
    trend_data: dict = {}
    insights: list[str] = []
    source_parts: list[str] = []

    period_map = {"1m": 30, "3m": 90, "6m": 180, "1y": 365}
    days = period_map.get(req.period, 90)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Google Trends (pytrends)
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="ko-KR", tz=540, timeout=(5, 10))
        pytrends.build_payload(keywords, cat=0, timeframe=f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}", geo="KR")
        df = pytrends.interest_over_time()
        if not df.empty:
            for kw in keywords:
                if kw in df.columns:
                    trend_data[kw] = [{"date": str(d.date()), "value": int(v)} for d, v in zip(df.index, df[kw])]
            source_parts.append("Google Trends")
    except Exception:
        pass

    # 네이버 데이터랩
    dl = req.naver_datalab
    if dl.get("client_id") and dl.get("client_secret"):
        try:
            groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords]
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.post(
                    "https://openapi.naver.com/v1/datalab/search",
                    headers={"X-Naver-Client-Id": dl["client_id"], "X-Naver-Client-Secret": dl["client_secret"], "Content-Type": "application/json"},
                    json={"startDate": start_date.strftime("%Y-%m-%d"), "endDate": end_date.strftime("%Y-%m-%d"), "timeUnit": "week", "keywordGroups": groups},
                )
            if r.status_code == 200:
                data = r.json()
                for item in data.get("results", []):
                    kw = item["title"]
                    if kw not in trend_data:
                        trend_data[kw] = [{"date": d["period"], "value": int(d["ratio"])} for d in item.get("data", [])]
                source_parts.append("네이버 데이터랩")
        except Exception:
            pass

    # AI insights
    if not trend_data:
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            try:
                prompt = f"""키워드 {keywords}의 최근 {req.period} 트렌드를 분석해 주세요.
JSON: {{"keywords": {keywords}, "trend_data": {{{', '.join([f'"{k}": [{{"date":"2025-01","value":50}},{{"date":"2025-02","value":60}},{{"date":"2025-03","value":75}}]' for k in keywords])}}}, "insights": ["인사이트1","인사이트2","인사이트3"]}}"""
                result = await _groq_json(prompt, groq_key)
                if isinstance(result, dict):
                    trend_data = result.get("trend_data", {})
                    insights = result.get("insights", [])
                    source_parts.append("AI 추정값")
            except Exception:
                pass

    # Generate insights from data
    if trend_data and not insights:
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            try:
                summary = {kw: {"avg": sum(p["value"] for p in pts)/len(pts) if pts else 0, "last": pts[-1]["value"] if pts else 0, "first": pts[0]["value"] if pts else 0} for kw, pts in trend_data.items()}
                prompt = (
                    f"다음 트렌드 데이터 요약을 보고 마케터에게 유용한 인사이트 3개를 한국어로 작성하세요: {summary}\n"
                    'JSON: {"insights": ["인사이트1","인사이트2","인사이트3"]}'
                )
                result = await _groq_json(prompt, groq_key)
                insights = result.get("insights", []) if isinstance(result, dict) else []
            except Exception:
                pass

    return {"keywords": keywords, "trend_data": trend_data, "insights": insights, "source": " + ".join(source_parts) if source_parts else "데이터 없음"}


class SeoGscReportRequest(BaseModel):
    days: int = 28
    credentials: dict = {}

@app.post("/seo/gsc/report")
async def seo_gsc_report(req: SeoGscReportRequest):
    """GSC 성과 리포트"""
    creds = req.credentials
    if not creds.get("client_id") or not creds.get("client_secret") or not creds.get("site_url"):
        return {"error": "GSC 자격증명이 없습니다.", "summary": {}, "queries": []}

    # OAuth2 flow가 필요하므로 현재는 안내 메시지 반환
    return {
        "summary": {"clicks": 0, "impressions": 0, "ctr": 0.0, "avg_position": 0.0},
        "queries": [],
        "message": "GSC OAuth2 인증이 필요합니다. 브라우저에서 인증 후 데이터를 조회할 수 있습니다.",
        "note": "OAuth2 구현 예정"
    }

# ── 에이전시 학습 — CSV/Excel 분석 ───────────────────────────────

class AgencyLearnRequest(BaseModel):
    filename: str
    headers: list[str] = []
    preview: str = ""
    row_count: int = 0
    agency_profile: dict = {}

@app.post("/agency/learn/csv")
async def agency_learn_csv(req: AgencyLearnRequest):
    """CSV/Excel 데이터를 AI로 분석해 에이전시 학습 컨텍스트 추출"""
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return {"summary": "AI 분석을 위해 Groq API Key가 필요합니다.", "keywords": [], "insights": [], "type": "general"}

    agency_name = req.agency_profile.get("agency_name") or req.agency_profile.get("name") or "이 브랜드"
    industry = req.agency_profile.get("industry", "")

    prompt = f"""다음은 마케터가 업로드한 CSV/Excel 데이터입니다.

파일명: {req.filename}
컬럼: {', '.join(req.headers)}
행 수: {req.row_count}
미리보기:
{req.preview}

브랜드: {agency_name} ({industry})

이 데이터를 분석해 마케팅에 활용할 수 있는 인사이트를 추출해 주세요.
다음 JSON 형식으로 반환:
{{
  "summary": "이 데이터가 무엇인지 한 줄 요약 + 마케팅 활용 방법",
  "type": "keywords|stats|faq|product|general 중 하나",
  "keywords": ["추출된 SEO 키워드 최대 10개"],
  "insights": ["마케팅 인사이트 3개"],
  "row_count": {req.row_count}
}}"""

    try:
        result = await _groq_json(prompt, groq_key)
        if isinstance(result, dict):
            result["row_count"] = req.row_count
            return result
    except Exception as e:
        pass

    return {
        "summary": f"{req.filename} ({req.row_count}행) 데이터가 학습되었습니다.",
        "type": "general",
        "keywords": [],
        "insights": [],
        "row_count": req.row_count
    }
