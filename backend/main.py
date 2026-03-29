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
    """브라우저에서 /ui 접속 시 랜딩 반환"""
    return FileResponse(str(BASE_DIR / "frontend" / "index.html"))

@app.get("/app.html", include_in_schema=False)
@app.get("/app", include_in_schema=False)
def serve_app():
    """메인 앱 (app.html) 서빙 — 항상 최신 파일 반환"""
    return FileResponse(str(BASE_DIR / "frontend" / "app.html"),
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

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

async def _gemini_text(prompt: str, api_keys: dict, tier: str = "tier1", max_tokens: int = 0) -> tuple[str, str | None]:
    """Gemini 호출 후 텍스트 반환. 429 시 Groq 자동 폴백.
    primary_llm='groq' 이면 Groq 먼저 시도 (Gemini 할당량 절약).
    max_tokens=0 이면 용도별 기본값 자동 적용.
    """
    import os
    # primary_llm 설정 확인 (프론트에서 api_keys에 포함)
    primary_llm = api_keys.get("primary_llm", "gemini")

    groq_key   = api_keys.get("groq_api_key")  or os.getenv("GROQ_API_KEY", "")
    gemini_key = api_keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")

    # 용도별 max_tokens 자동 설정 (0이면 프롬프트 길이 기반 추정)
    # 출력 품질 우선 — 짧은 분석만 줄이고 콘텐츠 생성은 충분히 확보
    if max_tokens == 0:
        prompt_len = len(prompt)
        if prompt_len < 1000:   max_tokens = 1024   # 짧은 분석·키워드 추출
        else:                   max_tokens = 4096   # SNS·블로그 생성은 넉넉하게

    # ── Groq 우선 모드 ──────────────────────────────────────────
    if primary_llm == "groq" and groq_key:
        try:
            from groq import Groq
            gclient = Groq(api_key=groq_key)
            gresp = gclient.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=max_tokens,
            )
            return gresp.choices[0].message.content or "", None
        except Exception as ge:
            err_str = str(ge)
            # Groq도 실패하면 Gemini 폴백
            if not gemini_key:
                return "", f"Groq 오류: {err_str[:150]}"
            # Gemini로 계속 진행

    key = gemini_key
    # tier2/3 = 2.5-flash(고품질), 기본 = 2.0-flash(6배 높은 무료 할당량)
    model_name = "gemini-2.5-flash" if tier in ("tier2", "tier3") else "gemini-2.0-flash"

    if key:
        try:
            from google import genai
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(model=model_name, contents=prompt)
            return resp.text or "", None
        except Exception as e:
            err_str = str(e)
            if "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
                return "", "❌ Gemini API 키가 유효하지 않습니다."
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                # ── Groq 자동 폴백 ───────────────────────────
                groq_key = api_keys.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
                if groq_key:
                    try:
                        from groq import Groq
                        gclient = Groq(api_key=groq_key)
                        gresp = gclient.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.6,
                            max_tokens=max_tokens,
                        )
                        return gresp.choices[0].message.content or "", None
                    except Exception as ge:
                        return "", f"❌ Gemini 할당량 초과 + Groq 폴백 실패: {str(ge)[:100]}"
                return "", "❌ Gemini 일일 할당량 초과(429). Groq API 키를 설정하면 자동 전환됩니다."
            return "", f"Gemini 오류: {err_str[:150]}"

    # Gemini 키 없으면 Groq 직접 시도
    groq_key = api_keys.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
    if groq_key:
        try:
            from groq import Groq
            gclient = Groq(api_key=groq_key)
            gresp = gclient.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=max_tokens,
            )
            return gresp.choices[0].message.content or "", None
        except Exception as ge:
            return "", f"Groq 오류: {str(ge)[:150]}"
    return "", "Gemini API 키가 없습니다. API 설정에서 키를 입력하고 저장해주세요."


async def _gemini_json(prompt: str, api_keys: dict, tier: str = "tier1"):
    """Gemini 호출 후 JSON 파싱. 429 시 Groq 자동 폴백."""
    import re, json as jl, os
    key = api_keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")
    model_name = "gemini-2.5-flash" if tier in ("tier2", "tier3") else "gemini-2.0-flash"
    raw = None

    if key:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            raw = resp.text
        except Exception as e:
            err_str = str(e)
            if "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
                return None, "❌ Gemini API 키가 유효하지 않습니다. API 설정에서 새 키를 입력하세요."
            if "PERMISSION_DENIED" in err_str or "403" in err_str:
                return None, "❌ Gemini API 권한 없음(403). 키가 비활성화됐거나 서비스가 꺼져있습니다."
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                raw = None  # Groq 폴백으로 진행
            else:
                return None, f"Gemini 오류: {err_str[:200]}"

    # Gemini 결과 없으면 Groq 폴백
    if raw is None:
        groq_key = api_keys.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
        if groq_key:
            try:
                from groq import Groq
                gclient = Groq(api_key=groq_key)
                gresp = gclient.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "반드시 유효한 JSON만 반환하세요. 코드블록 없이 순수 JSON만."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                    max_tokens=4096,
                )
                raw = gresp.choices[0].message.content or ""
            except Exception as ge:
                return None, f"Gemini 할당량 초과 + Groq 폴백 실패: {str(ge)[:100]}"
        else:
            if not key:
                return None, "Gemini API 키가 없습니다. API 설정에서 키를 입력하고 저장해주세요."
            return None, "❌ Gemini 일일 할당량 초과(429). Groq API 키를 설정하면 자동 전환됩니다."

    if not raw:
        return None, "빈 응답이 반환됐습니다."
    for pat in (r'\[.*\]', r'\{.*\}'):
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


# ── SEO 기획 퀄리티 향상 — 제목 후보 / 소주제 / 섹션 생성 / 태그 ──────

@app.post("/seo/title-candidates")
async def seo_title_candidates(body: dict):
    """SEO 제목 3종 후보 생성 (수치형·질문형·가이드형)"""
    import json as jsonlib, re
    topic    = body.get("topic", "")
    keywords = body.get("keywords", [])
    api_keys = body.get("api_keys", {})
    tier     = body.get("tier", "tier1")
    profile_data = body.get("agency_profile")
    profile  = AgencyProfile(**profile_data) if isinstance(profile_data, dict) else _agency_profile
    voice_dna_str, voice_samples_str, pillars_str = _build_voice_context(profile)

    kw_str = ", ".join(keywords) if keywords else topic
    current_year = 2026

    prompt = f"""당신은 SEO 카피라이팅 전문가입니다. 아래 주제와 키워드로 3가지 유형의 SEO 최적화 제목을 만들어 각각 분석하세요.

주제: {topic}
키워드: {kw_str}
연도: {current_year}
{voice_dna_str}

3가지 유형:
1. 수치형 — 숫자, 통계, 연도 포함 (예: "5가지", "2026년", "3배")
2. 질문형 — 검색자의 궁금증을 제목으로 (예: "~하는 방법?", "~해야 할까?")
3. 가이드형 — 완전한 가이드/방법 제시 (예: "완벽 가이드", "A to Z", "핵심 정리")

각 제목 SEO 점수 기준 (0-100):
- keyword_in_title: 주요 키워드가 제목 앞부분에 있으면 +20
- length_ok: 30-60자이면 +20
- has_number: 숫자 포함이면 +15
- has_question: 물음표나 질문 형태이면 +15
- has_year: 연도(2024~2027) 포함이면 +10
- intent_match: 검색 의도(정보형/거래형/비교형)에 맞으면 +20

반드시 JSON만 반환:
{{
  "candidates": [
    {{
      "title": "수치형 제목 예시",
      "type": "수치형",
      "seo_score": 85,
      "reasons": {{
        "keyword_in_title": true,
        "length_ok": true,
        "has_number": true,
        "has_question": false,
        "has_year": true,
        "intent_match": true
      }},
      "tip": "키워드를 제목 앞에 배치해 CTR을 높였습니다."
    }},
    {{
      "title": "질문형 제목 예시",
      "type": "질문형",
      "seo_score": 78,
      "reasons": {{
        "keyword_in_title": true,
        "length_ok": true,
        "has_number": false,
        "has_question": true,
        "has_year": false,
        "intent_match": true
      }},
      "tip": "질문형 제목은 정보 탐색 의도에 최적입니다."
    }},
    {{
      "title": "가이드형 제목 예시",
      "type": "가이드형",
      "seo_score": 80,
      "reasons": {{
        "keyword_in_title": true,
        "length_ok": true,
        "has_number": false,
        "has_question": false,
        "has_year": false,
        "intent_match": true
      }},
      "tip": "가이드형은 롱테일 키워드 유입에 유리합니다."
    }}
  ]
}}"""

    raw = await _llm_generate(prompt, api_keys, tier)
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            data = jsonlib.loads(match.group())
            return data
        except Exception:
            pass
    return {"candidates": []}


@app.post("/seo/subtopics")
async def seo_subtopics(body: dict):
    """주제에 대한 H2 소주제 5-7개 추출"""
    import json as jsonlib, re
    topic    = body.get("topic", "")
    keywords = body.get("keywords", [])
    api_keys = body.get("api_keys", {})
    tier     = body.get("tier", "tier1")
    profile_data = body.get("agency_profile")
    profile  = AgencyProfile(**profile_data) if isinstance(profile_data, dict) else _agency_profile
    voice_dna_str, _, pillars_str = _build_voice_context(profile)

    kw_str = ", ".join(keywords) if keywords else topic

    prompt = f"""당신은 SEO 콘텐츠 전략가입니다. 아래 주제로 블로그 포스팅의 H2 소주제 구조를 설계하세요.

주제: {topic}
키워드: {kw_str}
{voice_dna_str}

목표: 검색 의도를 완벽히 충족하고, 독자가 페이지를 끝까지 읽도록 유도하는 소주제 구조.

규칙:
- 5~7개의 H2 소주제
- 논리적 흐름 (도입 → 본론 → 결론 구조)
- 각 소주제는 400~800자 분량으로 작성 가능한 범위
- 핵심 키워드가 자연스럽게 포함되도록 구성

반드시 JSON만 반환:
{{
  "subtopics": [
    {{
      "index": 1,
      "heading": "H2",
      "title": "소주제 제목",
      "description": "이 섹션이 왜 필요한지 한 문장 설명",
      "recommended_chars": 600,
      "key_points": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"]
    }}
  ]
}}"""

    raw = await _llm_generate(prompt, api_keys, tier)
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            data = jsonlib.loads(match.group())
            return data
        except Exception:
            pass
    return {"subtopics": []}


@app.post("/seo/section-generate")
async def seo_section_generate(body: dict):
    """특정 H2 섹션 콘텐츠 생성"""
    topic               = body.get("topic", "")
    subtopic_title      = body.get("subtopic_title", "")
    subtopic_description= body.get("subtopic_description", "")
    key_points          = body.get("key_points", [])
    existing_sections   = body.get("existing_sections", "")
    api_keys            = body.get("api_keys", {})
    tier                = body.get("tier", "tier1")
    profile_data        = body.get("agency_profile")
    profile  = AgencyProfile(**profile_data) if isinstance(profile_data, dict) else _agency_profile
    voice_dna_str, voice_samples_str, _ = _build_voice_context(profile)

    kp_str = "\n".join(f"- {p}" for p in key_points) if key_points else ""
    ctx_str = f"\n\n[앞서 작성된 섹션 요약]\n{existing_sections[:800]}" if existing_sections else ""

    prompt = f"""당신은 SEO 블로그 작가입니다. 아래 소주제에 대한 섹션 내용을 마크다운으로 작성하세요.

전체 주제: {topic}
소주제 제목: {subtopic_title}
섹션 목적: {subtopic_description}
핵심 포인트:
{kp_str}
{voice_dna_str}
{voice_samples_str}
{ctx_str}

작성 규칙:
- ## {subtopic_title} 으로 시작
- 400~700자 분량
- 독자에게 실질적 가치 제공
- 자연스러운 키워드 포함 (키워드 스터핑 금지)
- 마크다운 형식 (소제목, 불릿 등 활용)
- 앞 섹션과 중복 내용 없이 작성

섹션 내용만 반환 (JSON 아님):"""

    content = await _llm_generate(prompt, api_keys, tier)
    return {"section_content": content.strip(), "char_count": len(content.strip())}


@app.post("/seo/tags")
async def seo_tags(body: dict):
    """3계층 태그 시스템 + 플랫폼별 최적화 태그 생성"""
    import json as jsonlib, re
    topic           = body.get("topic", "")
    keywords        = body.get("keywords", [])
    source_document = body.get("source_document", "")
    platforms       = body.get("platforms", ["naver","instagram","linkedin","threads"])
    api_keys        = body.get("api_keys", {})
    tier            = body.get("tier", "tier1")
    profile_data    = body.get("agency_profile")
    profile  = AgencyProfile(**profile_data) if isinstance(profile_data, dict) else _agency_profile
    voice_dna_str, _, _ = _build_voice_context(profile)

    kw_str  = ", ".join(keywords) if keywords else topic
    doc_snip = source_document[:600] if source_document else ""

    prompt = f"""당신은 SNS 마케팅 전문가입니다. 아래 주제와 문서를 분석해 3계층 태그와 플랫폼별 최적화 태그를 생성하세요.

주제: {topic}
키워드: {kw_str}
문서 요약: {doc_snip}
{voice_dna_str}

태그 전략:
1. core_tags (핵심 태그 3~5개): 검색량 최고, 주제 핵심
2. related_tags (관련 태그 5~10개): 롱테일, 세부 주제
3. trend_tags (트렌드 태그 3~5개): 현재 유행, 시의성

플랫폼별 전략:
- naver: SEO 중심, 검색 키워드형 해시태그 10~15개
- instagram: 감성·비주얼·커뮤니티 해시태그 20~30개 (# 포함)
- linkedin: 전문 업계 키워드 3~5개 (영문 혼용)
- threads: 대화 유도, 트렌디한 태그 5~10개

반드시 JSON만 반환:
{{
  "core_tags": ["태그1", "태그2", "태그3"],
  "related_tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "trend_tags": ["태그1", "태그2", "태그3"],
  "by_platform": {{
    "naver": {{
      "tags": ["태그1", "태그2"],
      "count": 12,
      "strategy": "네이버 블로그 검색 최적화 전략 설명"
    }},
    "instagram": {{
      "tags": ["#태그1", "#태그2"],
      "count": 25,
      "strategy": "인스타그램 해시태그 전략 설명"
    }},
    "linkedin": {{
      "tags": ["태그1", "태그2"],
      "count": 4,
      "strategy": "링크드인 태그 전략 설명"
    }},
    "threads": {{
      "tags": ["태그1", "태그2"],
      "count": 7,
      "strategy": "쓰레드 태그 전략 설명"
    }}
  }}
}}"""

    raw = await _llm_generate(prompt, api_keys, tier)
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            data = jsonlib.loads(match.group())
            return data
        except Exception:
            pass
    return {"core_tags": [], "related_tags": [], "trend_tags": [], "by_platform": {}}


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
    BlogPlatform.NAVER: """[CRITICAL] 반드시 한국어로만 작성하세요. 다른 언어 절대 사용 금지.

당신은 네이버 블로그 SEO 전문 작가입니다.
네이버 검색 알고리즘에 최적화된 블로그 글을 작성하세요.

주제: {topic}
에이전시: {agency}
톤앤매너: {tone}
타겟: {target}
언어: {language}
콘텐츠 기둥: {content_pillars}
{voice_dna}
{voice_samples}
{seo_strategy}

네이버 최적화 요구사항:
- 제목: 핵심 키워드 포함, 30자 이내, 클릭 유도 후킹
- 본문: 1500~2000자, 짧은 단락(3~4줄), 소제목(##) 5개 이상
- 키워드 밀도: 핵심 키워드 5~7회 자연스럽게 반복 (위 SEO 키워드 반드시 사용)
- 글 하단: 이웃추가/공감 유도 CTA
- 해시태그: 10개 (네이버 검색 최적화)
- 메타설명: 80자 이내 요약
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
- SEO 기획 전략(소주제 구조·검색 의도·리서치 내용)을 본문에 충분히 반영하세요

JSON 형식으로만 반환:
{{"title":"...","body":"...","meta_description":"...","hashtags":["#..."],"cta":"..."}}
""",
    BlogPlatform.TISTORY: """[CRITICAL] 반드시 한국어로만 작성하세요. 다른 언어 절대 사용 금지.

당신은 티스토리 SEO 블로그 전문 작가입니다.

주제: {topic}
에이전시: {agency}
톤앤매너: {tone}
타겟: {target}
언어: {language}
콘텐츠 기둥: {content_pillars}
{voice_dna}
{voice_samples}
{seo_strategy}

티스토리 최적화 요구사항:
- 제목: SEO 키워드 포함, 구체적 수치/결과 포함
- 본문: 1200~1800자, 구글/다음 SEO 최적화
- 구성: 목차(TOC) → 서론 → 본론(H2 3개 이상, 위 소주제 구조 활용) → 결론
- 내부 링크 유도 문장 포함
- 해시태그: 5개
- 메타설명: 검색 결과 미리보기용 160자 이내
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
- SEO 기획 전략(소주제 구조·검색 의도·리서치 내용)을 본문에 충분히 반영하세요

JSON 형식으로만 반환:
{{"title":"...","body":"...","meta_description":"...","hashtags":["#..."],"cta":"..."}}
""",
    BlogPlatform.WORDPRESS: """[CRITICAL] 반드시 한국어로만 작성하세요. 다른 언어 절대 사용 금지.

당신은 워드프레스 SEO 콘텐츠 전문 작가입니다.

주제: {topic}
에이전시: {agency}
톤앤매너: {tone}
타겟: {target}
언어: {language}
콘텐츠 기둥: {content_pillars}
{voice_dna}
{voice_samples}
{seo_strategy}

워드프레스 최적화 요구사항:
- 제목: Yoast SEO 기준, 핵심 키워드 앞배치, 60자 이내
- 본문: 1000~1500자, H2/H3 계층 구조 (위 소주제 구조 활용), 첫 문단에 키워드 포함
- 이미지 alt 텍스트 설명 포함 (이미지 삽입 위치 [IMAGE] 표시)
- 내부/외부 링크 유도 포함
- 해시태그: 5개 (카테고리/태그용)
- 메타설명: 155자 이내 Yoast 기준
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
- SEO 기획 전략(소주제 구조·검색 의도·리서치 내용)을 본문에 충분히 반영하세요

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
콘텐츠 기둥: {content_pillars}
{voice_dna}
{voice_samples}

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
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
""",
    VideoType.LONGFORM: """
당신은 유튜브 롱폼 영상 전문 대본 작가입니다.
5~10분 분량 정보성 유튜브 영상 대본을 작성하세요.

주제: {topic}
에이전시: {agency}
타겟: {target}
언어: {language}
콘텐츠 기둥: {content_pillars}
{voice_dna}
{voice_samples}

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
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
""",
}


def _build_voice_context(profile) -> tuple[str, str, str]:
    """agency_profile에서 voice_dna, voice_samples, content_pillars 문자열 생성
    토큰 절약: dna 핵심 3필드만, samples 2개로 제한
    """
    voice_dna_str = ""
    if getattr(profile, 'brand_voice_dna', None):
        dna = profile.brand_voice_dna
        parts = []
        if dna.get('sentence_style'): parts.append("스타일: " + dna['sentence_style'])
        if dna.get('tone_keywords'):  parts.append("표현: " + ', '.join(dna['tone_keywords'][:5]))
        if dna.get('avoid'):          parts.append("금지: " + ', '.join(dna['avoid'][:3]))
        if parts:
            voice_dna_str = "보이스DNA: " + " | ".join(parts)

    voice_samples_str = ""
    if getattr(profile, 'brand_voice_samples', None):
        samples = "\n".join(f"- {s[:150]}" for s in profile.brand_voice_samples[:3])
        voice_samples_str = "보이스샘플:\n" + samples

    pillars_str = ""
    if getattr(profile, 'content_pillars', None):
        pillars_str = ', '.join(profile.content_pillars[:5])  # 최대 5개

    return voice_dna_str, voice_samples_str, pillars_str


async def _llm_generate(prompt: str, api_keys: dict, tier: str = "tier1") -> str:
    """LLM 호출 공통 함수. Gemini 우선, 429 시 Groq 자동 폴백."""
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
    SNSPlatform.LINKEDIN: """[CRITICAL] 반드시 한국어로만 작성하세요. 영어·베트남어·중국어 등 다른 언어 절대 사용 금지.

당신은 링크드인 B2B 콘텐츠 전문 작가입니다.
비즈니스 의사결정자를 대상으로 인사이트 중심 포스트를 작성하세요.

주제: {topic}
핵심 내용 요약: {summary}
에이전시: {agency}
타겟: {target}
톤앤매너: {tone}
콘텐츠 기둥: {content_pillars}
{voice_dna}
{voice_samples}
{seo_strategy}

링크드인 최적화 요구사항:
- body 첫 줄: 스크롤을 멈추게 하는 후킹 문장 (숫자/질문/반전) — 빈 줄 후 본문 시작
- 본문: 3~5개 단락, 각 단락 2~3줄, 줄간격 활용
- 데이터/사례/구체적 수치 포함 (SEO 리서치 내용 적극 활용)
- 마지막: 토론 유도 질문 또는 CTA
- 총 800~1500자, 이모지 최소화 (3개 이내)
- 해시태그: 5개 (SEO 키워드 기반으로 선정)
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
- SEO 기획 전략(키워드·검색의도·리서치 내용)을 본문에 충분히 반영하세요

JSON 형식으로만 반환 (body 하나에 후킹 문장 + 본문 전체를 모두 포함):
{{"body": "후킹 문장\\n\\n본문 단락1\\n\\n본문 단락2\\n\\n마무리 CTA", "hashtags": ["#태그1", "#태그2", "#태그3", "#태그4", "#태그5"], "cta": "마무리 CTA 문구"}}""",

    SNSPlatform.INSTAGRAM: """[CRITICAL] 반드시 한국어로만 작성하세요. 영어·베트남어·중국어 등 다른 언어 절대 사용 금지.

당신은 인스타그램 비즈니스 계정 콘텐츠 전문 작가입니다.
비주얼 중심 플랫폼에 최적화된 캡션을 작성하세요.

주제: {topic}
핵심 내용 요약: {summary}
에이전시: {agency}
타겟: {target}
톤앤매너: {tone}
콘텐츠 기둥: {content_pillars}
{voice_dna}
{voice_samples}
{seo_strategy}

인스타그램 최적화 요구사항:
- body 첫 줄(프리뷰): 2줄 이내, 클릭 유도 문장 (이모지 활용)
- 본문: 핵심 내용을 짧은 bullet 또는 줄바꿈으로 구성 (SEO 리서치 핵심 인사이트 활용)
- 이모지: 적극 활용 (단락당 1~2개)
- 캡션 총 150~300자 (너무 길면 안 읽힘)
- 해시태그: 20~30개 (SEO 키워드 기반으로 선정)
- 마지막: 저장/링크 클릭 유도 CTA
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
- SEO 기획 전략(키워드·검색의도·리서치 내용)을 콘텐츠에 충분히 반영하세요

JSON 형식으로만 반환 (body 하나에 캡션 전체 포함):
{{"body": "클릭 유도 첫 줄\\n\\n본문 내용\\n\\nCTA", "hashtags": ["#태그1", "#태그2"], "cta": "CTA 문구"}}""",

    SNSPlatform.THREADS: """[CRITICAL] 반드시 한국어로만 작성하세요. 영어·베트남어·중국어 등 다른 언어 절대 사용 금지.

당신은 쓰레드(Threads) 플랫폼 전문 콘텐츠 작가입니다.
대화를 유도하는 짧고 흥미로운 시리즈형 글을 작성하세요.

주제: {topic}
핵심 내용 요약: {summary}
에이전시: {agency}
타겟: {target}
톤앤매너: {tone}
콘텐츠 기둥: {content_pillars}
{voice_dna}
{voice_samples}
{seo_strategy}

쓰레드 최적화 요구사항:
- 1번 글: 호기심을 자극하는 질문 또는 반전 문장 (100자 이내)
- 2~4번 글: 핵심 내용을 짧게 나눠서 연결 (각 150자 이내, SEO 리서치 인사이트 활용)
- 마지막 글: 의견 묻기 또는 저장 유도
- 구어체, 친근한 말투, 이모지 적극 활용
- 각 글은 "---" 로 구분
- 해시태그: 3~5개만 (마지막 글에만, SEO 키워드 기반)
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
- SEO 기획 전략(키워드·검색의도·리서치 내용)을 콘텐츠에 충분히 반영하세요

JSON 형식으로만 반환 (body 하나에 1번 글부터 전체 시리즈 포함):
{{"body": "1번 글(후킹)\\n---\\n2번 글\\n---\\n3번 글\\n---\\n마지막 글+CTA", "hashtags": ["#태그1", "#태그2", "#태그3"], "cta": "마지막 CTA"}}""",
}


# ── 카드뉴스 이미지 렌더러 (Playwright HTML→PNG) ────────────────────────────

import base64 as _b64m
from pathlib import Path as _FPath

_FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")

_CN_DIMS = {
    "1:1":  (1080, 1080),
    "4:5":  (1080, 1350),
    "9:16": (1080, 1920),
}

# ── 폰트 캐시 (base64) ───────────────────────────────────────────────────────
_CN_FONT_CACHE: dict = {}

def _get_cn_fonts() -> dict:
    """NanumGothic TTF → base64 (최초 1회만 읽어 캐시)"""
    if _CN_FONT_CACHE:
        return _CN_FONT_CACHE
    fdir = _FPath(__file__).parent / "assets" / "fonts"
    for key, fname in [("r", "NanumGothic-Regular.ttf"), ("b", "NanumGothic-Bold.ttf")]:
        try:
            _CN_FONT_CACHE[key] = _b64m.b64encode((fdir / fname).read_bytes()).decode()
        except Exception:
            _CN_FONT_CACHE[key] = ""
    return _CN_FONT_CACHE


def _hex_darken(h: str, factor: float = 0.38) -> str:
    """hex 색상을 factor 만큼 어둡게"""
    h = h.lstrip("#")
    if len(h) != 6:
        return "#0d1117"
    r = max(0, int(int(h[0:2], 16) * (1 - factor)))
    g = max(0, int(int(h[2:4], 16) * (1 - factor)))
    b = max(0, int(int(h[4:6], 16) * (1 - factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _cn_slide_html(slide: dict, design: dict, slide_total: int,
                   hashtags: list, cta: str) -> str:
    """슬라이드 1장 → HTML 문자열 (Playwright로 PNG 캡처용)"""
    fonts    = _get_cn_fonts()
    ratio    = design.get("ratio", "1:1")
    theme    = design.get("theme", "dark")
    brand    = design.get("brand_color", "#1f6feb")
    bname    = design.get("brand_name", "")
    W, H     = _CN_DIMS.get(ratio, (1080, 1080))
    is_cta   = slide.get("is_cta", False) or slide.get("type") == "cta"
    idx      = slide.get("index", 1)
    brand_dk = _hex_darken(brand)

    def esc(s: str) -> str:
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    title_e = esc(slide.get("title", ""))
    body_e  = esc(slide.get("body",  ""))

    # ── 폰트 CSS ─────────────────────────────────────────────
    fc = ""
    if fonts.get("r"):
        fc += (f"@font-face{{font-family:'NG';"
               f"src:url('data:font/truetype;base64,{fonts['r']}') format('truetype');"
               f"font-weight:400;}}")
    if fonts.get("b"):
        fc += (f"@font-face{{font-family:'NG';"
               f"src:url('data:font/truetype;base64,{fonts['b']}') format('truetype');"
               f"font-weight:700;}}")

    # ── 테마 설정 ─────────────────────────────────────────────
    T = {
        "dark":     {"bg": f"background-color:#0f1117",
                     "hbg": "#161928",
                     "tc": "#ffffff", "bc": "rgba(255,255,255,.82)",
                     "xc": "rgba(255,255,255,.5)", "dc": "rgba(255,255,255,.28)"},
        "light":    {"bg": "background-color:#f4f6fb",
                     "hbg": "#ffffff",
                     "tc": "#1a1a2e", "bc": "#4a4a6a",
                     "xc": "#999999", "dc": "rgba(0,0,0,.18)"},
        "vivid":    {"bg": f"background-color:{brand}",
                     "hbg": "rgba(0,0,0,.2)",
                     "tc": "#ffffff", "bc": "rgba(255,255,255,.9)",
                     "xc": "rgba(255,255,255,.7)", "dc": "rgba(255,255,255,.35)"},
        "gradient": {"bg": f"background:linear-gradient(145deg,{brand},{brand_dk})",
                     "hbg": "rgba(0,0,0,.12)",
                     "tc": "#ffffff", "bc": "rgba(255,255,255,.88)",
                     "xc": "rgba(255,255,255,.65)", "dc": "rgba(255,255,255,.32)"},
    }
    t = T.get(theme, T["dark"])

    pad  = int(W * 0.07)
    hh   = int(H * 0.072)   # header height

    # ── CTA 슬라이드 ──────────────────────────────────────────
    if is_cta:
        cta_e  = esc(cta or slide.get("title", "") or "저장하고 팔로우하세요!")
        tags   = "  ".join(hashtags[:6]) if hashtags else ""
        tags_h = (f'<div style="margin-top:{int(H*.028)}px;font-size:{int(H*.026)}px;'
                  f'color:rgba(255,255,255,.72);word-break:break-word;">{esc(tags)}</div>'
                  ) if tags else ""
        bname_h = (f'<div style="position:absolute;bottom:{int(H*.06)}px;width:100%;'
                   f'text-align:center;font-size:{int(H*.022)}px;'
                   f'color:rgba(255,255,255,.5);">{esc(bname)}</div>'
                   ) if bname else ""
        c1 = int(W * .65); c2 = int(W * .48)
        content = f"""
<div style="position:absolute;inset:0;
     background:linear-gradient(145deg,{brand},{brand_dk});overflow:hidden;">
  <div style="position:absolute;top:-{int(H*.18)}px;right:-{int(W*.15)}px;
       width:{c1}px;height:{c1}px;border-radius:50%;
       background:rgba(255,255,255,.07);"></div>
  <div style="position:absolute;bottom:-{int(H*.12)}px;left:-{int(W*.12)}px;
       width:{c2}px;height:{c2}px;border-radius:50%;
       background:rgba(255,255,255,.05);"></div>
  <div style="position:absolute;top:50%;left:50%;
       transform:translate(-50%,-55%);width:{int(W*.86)}px;text-align:center;">
    <div style="font-family:'NG',sans-serif;font-weight:700;
         font-size:{int(H*.052)}px;color:#fff;line-height:1.42;">{cta_e}</div>
    {tags_h}
  </div>
  {bname_h}
</div>"""

    # ── 일반 슬라이드 (커버 포함) ────────────────────────────
    else:
        # 본문 HTML: 줄별로 파싱
        body_parts = []
        for line in slide.get("body", "").split("\n"):
            l = line.strip()
            if not l:
                continue
            if l.startswith("• ") or l.startswith("- "):
                inner = esc(l[2:])
                body_parts.append(
                    f'<div style="display:flex;gap:10px;margin-bottom:{int(H*.01)}px;">'
                    f'<span style="color:{brand};flex-shrink:0;margin-top:2px;">•</span>'
                    f'<span>{inner}</span></div>')
            else:
                body_parts.append(
                    f'<div style="margin-bottom:{int(H*.012)}px;">{esc(l)}</div>')
        body_inner = "".join(body_parts)

        # 진행 점 (dots)
        dots = ""
        if slide_total > 1:
            dot_items = []
            for i in range(1, slide_total + 1):
                if i == idx:
                    dot_items.append(
                        f'<span style="width:12px;height:12px;border-radius:50%;'
                        f'background:{brand};display:inline-block;"></span>')
                else:
                    dot_items.append(
                        f'<span style="width:8px;height:8px;border-radius:50%;'
                        f'background:{t["dc"]};display:inline-block;'
                        f'align-self:center;"></span>')
            dots = (f'<div style="position:absolute;bottom:{int(H*.04)}px;'
                    f'left:0;right:0;display:flex;justify-content:center;'
                    f'align-items:center;gap:8px;">{"".join(dot_items)}</div>')

        # 커버(1번)와 내용 슬라이드의 레이아웃 차이
        is_cover = (idx == 1)
        if is_cover:
            title_top = int(H * .22)
            title_fs  = int(H * .056)
            body_top  = int(H * .46)
            header_html = ""
            accent_bar  = (f'<div style="position:absolute;top:{int(H*.175)}px;'
                           f'left:{pad}px;width:{int(W*.1)}px;height:{int(H*.005)}px;'
                           f'background:{brand};border-radius:3px;"></div>')
            # 커버 장식 원
            deco = (f'<div style="position:absolute;top:-{int(H*.12)}px;'
                    f'right:-{int(W*.1)}px;width:{int(W*.58)}px;height:{int(W*.58)}px;'
                    f'border-radius:50%;background:{brand};opacity:.1;"></div>'
                    f'<div style="position:absolute;bottom:{int(H*.08)}px;'
                    f'left:-{int(W*.08)}px;width:{int(W*.38)}px;height:{int(W*.38)}px;'
                    f'border-radius:50%;background:{brand};opacity:.07;"></div>')
        else:
            title_top = int(H * .135)
            title_fs  = int(H * .046)
            body_top  = int(H * .30)
            header_html = (
                f'<div style="position:absolute;top:0;left:0;right:0;height:{hh}px;'
                f'background:{t["hbg"]};display:flex;align-items:center;'
                f'padding:0 {pad}px;">'
                f'<span style="flex:1;font-family:\'NG\',sans-serif;'
                f'font-size:{int(H*.023)}px;color:{brand};font-weight:400;">'
                f'{esc(bname)}</span>'
                f'<span style="font-family:\'NG\',sans-serif;'
                f'font-size:{int(H*.022)}px;color:{t["xc"]};font-weight:400;">'
                f'{idx:02d}&nbsp;/&nbsp;{slide_total:02d}</span></div>')
            accent_bar = (f'<div style="position:absolute;top:{int(H*.108)}px;'
                          f'left:{pad}px;width:{int(W*.08)}px;height:{int(H*.0048)}px;'
                          f'background:{brand};border-radius:3px;"></div>')
            deco = ""

        content = f"""
<div style="position:absolute;inset:0;{t['bg']};overflow:hidden;">
  {deco}
  {header_html}
  {accent_bar}
  <div style="position:absolute;top:{title_top}px;left:{pad}px;right:{pad}px;
       font-family:'NG',sans-serif;font-weight:700;font-size:{title_fs}px;
       color:{t['tc']};line-height:1.38;">{title_e}</div>
  <div style="position:absolute;top:{body_top}px;left:{pad}px;right:{pad}px;
       bottom:{int(H*.12)}px;font-family:'NG',sans-serif;font-weight:400;
       font-size:{int(H*.029)}px;color:{t['bc']};line-height:1.72;
       overflow:hidden;">{body_inner}</div>
  {dots}
</div>"""

    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
            f'{fc}'
            f'*{{margin:0;padding:0;box-sizing:border-box;}}'
            f'html,body{{width:{W}px;height:{H}px;overflow:hidden;background:transparent;}}'
            f'</style></head><body>{content}</body></html>')


# ── Playwright 브라우저 싱글턴 ─────────────────────────────────────────────
_PW_BROWSER = None
_PW_PLAYWRIGHT = None
_PW_LOCK = None


async def _get_pw_browser():
    global _PW_BROWSER, _PW_PLAYWRIGHT, _PW_LOCK
    import asyncio
    if _PW_LOCK is None:
        _PW_LOCK = asyncio.Lock()
    async with _PW_LOCK:
        if _PW_BROWSER and _PW_BROWSER.is_connected():
            return _PW_BROWSER
        # 기존 인스턴스 정리
        if _PW_PLAYWRIGHT is not None:
            try:
                await _PW_PLAYWRIGHT.__aexit__(None, None, None)
            except Exception:
                pass
        from playwright.async_api import async_playwright
        _PW_PLAYWRIGHT = async_playwright()
        pw = await _PW_PLAYWRIGHT.__aenter__()
        _PW_BROWSER = await pw.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                  "--disable-setuid-sandbox"]
        )
        return _PW_BROWSER


@app.post("/cardnews/render-images")
async def cardnews_render_images(body: dict):
    """
    카드뉴스 슬라이드 → PNG 이미지 (Playwright HTML→Screenshot)
    body: { slides, hashtags, cta, design: {ratio, theme, brand_color, brand_name} }
    """
    slides   = body.get("slides", [])
    hashtags = body.get("hashtags", [])
    cta      = body.get("cta", "")
    design   = body.get("design", {})

    if not slides:
        raise HTTPException(status_code=400, detail="slides가 비어있습니다.")

    total = len(slides)
    ratio = design.get("ratio", "1:1")
    W, H  = _CN_DIMS.get(ratio, (1080, 1080))

    browser = await _get_pw_browser()
    ctx = await browser.new_context(
        viewport={"width": W, "height": H},
        device_scale_factor=2,   # 레티나 2× → 고화질
    )

    results = []
    try:
        for slide in slides:
            html      = _cn_slide_html(slide, design, total, hashtags, cta)
            page      = await ctx.new_page()
            await page.set_content(html, wait_until="networkidle")
            img_bytes = await page.screenshot(
                type="png", full_page=False,
                clip={"x": 0, "y": 0, "width": W, "height": H},
            )
            await page.close()
            results.append({
                "index":     slide.get("index", 0),
                "image_b64": _b64m.b64encode(img_bytes).decode(),
                "width":     W * 2,   # device_scale_factor=2
                "height":    H * 2,
            })
    finally:
        await ctx.close()

    return {
        "images": results,
        "total":  total,
        "ratio":  ratio,
        "theme":  design.get("theme", "dark"),
        "width":  W * 2,
        "height": H * 2,
    }


# ── 카드뉴스 파이프라인 ──────────────────────────────────────────────────────

def _sheets_service(service_account_json: str):
    """Service Account JSON 문자열 → Google Sheets service 객체"""
    import json as _json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds_dict = _json.loads(service_account_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _ensure_sheet_header(service, spreadsheet_id: str, sheet_title: str = "카드뉴스"):
    """시트 존재 확인 + 헤더 행 작성 (없으면 새 시트 생성)"""
    sheets = service.spreadsheets()
    meta = sheets.get(spreadsheetId=spreadsheet_id).execute()
    existing = [s["properties"]["title"] for s in meta["sheets"]]

    if sheet_title not in existing:
        sheets.batchUpdate(spreadsheetId=spreadsheet_id, body={
            "requests": [{"addSheet": {"properties": {"title": sheet_title}}}]
        }).execute()

    headers = [["슬라이드번호", "타입", "제목", "본문", "해시태그", "CTA", "생성일시", "상태", "이미지URL"]]
    sheets.values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_title}!A1:I1",
        valueInputOption="RAW",
        body={"values": headers}
    ).execute()


def _append_slides_to_sheet(service, spreadsheet_id: str, slides: list,
                             hashtags: list, cta: str, topic: str, sheet_title: str = "카드뉴스"):
    """슬라이드 데이터를 시트에 행별 추가"""
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ht  = " ".join(hashtags) if hashtags else ""
    rows = []
    for s in slides:
        rows.append([
            s.get("index", ""),
            s.get("type", "content") if "type" in s else ("cover" if s.get("index") == 1 else ("cta" if s.get("is_cta") else "content")),
            s.get("title", ""),
            s.get("body", ""),
            ht if s.get("is_cta") else "",
            cta if s.get("is_cta") else "",
            now,
            "pending",
            "",
        ])

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_title}!A:I",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows}
    ).execute()
    return len(rows)


@app.post("/cardnews/save-to-sheet")
async def cardnews_save_to_sheet(body: dict):
    """
    카드뉴스 슬라이드 데이터를 Google Sheets에 저장
    body: { slides, hashtags, cta, topic, spreadsheet_id, service_account_json }
    """
    slides   = body.get("slides", [])
    hashtags = body.get("hashtags", [])
    cta      = body.get("cta", "")
    topic    = body.get("topic", "")
    sheet_id = body.get("spreadsheet_id", "")
    sa_json  = body.get("service_account_json", "")

    if not sheet_id:
        raise HTTPException(status_code=400, detail="spreadsheet_id가 필요합니다.")
    if not sa_json:
        raise HTTPException(status_code=400, detail="service_account_json이 필요합니다.")
    if not slides:
        raise HTTPException(status_code=400, detail="저장할 슬라이드가 없습니다.")

    try:
        service    = _sheets_service(sa_json)
        _ensure_sheet_header(service, sheet_id)
        saved_rows = _append_slides_to_sheet(service, sheet_id, slides, hashtags, cta, topic)
        sheet_url  = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        return {
            "success":    True,
            "saved_rows": saved_rows,
            "sheet_url":  sheet_url,
            "sheet_id":   sheet_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"구글시트 저장 실패: {str(e)}")


@app.post("/cardnews/pipeline")
async def cardnews_pipeline(body: dict):
    """
    카드뉴스 전체 자동화 파이프라인
    STEP 1: AI 문구 생성 → STEP 2: 구글시트 저장 → STEP 3: 이미지 렌더링(예정)
    body: {
        topic, slide_count, api_keys, agency_profile, tier,
        spreadsheet_id, service_account_json,
        steps: ["generate","sheet","image"]   ← 실행할 단계 목록
    }
    """
    import re as re_mod

    topic      = body.get("topic", "").strip()
    slide_count= body.get("slide_count", 6)
    api_keys   = body.get("api_keys", {})
    agency     = body.get("agency_profile", {})
    tier       = body.get("tier", "tier1")
    sheet_id   = body.get("spreadsheet_id", "")
    sa_json    = body.get("service_account_json", "")
    steps      = body.get("steps", ["generate", "sheet"])  # image는 Phase 2에 추가

    if not topic:
        raise HTTPException(status_code=400, detail="topic이 필요합니다.")

    result = {
        "topic": topic,
        "steps_done": [],
        "steps_failed": [],
        "step_generate": None,
        "step_sheet": None,
        "step_image": None,
    }

    # ── STEP 1: AI 카드뉴스 생성 ──────────────────────────────────
    if "generate" in steps:
        try:
            ag_name  = agency.get("agency_name", "") if isinstance(agency, dict) else getattr(agency, "agency_name", "")
            industry = agency.get("industry", "")     if isinstance(agency, dict) else getattr(agency, "industry", "")
            tone     = agency.get("tone_and_manner", "전문적이고 신뢰감 있는") if isinstance(agency, dict) else getattr(agency, "tone_and_manner", "전문적이고 신뢰감 있는")
            target   = agency.get("target_audience", "") if isinstance(agency, dict) else getattr(agency, "target_audience", "")

            # agency가 dict인 경우 AgencyProfile로 변환해 voice context 추출
            _ag_obj = agency if not isinstance(agency, dict) else type('_P', (), {
                'brand_voice_dna':     agency.get('brand_voice_dna'),
                'brand_voice_samples': agency.get('brand_voice_samples'),
                'content_pillars':     agency.get('content_pillars', []),
            })()
            _voice_dna, _voice_samples, _content_pillars = _build_voice_context(_ag_obj)

            prompt = _CARD_NEWS_PROMPT.format(
                topic            = topic,
                slide_count      = slide_count,
                last_content     = slide_count - 1,
                language         = body.get("language", "한국어"),
                agency           = f"{ag_name} / {industry}".strip(" /"),
                tone             = tone,
                target           = target,
                content_pillars  = _content_pillars,
                voice_dna        = _voice_dna,
                voice_samples    = _voice_samples,
            )
            raw  = await _llm_generate(prompt, api_keys, tier)
            m    = re_mod.search(r'\{.*\}', raw, re_mod.DOTALL)
            data = jsonlib.loads(m.group()) if m else {}

            slides    = data.get("slides", [])
            hashtags  = data.get("hashtags", [])
            cta_text  = data.get("cta", "")
            hook      = data.get("hook_title", topic)

            result["step_generate"] = {
                "status": "done",
                "hook_title": hook,
                "slides": slides,
                "hashtags": hashtags,
                "cta": cta_text,
                "slide_count": len(slides),
            }
            result["steps_done"].append("generate")
        except Exception as e:
            result["step_generate"] = {"status": "error", "error": str(e)}
            result["steps_failed"].append("generate")
            return result  # STEP 1 실패 시 중단

    # ── STEP 2: 구글시트 저장 ─────────────────────────────────────
    if "sheet" in steps and result["step_generate"] and result["step_generate"].get("status") == "done":
        if not sheet_id or not sa_json:
            result["step_sheet"] = {"status": "skipped", "reason": "spreadsheet_id 또는 service_account_json 없음"}
        else:
            try:
                gen      = result["step_generate"]
                service  = _sheets_service(sa_json)
                _ensure_sheet_header(service, sheet_id)
                saved    = _append_slides_to_sheet(
                    service, sheet_id,
                    gen["slides"], gen["hashtags"], gen["cta"], topic
                )
                result["step_sheet"] = {
                    "status": "done",
                    "saved_rows": saved,
                    "sheet_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}",
                }
                result["steps_done"].append("sheet")
            except Exception as e:
                result["step_sheet"] = {"status": "error", "error": str(e)}
                result["steps_failed"].append("sheet")

    # ── STEP 3: 이미지 렌더링 ─────────────────────────────────────
    if "image" in steps and result["step_generate"] and result["step_generate"].get("status") == "done":
        try:
            gen    = result["step_generate"]
            design = body.get("design", {})
            render_result = await cardnews_render_images({
                "slides":   gen["slides"],
                "hashtags": gen["hashtags"],
                "cta":      gen["cta"],
                "design":   design,
            })
            result["step_image"] = {
                "status": "done",
                "images": render_result["images"],
                "total":  render_result["total"],
                "ratio":  render_result["ratio"],
                "theme":  render_result["theme"],
            }
            result["steps_done"].append("image")

            # 구글시트 이미지 컬럼 업데이트 (시트 저장 완료된 경우 건너뜀 — URL 없이 base64만)
        except Exception as e:
            result["step_image"] = {"status": "error", "error": str(e)}
            result["steps_failed"].append("image")

    return result


@app.post("/sns/generate", response_model=SNSResult)
async def generate_sns(req: SNSRequest):
    """SNS 플랫폼별 전용 콘텐츠 생성 (링크드인/인스타그램/쓰레드)"""
    import re, json as jsonlib

    profile = req.agency_profile or _agency_profile
    keys    = req.api_keys or {}

    voice_dna, voice_samples, content_pillars = _build_voice_context(profile)

    # ── SEO 기획 전략 컨텍스트 빌드 ──────────────────────────────
    seo_parts = []
    if req.keywords:
        seo_parts.append(f"[SEO 핵심 키워드] {', '.join(req.keywords)}")
    if req.search_intent:
        seo_parts.append(f"[검색 의도] {req.search_intent}")
    if req.content_brief:
        seo_parts.append(f"[콘텐츠 방향] {req.content_brief}")
    if req.subtopics:
        seo_parts.append("[핵심 토픽 구조]\n" + "\n".join(f"  • {t}" for t in req.subtopics))
    if req.source_document and req.source_document.strip():
        seo_parts.append(
            "[SEO 리서치 소스 — 아래 내용을 SNS 콘텐츠에 충분히 반영하세요]\n"
            + req.source_document.strip()[:2500]
        )
    seo_strategy = ("\n[SEO전략]\n" + "\n".join(seo_parts) + "\n[/SEO전략]\n") if seo_parts else ""

    prompt = _SNS_PROMPTS[req.platform].format(
        topic            = req.topic,
        summary          = req.seo_summary or req.topic,
        agency           = f"{profile.agency_name} / {profile.industry}",
        target           = profile.target_audience or "기업 의사결정자",
        tone             = profile.tone_and_manner or "전문적이고 신뢰감 있는",
        voice_dna        = voice_dna,
        voice_samples    = voice_samples,
        content_pillars  = content_pillars,
        seo_strategy     = seo_strategy,
    )

    raw = await _llm_generate(prompt, keys)

    # ── LLM 에러 감지 ── {"error": "..."} 형태로 반환되면 즉시 오류 응답
    try:
        _err_check = jsonlib.loads(raw) if raw.strip().startswith('{') else None
        if _err_check and _err_check.get("error"):
            raise HTTPException(status_code=500, detail=_err_check["error"])
    except HTTPException:
        raise
    except Exception:
        pass

    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            d = jsonlib.loads(match.group())
            # error 키가 있으면 LLM 오류 메시지로 처리
            if d.get("error"):
                raise HTTPException(status_code=500, detail=d["error"])
            body = d.get("body", "")
            if not body:
                # body가 비어있으면 raw 전체를 본문으로 사용 (non-JSON 응답 대비)
                body = raw.strip()[:3000]
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
        except HTTPException:
            raise
        except Exception:
            pass

    # JSON 파싱 실패 → raw 텍스트 전체를 본문으로 반환
    body_raw = raw.strip()[:3000]
    if not body_raw:
        raise HTTPException(status_code=500, detail="LLM이 빈 응답을 반환했습니다. API 키 또는 할당량을 확인하세요.")
    return SNSResult(
        topic=req.topic,
        platform=req.platform,
        post=SNSPost(platform=req.platform, body=body_raw, char_count=len(body_raw))
    )


# ── 소스 문서 파이프라인 ────────────────────────────────────────

@app.post("/seo/research")
async def seo_research(req: dict):
    """주제 기반 자료조사 → 소스 문서 초안 생성"""
    topic    = req.get("topic", "").strip()
    keywords = req.get("keywords", [])
    api_keys = req.get("api_keys") or {}
    agency   = req.get("agency_profile") or {}

    if not topic:
        raise HTTPException(status_code=400, detail="topic이 비어있습니다.")

    ag_name  = agency.get("agency_name", "") if isinstance(agency, dict) else getattr(agency, "agency_name", "")
    industry = agency.get("industry", "") if isinstance(agency, dict) else getattr(agency, "industry", "")
    tone     = agency.get("tone_and_manner", "전문적이고 신뢰감 있는") if isinstance(agency, dict) else getattr(agency, "tone_and_manner", "전문적이고 신뢰감 있는")
    target   = agency.get("target_audience", "") if isinstance(agency, dict) else getattr(agency, "target_audience", "")
    kw_str   = ', '.join(keywords) if keywords else topic

    # voice context 추출
    _ag_obj = agency if not isinstance(agency, dict) else type('_P', (), {
        'brand_voice_dna':     agency.get('brand_voice_dna'),
        'brand_voice_samples': agency.get('brand_voice_samples'),
        'content_pillars':     agency.get('content_pillars', []),
    })()
    _voice_dna, _voice_samples, _content_pillars = _build_voice_context(_ag_obj)

    prompt = f"""당신은 콘텐츠 마케팅 전문 리서처입니다.
아래 주제에 대해 블로그·SNS 콘텐츠 제작에 활용할 수 있는 깊이 있는 리서치 문서를 작성하세요.
이 문서는 나중에 블로그(SEO), 링크드인, 인스타그램 등 여러 플랫폼용 콘텐츠로 변환됩니다.

주제: {topic}
핵심 키워드: {kw_str}
에이전시/브랜드: {ag_name} / {industry}
타겟: {target}
톤앤매너: {tone}
콘텐츠 기둥: {_content_pillars}
{_voice_dna}
{_voice_samples}

작성 지침:
- 2,500~3,500자 분량의 심층 리서치 문서 작성
- 구성: 주제 개요 → 핵심 현황·트렌드 → 실제 사례/데이터 → 전문가 인사이트 → 실전 적용 방법 → 결론
- H2(##) 소제목으로 섹션 구분
- 구체적인 수치, 사례, 트렌드 포함
- 한국 시장/독자 맥락에 맞게 작성
- 콘텐츠 제작자가 바로 활용할 수 있도록 사실·인사이트 중심
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요

[소스 문서]"""

    raw, err = await _gemini_text(prompt, api_keys)
    if err:
        raise HTTPException(status_code=500, detail=err)
    return {"source_document": raw.strip()}


@app.post("/seo/add-section")
async def seo_add_section(req: dict):
    """소스 문서에 특정 섹션 추가 — 해당 주제만 조사해서 반환"""
    source_doc    = req.get("source_document", "")
    heading_type  = req.get("heading_type", "H2")  # H1/H2/H3
    section_title = req.get("section_title", "").strip()
    topic         = req.get("topic", "").strip()
    api_keys      = req.get("api_keys") or {}

    if not section_title:
        raise HTTPException(status_code=400, detail="section_title이 비어있습니다.")

    heading_marker = {"H1": "#", "H2": "##", "H3": "###"}.get(heading_type, "##")

    prompt = f"""당신은 콘텐츠 리서처입니다.
기존 소스 문서에 추가할 새 섹션을 작성하세요.

[기존 소스 문서 요약]
주제: {topic}
{source_doc[:800] if source_doc else '(없음)'}

[추가할 섹션]
헤딩: {heading_type} — {section_title}

작성 규칙:
- "{heading_marker} {section_title}" 헤딩으로 시작
- 400~800자 분량의 상세 내용
- 구체적인 사례, 수치, 인사이트 포함
- 기존 문서와 중복되지 않는 새로운 내용
- 섹션 내용만 출력 (헤딩 포함)

[섹션 내용]"""

    raw, err = await _gemini_text(prompt, api_keys)
    if err:
        raise HTTPException(status_code=500, detail=err)
    return {"section_content": f"\n\n{heading_marker} {section_title}\n{raw.strip()}"}


@app.post("/seo/edit-source")
async def seo_edit_source(req: dict):
    """소스 문서 대화형 편집 — 지시에 따라 AI가 수정"""
    source_doc  = req.get("source_document", "").strip()
    instruction = req.get("instruction", "").strip()
    api_keys    = req.get("api_keys") or {}

    if not source_doc:
        raise HTTPException(status_code=400, detail="source_document가 비어있습니다.")
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction이 비어있습니다.")

    prompt = f"""당신은 콘텐츠 편집 전문가입니다.
아래 소스 문서를 지시에 따라 수정·개선하세요.

[소스 문서]
{source_doc}

[수정 지시]
{instruction}

규칙:
- 수정 지시를 정확히 반영
- 문서 전체 구조(H2 섹션)는 유지하면서 내용 개선
- 수정된 전체 소스 문서만 출력 (설명·주석 없이)

[수정된 소스 문서]"""

    raw, err = await _gemini_text(prompt, api_keys)
    if err:
        raise HTTPException(status_code=500, detail=err)
    return {"source_document": raw.strip()}


@app.post("/content/generate-all")
async def generate_all_platforms(req: dict):
    """소스 문서 기반 블로그·링크드인·쓰레드·인스타그램 동시 생성"""
    import asyncio
    source_doc = req.get("source_document", "").strip()
    topic      = req.get("topic", "").strip()
    keywords   = req.get("keywords", [])
    api_keys   = req.get("api_keys") or {}
    agency     = req.get("agency_profile") or {}

    if not source_doc:
        raise HTTPException(status_code=400, detail="source_document가 비어있습니다.")

    ag_name  = agency.get("agency_name", "") if isinstance(agency, dict) else getattr(agency, "agency_name", "")
    industry = agency.get("industry", "") if isinstance(agency, dict) else getattr(agency, "industry", "")
    tone     = agency.get("tone_and_manner", "전문적이고 신뢰감 있는") if isinstance(agency, dict) else getattr(agency, "tone_and_manner", "전문적이고 신뢰감 있는")
    target   = agency.get("target_audience", "기업 의사결정자") if isinstance(agency, dict) else getattr(agency, "target_audience", "기업 의사결정자")
    kw_str   = ', '.join(keywords) if keywords else topic
    ag_str   = f"{ag_name} / {industry}".strip(" /")

    # voice context 추출
    _ag_obj = agency if not isinstance(agency, dict) else type('_P', (), {
        'brand_voice_dna':     agency.get('brand_voice_dna'),
        'brand_voice_samples': agency.get('brand_voice_samples'),
        'content_pillars':     agency.get('content_pillars', []),
    })()
    _voice_dna, _voice_samples, _content_pillars = _build_voice_context(_ag_obj)

    async def gen_blog():
        p = f"""당신은 SEO 블로그 전문 작가입니다.
아래 소스 문서를 바탕으로 SEO 최적화 블로그 글을 작성하세요.
블로그 요약이 아닌, 소스 문서의 모든 정보를 활용해 독자가 충분한 가치를 얻는 완성도 높은 글로 재편성하세요.

[소스 문서]
{source_doc}

주제: {topic}
키워드: {kw_str}
에이전시: {ag_str}
톤앤매너: {tone}
타겟: {target}
콘텐츠 기둥: {_content_pillars}
{_voice_dna}
{_voice_samples}

작성 규칙:
- ## H2 소제목으로 구조화 (3~5개 섹션)
- 키워드를 자연스럽게 배치
- 1,500자 이상
- 마지막 문단에 CTA 포함
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
- 블로그 본문만 출력 (제목 포함, 설명 없이)

[블로그 본문]"""
        raw, _ = await _gemini_text(p, api_keys)
        return raw.strip()

    async def gen_linkedin():
        p = f"""당신은 LinkedIn B2B 콘텐츠 전문가입니다.
아래 소스 문서에서 전문가에게 가장 임팩트 있는 인사이트 1~2개를 선별해 LinkedIn 포스트를 작성하세요.
단순 요약이 아닌, LinkedIn 독자가 저장·공유하고 싶은 전문가 관점 포스트여야 합니다.

[소스 문서]
{source_doc}

주제: {topic}
에이전시: {ag_str}
톤앤매너: {tone}
타겟: {target}
콘텐츠 기둥: {_content_pillars}
{_voice_dna}
{_voice_samples}

작성 규칙:
- 첫 줄: 스크롤을 멈추게 하는 강력한 Hook
- 구조: Hook → 핵심 인사이트 → 데이터/사례 → CTA
- 해시태그 3~5개 마지막에 포함
- 3,000자 이내
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
- LinkedIn 포스트 본문만 출력 (설명 없이)

[LinkedIn 포스트]"""
        raw, _ = await _gemini_text(p, api_keys)
        return raw.strip()

    async def gen_threads():
        p = f"""당신은 Threads SNS 콘텐츠 전문가입니다.
아래 소스 문서에서 가장 충격적이거나 의외인 사실 1개를 선택해 Threads 시리즈 포스트를 작성하세요.

[소스 문서]
{source_doc}

주제: {topic}
에이전시: {ag_str}
톤앤매너: {tone}
타겟: {target}
콘텐츠 기둥: {_content_pillars}
{_voice_dna}
{_voice_samples}

작성 규칙:
- 첫 파트: 호기심을 자극하는 짧은 Hook (100자 이내)
- 이후 파트: 핵심 내용을 짧게 나눠 연결 (각 150자 이내)
- 각 파트는 "---"로 구분
- 마지막 파트: 대화 유도 질문 또는 CTA
- 해시태그 3~5개 마지막에만
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
- Threads 포스트만 출력 (설명 없이)

[Threads 포스트]"""
        raw, _ = await _gemini_text(p, api_keys)
        return raw.strip()

    async def gen_instagram():
        p = f"""당신은 Instagram 콘텐츠 전문가입니다.
아래 소스 문서의 핵심 메시지를 Instagram 캡션으로 압축하세요.
블로그 요약이 아닌, Instagram에서 저장·공유될 감성적인 캡션이어야 합니다.

[소스 문서]
{source_doc}

주제: {topic}
에이전시: {ag_str}
톤앤매너: {tone}
타겟: {target}
콘텐츠 기둥: {_content_pillars}
{_voice_dna}
{_voice_samples}

작성 규칙:
- 첫 줄: 스크롤을 멈추게 하는 감성적 후킹 문장 (이모지 활용)
- 핵심 내용 3~5줄 (이모지 + 짧은 문장)
- 마지막: CTA 문장
- 해시태그 15~20개 (본문과 분리)
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요
- Instagram 캡션만 출력 (설명 없이)

[Instagram 캡션]"""
        raw, _ = await _gemini_text(p, api_keys)
        return raw.strip()

    blog, linkedin, threads, instagram = await asyncio.gather(
        gen_blog(), gen_linkedin(), gen_threads(), gen_instagram()
    )

    return {
        "blog": blog,
        "linkedin": linkedin,
        "threads": threads,
        "instagram": instagram,
    }


@app.post("/content/revise")
async def revise_content(req: dict):
    """콘텐츠 수정 지시 적용 — 블로그/링크드인/쓰레드/인스타그램/페이스북"""
    import json as jsonlib
    content     = req.get("content", "").strip()
    instruction = req.get("instruction", "").strip()
    platform    = req.get("platform", "blog")
    api_keys    = req.get("api_keys") or {}
    agency      = req.get("agency_profile") or {}

    if not content:
        raise HTTPException(status_code=400, detail="content가 비어있습니다.")
    if not instruction:
        raise HTTPException(status_code=400, detail="수정 지시를 입력해주세요.")

    ag_name  = agency.get("agency_name", "") if isinstance(agency, dict) else getattr(agency, "agency_name", "")
    tone     = agency.get("tone_and_manner", "") if isinstance(agency, dict) else getattr(agency, "tone_and_manner", "")
    target   = agency.get("target_audience", "") if isinstance(agency, dict) else getattr(agency, "target_audience", "")

    _ag_obj = agency if not isinstance(agency, dict) else type('_P', (), {
        'brand_voice_dna':     agency.get('brand_voice_dna'),
        'brand_voice_samples': agency.get('brand_voice_samples'),
        'content_pillars':     agency.get('content_pillars', []),
    })()
    _voice_dna, _voice_samples, _content_pillars = _build_voice_context(_ag_obj)

    plat_guide = {
        "blog":      "블로그 (SEO 최적화·마크다운 구조·검색 의도 반영)",
        "linkedin":  "링크드인 (전문적 B2B 인사이트, 3,000자 이내, 해시태그 포함)",
        "threads":   "쓰레드 (500자 이내, 대화체, 시리즈 구조 --- 분절)",
        "instagram": "인스타그램 (감성 캡션, 이모지 적극 사용, 해시태그 최적화)",
        "facebook":  "페이스북 (친근한 톤, 공유 유도, 간결하게)",
    }.get(platform, platform)

    agency_ctx = ""
    if ag_name or tone or target or _voice_dna or _voice_samples:
        agency_ctx = f"""
에이전시: {ag_name}
톤앤매너: {tone}
타겟: {target}
콘텐츠 기둥: {_content_pillars}
{_voice_dna}
{_voice_samples}
"""

    prompt = f"""다음 {plat_guide} 콘텐츠를 수정 지시에 따라 개선하세요.
{agency_ctx}
[원본 콘텐츠]
{content}

[수정 지시]
{instruction}

규칙:
- 수정 지시를 정확히 반영할 것
- 핵심 주제와 메시지는 유지
- 플랫폼 특성({plat_guide})에 맞게 유지
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 유지하세요
- 수정된 콘텐츠만 출력 (설명·주석 없이)

[수정된 콘텐츠]"""

    raw = await _llm_generate(prompt, api_keys)

    # 오류 JSON 감지
    if raw.strip().startswith('{"error"'):
        try:
            d = jsonlib.loads(raw)
            raise HTTPException(status_code=500, detail=d.get("error", "LLM 오류"))
        except HTTPException:
            raise
        except Exception:
            pass

    return {"revised_content": raw.strip()}


@app.post("/blog/generate", response_model=BlogResult)
async def generate_blog(req: BlogRequest):
    """블로그 플랫폼별 최적화 글 생성 (네이버/티스토리/워드프레스)"""
    import asyncio, json, re
    profile = req.agency_profile or _agency_profile
    keys = req.api_keys or {}

    voice_dna, voice_samples, content_pillars = _build_voice_context(profile)

    # ── SEO 기획 전략 컨텍스트 빌드 ──────────────────────────────
    seo_parts = []

    # 1) 핵심 키워드
    if req.keywords:
        seo_parts.append(f"[SEO 핵심 키워드] {', '.join(req.keywords)}")

    # 2) 검색 의도
    if req.search_intent:
        seo_parts.append(f"[검색 의도] {req.search_intent}")

    # 3) 콘텐츠 브리프
    if req.content_brief:
        seo_parts.append(f"[콘텐츠 방향] {req.content_brief}")

    # 4) H2 소주제 구조
    if req.subtopics:
        seo_parts.append("[본문 H2 구조 — 이 순서대로 섹션을 구성하세요]\n" +
                         "\n".join(f"  • {t}" for t in req.subtopics))

    # 5) 소스 문서(섹션별 리서치 내용)
    if req.source_document and req.source_document.strip():
        seo_parts.append(
            "[SEO 리서치 소스 — 아래 내용을 본문에 충분히 반영하세요]\n"
            + req.source_document.strip()[:3000]
        )

    seo_strategy = ("\n[SEO전략]\n" + "\n".join(seo_parts) + "\n[/SEO전략]\n") if seo_parts else ""

    async def gen_one(platform: BlogPlatform) -> BlogPost:
        prompt_tpl = BLOG_PLATFORM_PROMPTS[platform]
        prompt = prompt_tpl.format(
            topic=req.topic,
            agency=f"{profile.agency_name} / {profile.industry}",
            tone=profile.tone_and_manner or "전문적이고 신뢰감 있는",
            target=profile.target_audience or "기업 의사결정자",
            language=req.language,
            voice_dna=voice_dna,
            voice_samples=voice_samples,
            content_pillars=content_pillars,
            seo_strategy=seo_strategy,
        )
        raw = await _llm_generate(prompt, keys)
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                d = json.loads(match.group())
                # 에러 응답 감지
                if "error" in d and not d.get("title") and not d.get("body"):
                    err_msg = d.get("error", "알 수 없는 오류")
                    return BlogPost(platform=platform, title="[생성 오류]", body=f"❌ {err_msg}", word_count=0)
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
콘텐츠 기둥: {content_pillars}
{voice_dna}
{voice_samples}

[슬라이드 구성 규칙]
- 1번 슬라이드: 후킹 커버 — 제목(20자 이내) + 부제(30자 이내), 스크롤을 멈추게 하는 문장
- 2번~{last_content}번 슬라이드: 핵심 내용 — 제목(15자 이내) + 본문(40자 이내)
- {slide_count}번 슬라이드: CTA 마무리 — 저장/팔로우/댓글 유도
- 위 브랜드 보이스 DNA와 샘플 스타일을 반드시 반영하세요

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

    voice_dna, voice_samples, content_pillars = _build_voice_context(profile)

    prompt = _CARD_NEWS_PROMPT.format(
        topic            = req.topic,
        slide_count      = req.slide_count,
        last_content     = req.slide_count - 1,
        language         = req.language,
        agency           = f"{profile.agency_name or '미설정'} / {profile.industry or ''}".strip(" /"),
        target           = profile.target_audience or "일반 비즈니스 독자",
        tone             = profile.tone_and_manner or "전문적이고 신뢰감 있는",
        content_pillars  = content_pillars,
        voice_dna        = voice_dna,
        voice_samples    = voice_samples,
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

    voice_dna, voice_samples, content_pillars = _build_voice_context(profile)

    prompt = VIDEO_PROMPTS[req.video_type].format(
        topic            = req.topic,
        agency           = f"{profile.agency_name} / {profile.industry}",
        target           = profile.target_audience or "기업 의사결정자",
        language         = req.language,
        content_pillars  = content_pillars,
        voice_dna        = voice_dna,
        voice_samples    = voice_samples,
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


# ── 이미지 생성 ──────────────────────────────────────────────────────────────
@app.post("/image/generate")
async def generate_image(body: dict):
    """
    1순위: HuggingFace FLUX.1-schnell (hf_api_token 필요, Inference 권한 필요)
    2순위: Picsum 플레이스홀더 (항상 동작, AI 생성 아님)
    """
    import httpx, base64, random

    prompt   = body.get("prompt", "")
    width    = body.get("width", 1024)
    height   = body.get("height", 768)
    hf_token = (body.get("api_keys") or {}).get("hf_api_token", "")

    if not prompt:
        raise HTTPException(status_code=400, detail="prompt가 비어있습니다.")

    # ── 1순위: HuggingFace FLUX.1-schnell ─────────────────────
    if hf_token:
        hf_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    hf_url,
                    headers={"Authorization": f"Bearer {hf_token}"},
                    json={"inputs": prompt, "parameters": {"width": width, "height": height}}
                )
                if r.status_code == 200:
                    img_b64 = base64.b64encode(r.content).decode()
                    return {"image_b64": img_b64, "mime": "image/jpeg", "source": "hf"}
                # 403/401 → 권한 부족 안내 후 폴백
                if r.status_code in (401, 403):
                    hf_error = r.text[:200]
                    # 폴백으로 진행 (에러 raise 안 함)
        except Exception:
            pass  # 네트워크 오류 → 폴백

    # ── 2순위: Picsum 플레이스홀더 (항상 동작) ────────────────
    seed = random.randint(1, 999)
    picsum_url = f"https://picsum.photos/seed/{seed}/{width}/{height}"
    msg = "" if hf_token else "HF 토큰을 등록하면 AI 이미지 생성이 활성화됩니다"
    return {"image_url": picsum_url, "mime": "image/jpeg", "source": "picsum", "info": msg}


# ── 샘플링: URL 크롤링 → 글쓰기 스타일 추출 ────────────────────────────────

def _detect_platform_from_url(url: str) -> str:
    """URL 패턴으로 플랫폼 자동 감지"""
    u = url.lower()
    if "tistory.com"  in u: return "티스토리"
    if "blog.naver.com" in u: return "네이버 블로그"
    if "brunch.co.kr"  in u: return "브런치"
    if "linkedin.com"  in u: return "링크드인"
    if "threads.net"   in u: return "쓰레드"
    if "instagram.com" in u: return "인스타그램"
    if "facebook.com"  in u: return "페이스북"
    if "youtube.com" in u or "youtu.be" in u: return "유튜브"
    if "tiktok.com"    in u: return "틱톡"
    if "wordpress.com" in u or "wp-content" in u: return "워드프레스"
    return "블로그"


def _extract_author_url(url: str, soup) -> str | None:
    """크롤링된 페이지에서 작성자 채널/프로필 URL 추정"""
    from urllib.parse import urlparse, urljoin
    p = urlparse(url)

    # 티스토리: 포스트 URL → 블로그 루트
    if "tistory.com" in p.netloc:
        return f"{p.scheme}://{p.netloc}"

    # 네이버 블로그: /username/postId → /username
    if "blog.naver.com" in p.netloc:
        parts = p.path.strip("/").split("/")
        if len(parts) >= 1:
            return f"https://blog.naver.com/{parts[0]}"

    # 브런치: /@author/post → /@author
    if "brunch.co.kr" in p.netloc:
        parts = p.path.strip("/").split("/")
        for part in parts:
            if part.startswith("@"):
                return f"https://brunch.co.kr/{part}"

    # 링크드인: /posts/xxx → /in/username
    if "linkedin.com" in p.netloc:
        parts = p.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "in":
            return f"https://www.linkedin.com/in/{parts[1]}/recent-activity/all/"

    # 쓰레드: /@user/post/id → /@user
    if "threads.net" in p.netloc:
        parts = p.path.strip("/").split("/")
        for part in parts:
            if part.startswith("@"):
                return f"https://www.threads.net/{part}"

    # 인스타그램: /p/postid/ → 메타 태그에서 작성자 찾기
    if "instagram.com" in p.netloc:
        author_meta = soup.find("meta", property="og:url")
        if author_meta:
            return None  # 인스타는 로그인 필요, 원본 URL만 사용
        return None

    # 유튜브: /watch?v=xxx → /channel 또는 /@username
    if "youtube.com" in p.netloc:
        canonical = soup.find("link", rel="canonical")
        channel_link = soup.find("span", itemprop="author") or \
                       soup.find("link", itemprop="url")
        if channel_link and channel_link.get("href"):
            return urljoin("https://www.youtube.com", channel_link["href"])
        return None

    # 일반 블로그: 루트 도메인
    return f"{p.scheme}://{p.netloc}"


@app.post("/agency/sampling/analyze")
async def agency_sampling_analyze(body: dict):
    """
    샘플링: URL 목록 크롤링 → 작성자 페이지 크롤링 → 글쓰기 스타일 샘플 추출
    body: { urls: [str], member_id: str, api_keys: dict, agency_profile: dict }
    """
    import asyncio, json as jsonlib
    urls         = body.get("urls", [])
    member_id    = body.get("member_id", "팀원")
    api_keys     = body.get("api_keys", {})
    agency       = body.get("agency_profile", {})

    if not urls:
        raise HTTPException(status_code=400, detail="URL을 1개 이상 입력하세요.")

    url_results: list[dict] = []

    async def analyze_one(url: str) -> dict:
        result = {"url": url, "platform": _detect_platform_from_url(url),
                  "status": "error", "title": "", "author_url": None,
                  "body_preview": "", "author_body": ""}
        try:
            crawled = await _crawl_url(url)
            result["title"]        = crawled.get("title", "")
            result["body_preview"] = crawled.get("body_text", "")[:3000]
            result["status"]       = "crawled"

            # BeautifulSoup 재크롤로 작성자 URL 추정
            import httpx
            from bs4 import BeautifulSoup
            headers = {"User-Agent": "Mozilla/5.0 Chrome/120"}
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get(url, headers=headers)
            soup = BeautifulSoup(r.text, "lxml")
            author_url = _extract_author_url(url, soup)
            result["author_url"] = author_url

            # 작성자 채널 크롤링
            if author_url and author_url != url:
                try:
                    author_crawled      = await _crawl_url(author_url)
                    result["author_body"] = author_crawled.get("body_text", "")[:2000]
                    result["status"] = "author_crawled"
                except Exception:
                    pass  # 작성자 페이지 실패해도 원본은 유지

        except Exception as e:
            result["error"] = str(e)
        return result

    # URL들 병렬 크롤링 (최대 5개)
    tasks = [analyze_one(u) for u in urls[:5] if u.strip()]
    url_results = await asyncio.gather(*tasks)

    # 성공한 URL들의 텍스트만 모아 AI로 글쓰기 스타일 추출
    combined_texts = []
    for r in url_results:
        if r["status"] in ("crawled", "author_crawled") and r.get("body_preview"):
            combined_texts.append(
                f"[{r['platform']}] {r['title']}\n{r['body_preview']}"
            )
        if r.get("author_body"):
            combined_texts.append(
                f"[{r['platform']} 채널 전체] {r['author_body']}"
            )

    voice_samples: list[dict] = []
    llm_error: str | None = None

    if combined_texts:
        # Gemini 키 사전 확인
        gemini_key = api_keys.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")
        if not gemini_key:
            llm_error = "Gemini API 키가 없습니다. API 설정 → API Keys 탭에서 입력해주세요."
        else:
            ag_name  = agency.get("agency_name", "")
            ag_tone  = agency.get("tone_and_manner", "")
            full_text = "\n\n---\n\n".join(combined_texts)[:8000]

            prompt = f"""당신은 콘텐츠 분석 전문가입니다. 아래 콘텐츠들을 분석하여 글쓰기 스타일 샘플 3~5개를 추출하세요.

에이전시: {ag_name}
팀원: {member_id}
톤앤매너: {ag_tone}

[분석할 콘텐츠]
{full_text}

규칙:
- 각 샘플은 해당 플랫폼에서 가장 핵심적인 글쓰기 패턴을 보여주는 문단/섹션이어야 합니다
- 각 샘플은 150~400자 내외로 원문을 그대로 발췌
- 반드시 아래 JSON 형식으로만 응답 (설명 없이)

{{"samples": [
  {{"platform": "플랫폼명", "excerpt": "발췌한 텍스트", "pattern_note": "이 글의 특징 한줄 요약"}},
  ...
]}}"""

            raw = await _llm_generate(prompt, api_keys)

            # _llm_generate가 오류를 {"error": "..."} 형태로 반환하는 경우 처리
            if raw.startswith('{"error"'):
                try:
                    err_obj = jsonlib.loads(raw)
                    llm_error = err_obj.get("error", "AI 호출 실패")
                except Exception:
                    llm_error = "AI 호출 실패 (응답 파싱 오류)"
            else:
                try:
                    import re as re_mod
                    m = re_mod.search(r'\{.*\}', raw, re_mod.DOTALL)
                    if m:
                        parsed = jsonlib.loads(m.group())
                        for s in parsed.get("samples", []):
                            note = s.get("pattern_note", "")
                            text = s.get("excerpt", "").strip()
                            plat = s.get("platform", "공통")
                            if text:
                                full = f"{text}\n\n💡 스타일 메모: {note}" if note else text
                                voice_samples.append({"channel": plat, "text": full})
                    else:
                        llm_error = "AI 응답에서 JSON을 찾을 수 없습니다."
                except Exception as parse_err:
                    llm_error = f"AI 응답 파싱 실패: {str(parse_err)[:120]}"
    elif not url_results or all(r["status"] == "error" for r in url_results):
        llm_error = "크롤링된 본문이 없어 스타일 추출을 건너뜁니다."

    return {
        "member_id":     member_id,
        "url_results":   url_results,
        "voice_samples": voice_samples,
        "total_crawled": sum(1 for r in url_results if r["status"] != "error"),
        "total_urls":    len(url_results),
        "llm_error":     llm_error,
    }


# ── 소셜 직접 배포 ────────────────────────────────────────────────

import base64 as _b64lib

class _PublishLinkedInReq(BaseModel):
    access_token: str
    content: str
    title: str = ""

class _PublishFacebookReq(BaseModel):
    page_access_token: str
    page_id: str
    content: str
    title: str = ""
    link: str = ""

class _PublishThreadsReq(BaseModel):
    access_token: str
    user_id: str
    content: str

class _PublishInstagramReq(BaseModel):
    access_token: str
    ig_account_id: str
    caption: str
    image_urls: list[str] = []
    image_b64_list: list[str] = []
    imgbb_api_key: str = ""

class _PublishWordPressReq(BaseModel):
    site_url: str
    username: str
    app_password: str
    title: str
    content: str
    status: str = "publish"


async def _imgbb_upload(b64: str, api_key: str) -> str:
    import httpx as _hx
    async with _hx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.imgbb.com/1/upload",
                         data={"key": api_key, "image": b64})
        if r.status_code != 200:
            raise ValueError(f"imgbb 업로드 실패: {r.text[:200]}")
        return r.json()["data"]["url"]


@app.post("/publish/linkedin")
async def publish_linkedin(body: _PublishLinkedInReq):
    import httpx as _hx
    token = body.access_token
    async with _hx.AsyncClient(timeout=15) as c:
        ru = await c.get("https://api.linkedin.com/v2/userinfo",
                         headers={"Authorization": f"Bearer {token}"})
        if ru.status_code != 200:
            raise HTTPException(400, f"LinkedIn 토큰 오류: {ru.text[:200]}")
        author_id = ru.json().get("sub", "")
        if not author_id:
            raise HTTPException(400, "LinkedIn 사용자 ID 조회 실패")
        author_urn = f"urn:li:person:{author_id}"

        text = f"{body.title}\n\n{body.content}".strip() if body.title else body.content
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        rp = await c.post("https://api.linkedin.com/v2/ugcPosts",
                          json=payload,
                          headers={
                              "Authorization": f"Bearer {token}",
                              "Content-Type": "application/json",
                              "X-Restli-Protocol-Version": "2.0.0"
                          })
        if rp.status_code not in (200, 201):
            raise HTTPException(rp.status_code, f"LinkedIn 포스팅 실패: {rp.text[:300]}")
        post_id = rp.headers.get("x-restli-id") or rp.json().get("id", "")
        return {"status": "done", "post_id": post_id, "platform": "linkedin"}


@app.post("/publish/facebook")
async def publish_facebook(body: _PublishFacebookReq):
    import httpx as _hx
    text = f"{body.title}\n\n{body.content}".strip() if body.title else body.content
    payload: dict = {"message": text, "access_token": body.page_access_token}
    if body.link:
        payload["link"] = body.link
    async with _hx.AsyncClient(timeout=15) as c:
        r = await c.post(f"https://graph.facebook.com/v19.0/{body.page_id}/feed",
                         data=payload)
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"Facebook 포스팅 실패: {r.text[:300]}")
        return {"status": "done", "post_id": r.json().get("id", ""), "platform": "facebook"}


@app.post("/publish/threads")
async def publish_threads(body: _PublishThreadsReq):
    import httpx as _hx
    token, uid = body.access_token, body.user_id
    async with _hx.AsyncClient(timeout=15) as c:
        r1 = await c.post(f"https://graph.threads.net/v1.0/{uid}/threads",
                          data={"media_type": "TEXT", "text": body.content, "access_token": token})
        if r1.status_code != 200:
            raise HTTPException(r1.status_code, f"Threads 미디어 생성 실패: {r1.text[:300]}")
        creation_id = r1.json().get("id")
        r2 = await c.post(f"https://graph.threads.net/v1.0/{uid}/threads_publish",
                          data={"creation_id": creation_id, "access_token": token})
        if r2.status_code != 200:
            raise HTTPException(r2.status_code, f"Threads 발행 실패: {r2.text[:300]}")
        return {"status": "done", "post_id": r2.json().get("id", ""), "platform": "threads"}


@app.post("/publish/instagram")
async def publish_instagram(body: _PublishInstagramReq):
    import httpx as _hx
    token, ig_id = body.access_token, body.ig_account_id
    image_urls = list(body.image_urls)
    if body.image_b64_list and body.imgbb_api_key:
        for b64 in body.image_b64_list:
            url = await _imgbb_upload(b64, body.imgbb_api_key)
            image_urls.append(url)
    if not image_urls:
        raise HTTPException(400, "Instagram 포스팅에는 이미지가 필요합니다")

    async with _hx.AsyncClient(timeout=60) as c:
        if len(image_urls) == 1:
            r = await c.post(f"https://graph.facebook.com/v19.0/{ig_id}/media",
                             data={"image_url": image_urls[0], "caption": body.caption,
                                   "access_token": token})
            if r.status_code != 200:
                raise HTTPException(r.status_code, f"Instagram 미디어 생성 실패: {r.text[:300]}")
            creation_id = r.json().get("id")
        else:
            item_ids = []
            for url in image_urls[:10]:
                ri = await c.post(f"https://graph.facebook.com/v19.0/{ig_id}/media",
                                  data={"image_url": url, "is_carousel_item": "true",
                                        "access_token": token})
                if ri.status_code == 200:
                    item_ids.append(ri.json().get("id"))
            if not item_ids:
                raise HTTPException(500, "carousel 아이템 생성 실패")
            rc = await c.post(f"https://graph.facebook.com/v19.0/{ig_id}/media",
                              data={"media_type": "CAROUSEL", "caption": body.caption,
                                    "children": ",".join(item_ids), "access_token": token})
            if rc.status_code != 200:
                raise HTTPException(rc.status_code, f"Carousel 컨테이너 생성 실패: {rc.text[:300]}")
            creation_id = rc.json().get("id")

        rp = await c.post(f"https://graph.facebook.com/v19.0/{ig_id}/media_publish",
                          data={"creation_id": creation_id, "access_token": token})
        if rp.status_code != 200:
            raise HTTPException(rp.status_code, f"Instagram 발행 실패: {rp.text[:300]}")
        return {"status": "done", "post_id": rp.json().get("id", ""), "platform": "instagram"}


@app.post("/publish/wordpress")
async def publish_wordpress(body: _PublishWordPressReq):
    import httpx as _hx
    site = body.site_url.rstrip("/")
    creds = _b64lib.b64encode(f"{body.username}:{body.app_password}".encode()).decode()
    async with _hx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{site}/wp-json/wp/v2/posts",
                         json={"title": body.title, "content": body.content, "status": body.status},
                         headers={"Authorization": f"Basic {creds}",
                                  "Content-Type": "application/json"})
        if r.status_code not in (200, 201):
            raise HTTPException(r.status_code, f"WordPress 포스팅 실패: {r.text[:300]}")
        d = r.json()
        return {"status": "done", "post_id": str(d.get("id", "")),
                "post_url": d.get("link", ""), "platform": "wordpress"}
