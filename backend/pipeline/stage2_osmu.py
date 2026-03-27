"""
Stage 2: OSMU 텍스트 가공

Tier 1 (완전 무료): Gemini 2.5 Flash (글) + Groq Llama3 (대본)
Tier 2 (무료 충분): 동일
Tier 3 (유료 포함): Gemini 2.5 Flash (동일, Pro 업그레이드 옵션)
"""

import os
import asyncio
from backend.models.schemas import (
    Stage1Output, Stage2Output, OSMUContent, ContentRequest,
    Platform, ContentFormat, ApiTier
)

try:
    from google import genai as _genai_check
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


_ENV_GEMINI = os.getenv("GEMINI_API_KEY", "")
_ENV_GROQ   = os.getenv("GROQ_API_KEY", "")

# Tier별 Gemini 모델 선택
GEMINI_MODEL = {
    ApiTier.TIER_1: "gemini-2.5-flash",
    ApiTier.TIER_2: "gemini-2.5-flash",
    ApiTier.TIER_3: "gemini-2.5-flash",   # Tier3에서 최신 모델
}

GROQ_MODEL = "llama-3.1-8b-instant"


# ── 플랫폼별 프롬프트 ──────────────────────────────────────────

BLOG_PROMPT = """
당신은 B2B 마케팅 전문 콘텐츠 라이터입니다.
아래 주제와 트렌드 패턴을 기반으로 정보성 롱폼 블로그 글을 작성하세요.

주제: {topic}
트렌드 패턴: {patterns}
타겟: 기업 의사결정자 (CEO, CMO, 팀장급)
언어: {language}

요구사항:
- 제목: CTR 극대화 후킹 제목 (숫자/질문/결과형 중 택1)
- 구성: 도입(공감/문제제기) → 본문(데이터 근거 3가지) → 결론(CTA)
- 분량: 800~1200자
- 해시태그 5개

JSON 형식으로만 반환 (다른 텍스트 없이):
{{"hook_title": "...", "body": "...", "hashtags": ["#...", ...], "cta": "..."}}
"""

LINKEDIN_PROMPT = """
당신은 링크드인 B2B 마케팅 전문가입니다.
아래 주제로 C-Level이 즐겨 공유하는 링크드인 인사이트 포스트를 작성하세요.

주제: {topic}
트렌드: {patterns}
언어: {language}

요구사항:
- 첫 2줄: 스크롤을 멈추는 후킹 문장
- 핵심 인사이트 3줄 → 실전 팁 → 댓글 유도 질문
- 300자 이내, 이모지 활용
- 해시태그 3개

JSON 형식으로만 반환:
{{"hook_title": "...", "body": "...", "hashtags": ["#...", ...], "cta": "..."}}
"""

CARD_NEWS_PROMPT = """
카드뉴스용 슬라이드 텍스트를 작성하세요.

주제: {topic}
언어: {language}

슬라이드 5장 구성:
- 각 슬라이드: 제목(15자 이내) | 내용(30자 이내)
- 마지막 슬라이드: CTA

JSON 형식으로만 반환:
{{"hook_title": "...", "body": "슬라이드1제목|내용||슬라이드2제목|내용||...", "hashtags": [], "cta": "..."}}
"""

SCRIPT_PROMPT = """
아래 주제로 30~60초 숏폼 영상 대본을 작성하세요.

주제: {topic}
참고 패턴: {patterns}
언어: {language}

구성:
- [훅] 첫 3초 충격 문장
- [본론] 핵심 메시지 3가지 (각 10초 분량)
- [클로징] 구독/좋아요/링크 CTA

자막용으로 문장마다 줄바꿈. 마크다운 없이 plain text로.
"""


# ── LLM 호출 ──────────────────────────────────────────────────

async def _call_gemini(prompt: str, tier: ApiTier, api_key: str = "") -> str:
    key = api_key or _ENV_GEMINI
    if not key:
        return '{"hook_title": "[Gemini API 키 필요]", "body": "Tier 설정에서 GEMINI_API_KEY를 입력하세요.", "hashtags": [], "cta": ""}'
    try:
        from google import genai as _genai
        client = _genai.Client(api_key=key)
        model_name = GEMINI_MODEL.get(tier, "gemini-2.0-flash")
        response = client.models.generate_content(model=model_name, contents=prompt)
        return response.text or ""
    except Exception as e:
        return f'{{"error": "{str(e)[:100]}"}}'


async def _call_groq(prompt: str, api_key: str = "") -> str:
    key = api_key or _ENV_GROQ
    if not GROQ_AVAILABLE or not key:
        return "[Groq API 키 필요]\nTier 설정에서 GROQ_API_KEY를 입력하세요.\n대본이 여기에 생성됩니다."

    client = Groq(api_key=key)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1024,
    )
    return completion.choices[0].message.content


def _parse_osmu(text: str, platform: Platform, fmt: ContentFormat) -> OSMUContent:
    import json, re
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return OSMUContent(
                platform=platform, format=fmt,
                hook_title=data.get("hook_title", ""),
                body=data.get("body", ""),
                hashtags=data.get("hashtags", []),
                cta=data.get("cta"),
            )
        except json.JSONDecodeError:
            pass
    return OSMUContent(platform=platform, format=fmt, hook_title="[파싱 실패]", body=text)


# ── Stage 2 실행 ───────────────────────────────────────────────

async def run(request: ContentRequest, stage1: Stage1Output) -> Stage2Output:
    """
    Tier별 LLM 라우팅:
    - Tier 1/2: Gemini 2.0 Flash (무료) + Groq Llama3
    - Tier 3:   Gemini 2.5 Flash (최신) + Groq Llama3
    """
    topic = stage1.original_topic
    patterns = stage1.trend_analysis
    lang = request.language
    tier = request.tier
    gemini_key = request.api_keys.resolve("gemini_api_key")
    groq_key   = request.api_keys.resolve("groq_api_key")

    task_map: dict[str, asyncio.Task] = {}

    if Platform.BLOG in request.target_platforms:
        task_map["blog"] = asyncio.create_task(
            _call_gemini(BLOG_PROMPT.format(topic=topic, patterns=patterns, language=lang), tier, gemini_key)
        )
    if Platform.LINKEDIN in request.target_platforms:
        task_map["linkedin"] = asyncio.create_task(
            _call_gemini(LINKEDIN_PROMPT.format(topic=topic, patterns=patterns, language=lang), tier, gemini_key)
        )
    if Platform.INSTAGRAM in request.target_platforms:
        task_map["card"] = asyncio.create_task(
            _call_gemini(CARD_NEWS_PROMPT.format(topic=topic, language=lang), tier, gemini_key)
        )

    # 대본은 모든 tier에서 Groq (속도 우선)
    task_map["script"] = asyncio.create_task(
        _call_groq(SCRIPT_PROMPT.format(topic=topic, patterns=patterns, language=lang), groq_key)
    )

    results = await asyncio.gather(*task_map.values(), return_exceptions=True)
    result_map = dict(zip(task_map.keys(), results))

    blog = None
    if "blog" in result_map and not isinstance(result_map["blog"], Exception):
        blog = _parse_osmu(result_map["blog"], Platform.BLOG, ContentFormat.LONGFORM)

    linkedin = None
    if "linkedin" in result_map and not isinstance(result_map["linkedin"], Exception):
        linkedin = _parse_osmu(result_map["linkedin"], Platform.LINKEDIN, ContentFormat.LONGFORM)

    card = None
    if "card" in result_map and not isinstance(result_map["card"], Exception):
        card = _parse_osmu(result_map["card"], Platform.INSTAGRAM, ContentFormat.CARD_NEWS)

    script_raw = ""
    if "script" in result_map and not isinstance(result_map["script"], Exception):
        script_raw = result_map["script"]

    script_clean = script_raw.replace("**", "").replace("##", "").replace("#", "").strip()

    return Stage2Output(
        topic=topic,
        blog_post=blog,
        linkedin_post=linkedin,
        card_news=card,
        video_script=script_raw,
        script_txt=script_clean,
    )
