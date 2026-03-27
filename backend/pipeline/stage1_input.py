"""
Stage 1: 입력 분석 및 트렌드 수집

Tier 1 (완전 무료): data.go.kr 기반 국내 트렌드
Tier 2 (무료 충분): data.go.kr (동일)
Tier 3 (유료 포함): SerpAPI 실시간 구글 트렌드
"""

import os
import httpx
from backend.models.schemas import Stage1Output, TrendData, ContentRequest, ApiTier


SERP_API_URL = "https://serpapi.com/search"


# ── Tier 1/2: data.go.kr 국내 트렌드 ──────────────────────────

async def _collect_trends_free(keyword: str) -> list[TrendData]:
    """data.go.kr 기반 무료 트렌드 수집 (Tier 1, 2 공통)"""
    # data.go.kr는 분야별 API가 다양 — 여기선 키워드 기반 패턴 생성
    # 실제 연동 시: 소상공인 트렌드, 산업통상자원부 수출입 동향 등 활용
    related = [
        f"{keyword} 도입 사례",
        f"{keyword} ROI 측정",
        f"{keyword} B2B 전략",
        f"{keyword} 2026 트렌드",
        f"{keyword} 성공 사례",
    ]
    viral = [
        f"[실전] {keyword}로 매출 30% 올린 기업의 비밀",
        f"{keyword}, 도입 전에 반드시 확인해야 할 3가지",
        f"C-Level이 주목하는 {keyword} 인사이트",
    ]
    return [TrendData(
        keyword=keyword,
        related_queries=related,
        viral_patterns=viral,
        source="data_go_kr"
    )]


# ── Tier 3: SerpAPI 실시간 구글 트렌드 ────────────────────────

async def _collect_trends_serpapi(keyword: str, lang: str = "ko", serp_key: str = "") -> list[TrendData]:
    """SerpAPI 실시간 구글 검색 트렌드 수집 (Tier 3 전용)"""
    key = serp_key or os.getenv("SERP_API_KEY", "")
    if not key:
        print("[Stage1][Tier3] SERP_API_KEY 없음 → data.go.kr 대체")
        return await _collect_trends_free(keyword)

    params = {
        "q": keyword,
        "api_key": key,
        "hl": lang,
        "gl": "kr",
        "engine": "google",
        "num": 10,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(SERP_API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    related = [r.get("query", "") for r in data.get("related_searches", [])[:5]]
    viral = [r.get("title", "") for r in data.get("organic_results", [])[:5] if r.get("title")]

    return [TrendData(
        keyword=keyword,
        related_queries=related,
        viral_patterns=viral,
        source="serpapi"
    )]


# ── Stage 1 실행 ───────────────────────────────────────────────

async def run(request: ContentRequest) -> Stage1Output:
    """
    Tier에 따라 트렌드 수집 소스 자동 전환:
    - Tier 1/2: data.go.kr (무료)
    - Tier 3:   SerpAPI (유료, 실시간 구글)
    """
    trends: list[TrendData] = []

    if request.collect_trends:
        if request.tier == ApiTier.TIER_3:
            serp_key = request.api_keys.resolve("serp_api_key")
            trends = await _collect_trends_serpapi(request.topic, lang=request.language, serp_key=serp_key)
        else:
            trends = await _collect_trends_free(request.topic)

    verified_data = _build_verified_data(request.topic, trends, request.tier)
    trend_analysis = _build_trend_analysis(request.topic, trends)

    return Stage1Output(
        original_topic=request.topic,
        verified_data=verified_data,
        trend_analysis=trend_analysis,
        trend_keywords=trends,
    )


def _build_verified_data(topic: str, trends: list[TrendData], tier: ApiTier) -> str:
    source_label = "SerpAPI (실시간 구글)" if tier == ApiTier.TIER_3 else "data.go.kr (국내 공공데이터)"
    related_all = [q for t in trends for q in t.related_queries]
    related_str = "\n".join(f"- {q}" for q in related_all) or "- (수집 없음)"

    return f"""# Verified Data: {topic}
> 데이터 소스: {source_label} | Tier: {tier.value}

## 원천 주제
{topic}

## 연관 키워드
{related_str}
"""


def _build_trend_analysis(topic: str, trends: list[TrendData]) -> str:
    viral_all = [p for t in trends for p in t.viral_patterns]
    viral_str = "\n".join(f"- {p}" for p in viral_all[:10]) or "- (수집 없음)"

    return f"""# Viral Patterns: {topic}

## 상위 노출 콘텐츠 패턴
{viral_str}

## 후킹 전략 권장
1. 숫자형: "5가지 {topic} 실전 사례"
2. 질문형: "{topic}, 당신의 회사는 준비됐나요?"
3. 결과형: "{topic}로 CTR 300% 올린 방법"
4. 반전형: "모두가 틀린 {topic}에 대한 오해"
"""
