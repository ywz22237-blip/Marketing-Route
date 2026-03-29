from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class ApiTier(str, Enum):
    """
    API 사용 등급 선택
    - TIER_1: 완전 무료   (Gemini Flash + Groq + Pollinations + data.go.kr)
    - TIER_2: 무료 충분   (+ Google TTS + HuggingFace + Make.com Free)
    - TIER_3: 유료 포함   (+ SerpAPI + Make.com Core 이상)
    """
    TIER_1 = "tier1"   # 완전 무료
    TIER_2 = "tier2"   # 무료 한도 활용
    TIER_3 = "tier3"   # 유료 API 포함


TIER_LABELS = {
    ApiTier.TIER_1: "완전 무료 (Gemini Flash + Groq + Pollinations + data.go.kr)",
    ApiTier.TIER_2: "무료 충분 (+ Google TTS + HuggingFace + Make.com Free)",
    ApiTier.TIER_3: "유료 포함 (+ SerpAPI 실시간 트렌드 + Make.com Core)",
}

TIER_FEATURES = {
    ApiTier.TIER_1: {
        "llm":        "gemini-2.5-flash",
        "script_llm": "groq-llama3",
        "image":      "pollinations",
        "tts":        False,
        "stt":        False,
        "trend":      "data_go_kr",
        "publish":    False,
        "monthly_cost": "$0",
    },
    ApiTier.TIER_2: {
        "llm":        "gemini-2.5-flash",
        "script_llm": "groq-llama3",
        "image":      "huggingface",
        "tts":        True,   # Google Cloud TTS
        "stt":        True,   # Groq Whisper
        "trend":      "data_go_kr",
        "publish":    "make_free",
        "monthly_cost": "$0 (결제수단 등록 필요)",
    },
    ApiTier.TIER_3: {
        "llm":        "gemini-2.5-flash",
        "script_llm": "groq-llama3",
        "image":      "huggingface",
        "tts":        True,
        "stt":        True,
        "trend":      "serpapi",  # 실시간 구글 트렌드
        "publish":    "make_core",
        "monthly_cost": "~$60/월 (SerpAPI $50 + Make.com $10.59)",
    },
}


class Platform(str, Enum):
    BLOG = "blog"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    THREADS = "threads"


class ContentFormat(str, Enum):
    LONGFORM = "longform"       # 블로그 롱폼
    SHORTFORM = "shortform"     # 숏폼 대본
    CARD_NEWS = "card_news"     # 카드뉴스 3줄
    SCRIPT = "script"           # 영상 대본


# ── 에이전시 프로필 (학습 데이터) ─────────────────────────────
class AgencyProfile(BaseModel):
    """에이전시/고객사 정보 — 모든 콘텐츠 생성의 베이스 컨텍스트"""
    agency_name: str = Field(default="", description="에이전시/브랜드 이름")
    persona_type: str = Field(default="", description="사용 모드 (startup/sidehustle/local)")
    industry: str = Field(default="", description="업종 (예: B2B SaaS, 제조, 금융 등)")
    services: str = Field(default="", description="주요 서비스/제품 설명")
    target_audience: str = Field(default="", description="타겟 고객 (예: 중소기업 CEO, 마케터 등)")
    tone_and_manner: str = Field(default="", description="톤앤매너 (예: 전문적/친근한/권위있는)")
    main_keywords: List[str] = Field(default=[], description="핵심 SEO 키워드 목록")
    competitors: str = Field(default="", description="주요 경쟁사 (참고용)")
    usp: str = Field(default="", description="차별화 포인트 (USP)")
    # 배포 채널 설정
    blog_platforms: List[str] = Field(default=[], description="블로그 플랫폼 (naver/tistory/wordpress)")
    sns_platforms: List[str] = Field(default=[], description="SNS 플랫폼 (linkedin/instagram/threads)")
    video_platforms: List[str] = Field(default=[], description="영상 플랫폼 (youtube)")
    # 콘텐츠 전략
    content_pillars: List[str] = Field(default=[], description="콘텐츠 기둥 주제 (예: 업계트렌드, 사용법, 사례)")
    posting_frequency: str = Field(default="주 3회", description="발행 주기")
    brand_voice_samples: List[str] = Field(default=[], description="기존 대표 글/카피 샘플 (3~5개)")
    brand_voice_dna: dict = Field(default={}, description="AI 분석 보이스 DNA (sentence_style, title_pattern, tone_keywords, avoid, summary)")


# ── SEO 기획 ──────────────────────────────────────────────────
class ContentBrief(BaseModel):
    """플랫폼별 콘텐츠 브리프 — SEO 기획 결과물"""
    platform: str
    topic: str = ""
    summary: str = ""
    key_points: List[str] = []
    angle: str = ""
    recommended_format: str = ""
    recommended_slide_count: Optional[int] = None  # 카드뉴스용


class SEOPlanRequest(BaseModel):
    keyword: str
    agency_profile: Optional[AgencyProfile] = None
    tier: str = "tier1"
    api_keys: Optional[dict] = None


class SEOPlanResult(BaseModel):
    keyword: str
    search_intent: str
    recommended_topics: List[str] = []
    hook_angles: List[str] = []
    competitor_patterns: List[str] = []
    content_calendar: List[dict] = []
    content_briefs: dict = {}  # platform -> ContentBrief dict


# ── 카드뉴스 기획 ──────────────────────────────────────────────
class SlideOutline(BaseModel):
    index: int
    title: str
    type: str = "content"  # cover / content / cta


class CardNewsPlanRequest(BaseModel):
    topic: str
    agency_profile: Optional[AgencyProfile] = None
    api_keys: Optional[dict] = None
    tier: str = "tier1"


class CardNewsPlanResult(BaseModel):
    topic: str
    recommended_count: int
    reasoning: str
    slide_outline: List[SlideOutline] = []


# ── SNS 플랫폼별 생성 ─────────────────────────────────────────
class SNSPlatform(str, Enum):
    LINKEDIN  = "linkedin"
    INSTAGRAM = "instagram"
    THREADS   = "threads"


class SNSRequest(BaseModel):
    topic: str
    platform: SNSPlatform
    seo_summary: str = ""        # SEO 기획 브리프 내용 (옵션)
    agency_profile: Optional[AgencyProfile] = None
    api_keys: Optional[dict] = None
    tier: str = "tier1"
    language: str = "ko"


class SNSPost(BaseModel):
    platform: SNSPlatform
    title: str = ""
    body: str
    hashtags: List[str] = []
    cta: str = ""
    char_count: int = 0


class SNSResult(BaseModel):
    topic: str
    platform: SNSPlatform
    post: SNSPost


# ── 블로그 플랫폼별 생성 ───────────────────────────────────────
class BlogPlatform(str, Enum):
    NAVER    = "naver"
    TISTORY  = "tistory"
    WORDPRESS = "wordpress"

class BlogRequest(BaseModel):
    topic: str
    platforms: List[BlogPlatform] = [BlogPlatform.NAVER]
    agency_profile: Optional[AgencyProfile] = None
    api_keys: Optional[dict] = None
    tier: str = "tier1"
    language: str = "ko"
    source_document: Optional[str] = None  # SEO기획 소스 문서 (있으면 품질 대폭 향상)
    keywords: List[str] = []              # SEO 핵심 키워드 목록
    search_intent: Optional[str] = None  # 검색 의도 (정보성/거래성/탐색성 등)
    subtopics: List[str] = []            # H2 소주제 목록 (본문 구조)
    content_brief: Optional[str] = None  # 콘텐츠 브리프 요약

class BlogPost(BaseModel):
    platform: BlogPlatform
    title: str
    body: str
    meta_description: str = ""
    hashtags: List[str] = []
    cta: str = ""
    word_count: int = 0

class BlogResult(BaseModel):
    topic: str
    posts: List[BlogPost] = []


# ── 영상 콘텐츠 ───────────────────────────────────────────────
class VideoType(str, Enum):
    LONGFORM  = "longform"   # 유튜브 5~15분
    SHORTFORM = "shortform"  # 숏폼 30~60초

class VideoRequest(BaseModel):
    topic: str
    video_type: VideoType = VideoType.SHORTFORM
    agency_profile: Optional[AgencyProfile] = None
    api_keys: Optional[dict] = None
    tier: str = "tier1"
    language: str = "ko"
    generate_tts: bool = False
    generate_thumbnails: bool = True

class VideoSection(BaseModel):
    label: str        # 예: [훅], [본론1], [클로징]
    text: str
    duration_sec: int = 0

class VideoResult(BaseModel):
    topic: str
    video_type: VideoType
    title: str
    sections: List[VideoSection] = []
    full_script: str = ""
    script_plain: str = ""    # TTS용 마크다운 제거본
    srt_content: str = ""
    capcut_json: Optional[dict] = None
    audio_path: Optional[str] = None
    thumbnails: List[dict] = []


# ── API 키 모델 ────────────────────────────────────────────────
class ApiKeys(BaseModel):
    """UI에서 입력된 API 키 (env var 우선순위보다 높음)"""
    # Tier 1 (공통 필수)
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    # Tier 2 추가
    google_tts_api_key: Optional[str] = None
    hf_api_token: Optional[str] = None
    data_go_kr_key: Optional[str] = None
    make_webhook_linkedin: Optional[str] = None
    make_webhook_instagram: Optional[str] = None
    make_webhook_youtube: Optional[str] = None
    make_webhook_blog: Optional[str] = None
    # Tier 3 추가
    serp_api_key: Optional[str] = None

    def resolve(self, key: str) -> str:
        """UI 입력값 → 없으면 환경변수 순으로 반환"""
        import os
        ui_val = getattr(self, key.lower(), None)
        if ui_val:
            return ui_val
        return os.getenv(key.upper(), "")


# ── Stage 1: 입력 ──────────────────────────────────────────────
class ContentRequest(BaseModel):
    topic: str = Field(..., description="핵심 주제 또는 원천 소스 텍스트")
    target_platforms: List[Platform] = Field(
        default=[Platform.BLOG, Platform.LINKEDIN],
        description="생성할 플랫폼 목록"
    )
    tier: ApiTier = Field(
        default=ApiTier.TIER_1,
        description="API 사용 등급 (tier1=완전무료 / tier2=무료충분 / tier3=유료포함)"
    )
    api_keys: ApiKeys = Field(
        default_factory=ApiKeys,
        description="UI에서 입력한 API 키 (없으면 .env 값 사용)"
    )
    collect_trends: bool = Field(default=True, description="트렌드 수집 여부")
    language: str = Field(default="ko", description="출력 언어 (ko/en)")


class TrendData(BaseModel):
    keyword: str
    search_volume: Optional[int] = None
    related_queries: List[str] = []
    viral_patterns: List[str] = []
    source: str = "serpapi"


class Stage1Output(BaseModel):
    original_topic: str
    verified_data: str          # verified-data.md 내용
    trend_analysis: str         # patterns.md 내용
    trend_keywords: List[TrendData] = []


# ── Stage 2: OSMU 텍스트 가공 ──────────────────────────────────
class OSMUContent(BaseModel):
    platform: Platform
    format: ContentFormat
    hook_title: str             # 낚시성 후킹 제목
    body: str                   # 본문
    hashtags: List[str] = []
    cta: Optional[str] = None   # Call-to-Action 문구


class Stage2Output(BaseModel):
    topic: str
    blog_post: Optional[OSMUContent] = None
    linkedin_post: Optional[OSMUContent] = None
    card_news: Optional[OSMUContent] = None
    video_script: Optional[str] = None     # draft.md
    script_txt: Optional[str] = None       # script.txt (TTS용 정제)


# ── Stage 3: 시각화 / TTS ──────────────────────────────────────
class ThumbnailResult(BaseModel):
    index: int
    url: str
    prompt_used: str


class Stage3Output(BaseModel):
    audio_path: Optional[str] = None        # audio.mp3
    subtitle_path: Optional[str] = None     # subtitle.srt
    thumbnails: List[ThumbnailResult] = []
    capcut_json_path: Optional[str] = None  # draft_content.json


# ── Stage 4: 검수 / 링크 체인 ─────────────────────────────────
class LinkChainConfig(BaseModel):
    insert_sns_links_in_blog: bool = True       # 블로그 하단 SNS 링크 삽입
    insert_blog_link_in_linkedin_comment: bool = True   # 링크드인 댓글에 블로그 링크
    utm_source: str = "linkedin"
    utm_medium: str = "social"
    utm_campaign: str = ""

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Stage4Output(BaseModel):
    status: ApprovalStatus = ApprovalStatus.PENDING
    blog_final: Optional[str] = None        # 링크 삽입된 최종 블로그
    linkedin_final: Optional[str] = None    # UTM 포함된 최종 링크드인 글
    link_chain: LinkChainConfig = LinkChainConfig()
    review_notes: Optional[str] = None


# ── Stage 5: 배포 ─────────────────────────────────────────────
class PublishRequest(BaseModel):
    job_id: str
    platforms: List[Platform]
    schedule_at: Optional[str] = None   # ISO 8601 (없으면 즉시 발송)

class PublishResult(BaseModel):
    platform: Platform
    success: bool
    webhook_response: Optional[str] = None
    error: Optional[str] = None


# ── 카드뉴스 ───────────────────────────────────────────────────
class CardNewsSlide(BaseModel):
    index: int
    title: str
    body: str
    is_cta: bool = False

class CardNewsRequest(BaseModel):
    topic: str
    slide_count: int = Field(default=5, ge=3, le=10, description="슬라이드 수 (3~10장)")
    agency_profile: Optional[AgencyProfile] = None
    api_keys: Optional[dict] = None
    tier: str = "tier1"
    language: str = "ko"

class CardNewsResult(BaseModel):
    topic: str
    slide_count: int
    hook_title: str = ""
    slides: List[CardNewsSlide] = []
    hashtags: List[str] = []
    cta: str = ""


# ── 롱폼 → 숏폼 변환 ──────────────────────────────────────────
class ConvertRequest(BaseModel):
    source_text: str = Field(..., description="원본 롱폼 콘텐츠 (블로그 글 또는 영상 대본)")
    platform: str = Field(default="youtube_shorts", description="youtube_shorts / instagram_reels / tiktok")
    duration_sec: int = Field(default=30, description="목표 길이 (15 / 30 / 60초)")
    strategy: str = Field(default="hook_first", description="hook_first / key_point / story / list")
    caption_style: str = Field(default="bold_highlight", description="bold_highlight / sentence / word")
    agency_profile: Optional[AgencyProfile] = None
    api_keys: Optional[dict] = None
    tier: str = "tier1"
    language: str = "ko"


class ConvertResult(BaseModel):
    platform: str
    duration_sec: int
    strategy: str
    title: str = ""
    sections: List[VideoSection] = []
    full_script: str = ""
    script_plain: str = ""
    caption_lines: List[str] = []
    srt_content: str = ""


# ── SEO 키워드 도구 ───────────────────────────────────────────

class SEOKeywordItem(BaseModel):
    keyword: str
    intent: str = ""
    competition: str = "medium"   # low / medium / high
    monthly_search: str = ""
    recommended: bool = False
    notes: str = ""

class SEOQuickRequest(BaseModel):
    keywords: List[str]           # 최대 20개
    tier: str = "tier1"
    api_keys: Optional[dict] = None

class SEOQuickResult(BaseModel):
    items: List[SEOKeywordItem] = []

class SEOTrendPoint(BaseModel):
    period: str                   # "YYYY-MM"
    value: int = 0                # 상대값 0~100

class SEOAnalyzeRequest(BaseModel):
    keyword: str
    context: str = ""             # 추가 맥락 (아이디어 설명)
    related_count: int = 10       # 10/50/100/200
    cluster_count: int = 10       # 3/10/30/100
    trend_period: int = 1         # 1/3/4/5 (년)
    compare_keywords: List[str] = []   # 최대 5개
    gender_filter: str = "all"
    age_filter: str = "all"
    agency_profile: Optional[AgencyProfile] = None
    tier: str = "tier1"
    api_keys: Optional[dict] = None

class SEOAnalyzeResult(BaseModel):
    keyword: str
    search_intent: str = ""
    related_keywords: List[dict] = []   # [{keyword, relevance, monthly_est, competition}]
    clusters: List[dict] = []           # [{name, keywords:[]}]
    trend_data: List[SEOTrendPoint] = []
    smart_block: List[dict] = []        # [{rank, title, type, engagement}]
    content_briefs: dict = {}
    recommended_topics: List[str] = []
    hook_angles: List[str] = []

class SEOSuggestRequest(BaseModel):
    base_keyword: str
    industry: str = ""
    suggest_count: int = 10       # 10/15/20
    content_type: str = "blog"    # blog/marketing/sns/youtube
    filters: dict = {}
    agency_profile: Optional[AgencyProfile] = None
    tier: str = "tier1"
    api_keys: Optional[dict] = None

class SEOSuggestResult(BaseModel):
    base_keyword: str
    keywords: List[dict] = []     # [{keyword, score, reason, monthly_est, competition, content_fit}]

class SEOExpandRequest(BaseModel):
    seed_keyword: str
    strategy: str = "broad"       # broad/question/modifier/lsi/longtail
    tier: str = "tier1"
    api_keys: Optional[dict] = None

class SEOExpandResult(BaseModel):
    seed_keyword: str
    strategy: str = ""
    expanded: List[dict] = []     # [{keyword, type, relevance, monthly_est}]

class SEOBulkRequest(BaseModel):
    keywords: List[str]
    tier: str = "tier1"
    api_keys: Optional[dict] = None
    agency_profile: Optional[AgencyProfile] = None

class SEOBulkResult(BaseModel):
    items: List[SEOKeywordItem] = []
    total: int = 0


# ── SEO Phase1 — 크롤링 기반 분석 ─────────────────────────────

class SEOCrawlRequest(BaseModel):
    url: str
    target_keyword: str = ""
    api_keys: Optional[dict] = None

class SEOTechCheck(BaseModel):
    item: str
    status: str          # "ok" | "warn" | "error"
    value: str = ""
    advice: str = ""

class SEOCrawlResult(BaseModel):
    url: str
    title: str = ""
    meta_description: str = ""
    h1: List[str] = []
    h2: List[str] = []
    h3: List[str] = []
    images_total: int = 0
    images_no_alt: int = 0
    word_count: int = 0
    keyword_density: float = 0.0
    tech_checks: List[SEOTechCheck] = []
    content_summary: str = ""
    top_keywords: List[str] = []

class SEOGapRequest(BaseModel):
    my_keyword: str
    my_idea: str = ""
    competitor_urls: List[str]      # 최대 3개
    api_keys: Optional[dict] = None

class SEOGapResult(BaseModel):
    my_keyword: str
    competitors_analyzed: int = 0
    missing_keywords: List[str] = []
    missing_sections: List[str] = []
    my_advantages: List[str] = []
    recommended_additions: List[dict] = []  # [{section, reason, priority}]
    overall_score: int = 0          # 내 콘텐츠 경쟁력 0~100

class SEOMetaRequest(BaseModel):
    target_keyword: str
    content_summary: str = ""
    url: str = ""
    brand_name: str = ""
    api_keys: Optional[dict] = None

class SEOMetaResult(BaseModel):
    target_keyword: str
    title_candidates: List[dict] = []       # [{title, length, score, reason}]
    description_candidates: List[dict] = [] # [{description, length, score, reason}]
    og_title: str = ""
    og_description: str = ""

# ── SEO Phase2 — Google Search Console ────────────────────────

class GSCConnectRequest(BaseModel):
    service_account_json: str = ""   # JSON 키 문자열
    site_url: str = ""               # https://yourdomain.com/
    api_keys: Optional[dict] = None

class GSCRow(BaseModel):
    query: str
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0

class GSCReport(BaseModel):
    site_url: str
    date_range: str = ""
    total_clicks: int = 0
    total_impressions: int = 0
    avg_ctr: float = 0.0
    avg_position: float = 0.0
    top_queries: List[GSCRow] = []
    low_ctr_pages: List[dict] = []   # CTR 낮은 페이지 → Meta 재생성 후보
    opportunities: List[dict] = []   # [{query, impressions, position, advice}]


# ── 전체 파이프라인 Job ────────────────────────────────────────
class PipelineJob(BaseModel):
    job_id: str
    request: ContentRequest
    stage1: Optional[Stage1Output] = None
    stage2: Optional[Stage2Output] = None
    stage3: Optional[Stage3Output] = None
    stage4: Optional[Stage4Output] = None
    publish_results: List[PublishResult] = []
    current_stage: int = 0
    error: Optional[str] = None
