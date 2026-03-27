"""
Stage 5: 배포 트리거 (Make.com 웹훅)
- 승인된 콘텐츠를 Make.com 시나리오로 전송
- Make.com이 실제 LinkedIn / Instagram / YouTube 업로드를 처리
"""

import os
import httpx
from backend.models.schemas import (
    Stage2Output, Stage4Output, Platform,
    PublishRequest, PublishResult
)


WEBHOOKS = {
    Platform.LINKEDIN:  os.getenv("MAKE_WEBHOOK_LINKEDIN", ""),
    Platform.INSTAGRAM: os.getenv("MAKE_WEBHOOK_INSTAGRAM", ""),
    Platform.YOUTUBE:   os.getenv("MAKE_WEBHOOK_YOUTUBE", ""),
    Platform.BLOG:      os.getenv("MAKE_WEBHOOK_BLOG", ""),
}


async def _trigger_webhook(platform: Platform, payload: dict) -> PublishResult:
    url = WEBHOOKS.get(platform, "")
    if not url:
        return PublishResult(
            platform=platform,
            success=False,
            error=f"MAKE_WEBHOOK_{platform.value.upper()} 환경변수 미설정"
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return PublishResult(
                platform=platform,
                success=True,
                webhook_response=resp.text[:200]
            )
    except Exception as e:
        return PublishResult(platform=platform, success=False, error=str(e))


async def run(
    request: PublishRequest,
    stage2: Stage2Output,
    stage4: Stage4Output,
) -> list[PublishResult]:
    """Stage 5 실행: 플랫폼별 Make.com 웹훅 병렬 트리거"""
    import asyncio

    tasks = []
    for platform in request.platforms:
        payload = _build_payload(platform, stage2, stage4, request.job_id)
        tasks.append(_trigger_webhook(platform, payload))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    final: list[PublishResult] = []
    for r in results:
        if isinstance(r, Exception):
            final.append(PublishResult(platform=Platform.BLOG, success=False, error=str(r)))
        else:
            final.append(r)

    return final


def _build_payload(
    platform: Platform,
    stage2: Stage2Output,
    stage4: Stage4Output,
    job_id: str
) -> dict:
    """플랫폼별 Make.com 웹훅 페이로드 구성"""
    base = {"job_id": job_id, "platform": platform.value, "topic": stage2.topic}

    if platform == Platform.BLOG:
        base["content"] = stage4.blog_final or ""
        base["title"] = stage2.blog_post.hook_title if stage2.blog_post else ""

    elif platform == Platform.LINKEDIN:
        base["content"] = stage4.linkedin_final or ""
        base["hashtags"] = stage2.linkedin_post.hashtags if stage2.linkedin_post else []

    elif platform == Platform.INSTAGRAM:
        base["caption"] = stage2.card_news.body if stage2.card_news else ""
        base["hashtags"] = stage2.card_news.hashtags if stage2.card_news else []

    elif platform == Platform.YOUTUBE:
        base["script"] = stage2.video_script or ""
        base["title"] = stage2.blog_post.hook_title if stage2.blog_post else stage2.topic

    return base
