"""
Stage 4: 최종 검수 및 바이럴 링크 연동 (The Click Trigger)
- 블로그 하단 SNS 채널 링크 자동 삽입
- 링크드인 댓글용 UTM 트래킹 링크 생성
"""

import re
from urllib.parse import urlencode
from backend.models.schemas import (
    Stage2Output, Stage3Output, Stage4Output,
    LinkChainConfig, ApprovalStatus
)


def build_utm_url(base_url: str, config: LinkChainConfig, content: str = "") -> str:
    """UTM 파라미터 포함 추적 URL 생성"""
    params = {
        "utm_source": config.utm_source,
        "utm_medium": config.utm_medium,
        "utm_campaign": config.utm_campaign or "osmu_auto",
        "utm_content": content,
    }
    # 빈 값 제거
    params = {k: v for k, v in params.items() if v}
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


def insert_sns_links_in_blog(blog_body: str, config: LinkChainConfig, sns_links: dict) -> str:
    """
    블로그 본문 하단에 SNS 채널 링크 삽입.
    sns_links 예시: {"linkedin": "https://...", "instagram": "https://..."}
    """
    if not config.insert_sns_links_in_blog:
        return blog_body

    link_section = "\n\n---\n\n📣 **더 많은 인사이트를 원하신다면?**\n"
    if "linkedin" in sns_links:
        link_section += f"- 🔗 LinkedIn: {sns_links['linkedin']}\n"
    if "instagram" in sns_links:
        link_section += f"- 📸 Instagram: {sns_links['instagram']}\n"
    if "youtube" in sns_links:
        link_section += f"- 🎬 YouTube: {sns_links['youtube']}\n"

    return blog_body + link_section


def build_linkedin_comment(blog_url: str, config: LinkChainConfig) -> str:
    """링크드인 댓글에 삽입할 블로그 원문 UTM 링크 텍스트 생성"""
    if not config.insert_blog_link_in_linkedin_comment or not blog_url:
        return ""

    tracked_url = build_utm_url(blog_url, config, content="linkedin_comment")
    return (
        f"📖 전체 아티클 원문은 아래 링크에서 확인하세요!\n"
        f"👉 {tracked_url}\n\n"
        f"#B2B마케팅 #콘텐츠마케팅 #OSMU"
    )


async def run(
    stage2: Stage2Output,
    stage3: Stage3Output,
    link_config: LinkChainConfig,
    blog_url: str = "",
    sns_links: dict | None = None,
) -> Stage4Output:
    """Stage 4 실행: 링크 체인 삽입 → 검수 대기 상태로 반환"""

    if sns_links is None:
        sns_links = {}

    # 블로그 최종본: SNS 링크 삽입
    blog_final = ""
    if stage2.blog_post:
        blog_final = insert_sns_links_in_blog(
            stage2.blog_post.body,
            link_config,
            sns_links
        )
        # 제목도 포함
        blog_final = f"# {stage2.blog_post.hook_title}\n\n{blog_final}"
        if stage2.blog_post.cta:
            blog_final += f"\n\n> {stage2.blog_post.cta}"

    # 링크드인 최종본: UTM 댓글 추가
    linkedin_final = ""
    if stage2.linkedin_post:
        linkedin_final = f"{stage2.linkedin_post.hook_title}\n\n{stage2.linkedin_post.body}"
        if stage2.linkedin_post.cta:
            linkedin_final += f"\n\n{stage2.linkedin_post.cta}"
        comment = build_linkedin_comment(blog_url, link_config)
        if comment:
            linkedin_final += f"\n\n[댓글 자동 삽입 예정]\n{comment}"

    return Stage4Output(
        status=ApprovalStatus.PENDING,
        blog_final=blog_final,
        linkedin_final=linkedin_final,
        link_chain=link_config,
        review_notes="자동 생성 완료 - 마케터 검수 후 승인 버튼을 눌러주세요.",
    )
