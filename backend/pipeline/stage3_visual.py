"""
Stage 3: 시각화 및 영상 데이터 생성

Tier 1 (완전 무료):
  - 이미지: Pollinations.ai (URL 기반, 무료 무제한)
  - TTS: 미사용 (스크립트 텍스트만 제공)
  - STT: 미사용

Tier 2 (무료 충분):
  - 이미지: HuggingFace Inference API (무료 크레딧)
  - TTS: Google Cloud TTS (100만 자/월 무료)
  - STT: Groq Whisper (무료 한도)

Tier 3 (유료 포함):
  - Tier 2와 동일 (이미지/TTS/STT)
"""

import os
import json
import base64
import urllib.parse
import httpx
from pathlib import Path
from backend.models.schemas import Stage2Output, Stage3Output, ThumbnailResult, ApiTier


OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")

GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
HF_SD_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"


# ── 이미지: Pollinations.ai (Tier 1 — 완전 무료) ───────────────

async def _thumbnails_pollinations(topic: str, job_id: str, count: int = 5) -> list[ThumbnailResult]:
    thumb_dir = Path(OUTPUT_DIR) / job_id / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    prompts = [
        f"professional B2B marketing thumbnail, {topic}, modern minimalist design, bold typography",
        f"viral social media thumbnail, {topic}, eye-catching colors, business professional",
        f"LinkedIn article thumbnail, {topic}, corporate style, data visualization",
        f"YouTube thumbnail, {topic}, high contrast, dramatic lighting",
        f"Instagram card news, {topic}, clean infographic style",
    ]

    results: list[ThumbnailResult] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, prompt in enumerate(prompts[:count]):
            url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}&width=1280&height=720&nologo=true"
            try:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 200:
                    img_path = thumb_dir / f"thumbnail_0{i+1}.png"
                    img_path.write_bytes(resp.content)
                    results.append(ThumbnailResult(index=i+1, url=str(img_path), prompt_used=prompt))
                else:
                    results.append(ThumbnailResult(index=i+1, url="", prompt_used=prompt))
            except Exception as e:
                print(f"[Stage3][Pollinations] 썸네일 {i+1} 실패: {e}")
                results.append(ThumbnailResult(index=i+1, url="", prompt_used=prompt))
    return results


# ── 이미지: HuggingFace Inference API (Tier 2/3) ──────────────

async def _thumbnails_huggingface(topic: str, job_id: str, count: int = 5, hf_token: str = "") -> list[ThumbnailResult]:
    token = hf_token or os.getenv("HF_API_TOKEN", "")
    if not token:
        print("[Stage3][HuggingFace] HF_API_TOKEN 없음 → Pollinations 대체")
        return await _thumbnails_pollinations(topic, job_id, count)

    thumb_dir = Path(OUTPUT_DIR) / job_id / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    prompts = [
        f"B2B marketing thumbnail, {topic}, minimalist design",
        f"social media thumbnail, {topic}, vibrant colors",
        f"LinkedIn post image, {topic}, corporate professional",
        f"YouTube thumbnail, {topic}, dramatic lighting",
        f"Instagram card news, {topic}, infographic",
    ]

    headers = {"Authorization": f"Bearer {token}"}
    results: list[ThumbnailResult] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, prompt in enumerate(prompts[:count]):
            try:
                resp = await client.post(
                    HF_SD_URL,
                    headers=headers,
                    json={"inputs": prompt},
                )
                if resp.status_code == 200:
                    img_path = thumb_dir / f"thumbnail_0{i+1}.png"
                    img_path.write_bytes(resp.content)
                    results.append(ThumbnailResult(index=i+1, url=str(img_path), prompt_used=prompt))
                elif resp.status_code == 503:
                    # 모델 로딩 중 (콜드스타트) → Pollinations 폴백
                    print(f"[Stage3][HuggingFace] 모델 로딩 중, Pollinations 대체")
                    fallback = await _thumbnails_pollinations(topic, job_id, count)
                    return fallback
                else:
                    results.append(ThumbnailResult(index=i+1, url="", prompt_used=prompt))
            except Exception as e:
                print(f"[Stage3][HuggingFace] 썸네일 {i+1} 실패: {e}")
                results.append(ThumbnailResult(index=i+1, url="", prompt_used=prompt))
    return results


# ── TTS: Google Cloud (Tier 2/3 전용) ─────────────────────────

async def _generate_audio(script: str, job_id: str, lang: str = "ko", tts_key: str = "") -> str | None:
    key = tts_key or os.getenv("GOOGLE_TTS_API_KEY", "")
    if not key:
        print("[Stage3][TTS] GOOGLE_TTS_API_KEY 없음 — Tier2/3에서 활성화")
        return None

    voice_name = "ko-KR-Neural2-C" if lang == "ko" else "en-US-Neural2-J"
    language_code = "ko-KR" if lang == "ko" else "en-US"

    payload = {
        "input": {"text": script[:4500]},
        "voice": {"languageCode": language_code, "name": voice_name},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.1},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{GOOGLE_TTS_URL}?key={key}",
            json=payload
        )
        resp.raise_for_status()
        audio_b64 = resp.json().get("audioContent", "")

    if not audio_b64:
        return None

    out_path = Path(OUTPUT_DIR) / job_id / "audio.mp3"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(audio_b64))
    return str(out_path)


# ── 자막 SRT 생성 (모든 Tier 공통) ────────────────────────────

def _generate_srt(script: str, job_id: str) -> str:
    lines = [l.strip() for l in script.split("\n") if l.strip()]
    srt_blocks = []
    for i, line in enumerate(lines):
        s, e = i * 3, i * 3 + 3
        srt_blocks.append(f"{i+1}\n{_fmt_srt(s)} --> {_fmt_srt(e)}\n{line}\n")

    out_path = Path(OUTPUT_DIR) / job_id / "subtitle.srt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(srt_blocks), encoding="utf-8")
    return str(out_path)


def _fmt_srt(sec: int) -> str:
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d},000"


# ── CapCut JSON (모든 Tier 공통) ──────────────────────────────

def _generate_capcut_json(stage2: Stage2Output, job_id: str, audio_path: str | None, subtitle_path: str | None) -> str:
    lines = [l.strip() for l in (stage2.script_txt or "").split("\n") if l.strip()]
    data = {
        "version": "1.0",
        "project_name": f"OSMU_{job_id}",
        "topic": stage2.topic,
        "tracks": [
            {"type": "text", "segments": [
                {"index": i, "text": l, "start_ms": i*3000, "end_ms": (i+1)*3000}
                for i, l in enumerate(lines)
            ]},
            {"type": "audio", "source": audio_path or ""},
            {"type": "subtitle", "source": subtitle_path or ""},
        ],
        "metadata": {
            "platform_targets": ["youtube_shorts", "instagram_reels", "tiktok"],
            "resolution": "1080x1920", "fps": 30,
        }
    }
    out_path = Path(OUTPUT_DIR) / job_id / "draft_content.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


# ── Stage 3 실행 ───────────────────────────────────────────────

async def run(stage2: Stage2Output, job_id: str, lang: str = "ko", tier: ApiTier = ApiTier.TIER_1,
              hf_token: str = "", tts_key: str = "") -> Stage3Output:
    """
    Tier별 시각화 분기:
    - Tier 1: Pollinations 썸네일, TTS/STT 없음
    - Tier 2: HuggingFace 썸네일 + Google TTS + Groq Whisper
    - Tier 3: Tier 2 동일
    """
    import asyncio
    script = stage2.script_txt or stage2.video_script or ""

    # 이미지 생성
    if tier == ApiTier.TIER_1:
        thumb_task = asyncio.create_task(_thumbnails_pollinations(stage2.topic, job_id))
        audio_task = None
    else:
        thumb_task = asyncio.create_task(_thumbnails_huggingface(stage2.topic, job_id, hf_token=hf_token))
        audio_task = asyncio.create_task(_generate_audio(script, job_id, lang, tts_key=tts_key)) if script else None

    thumbnails = await thumb_task
    audio_path = await audio_task if audio_task else None

    subtitle_path = _generate_srt(script, job_id) if script else None
    capcut_path = _generate_capcut_json(stage2, job_id, audio_path, subtitle_path)

    return Stage3Output(
        audio_path=audio_path,
        subtitle_path=subtitle_path,
        thumbnails=thumbnails,
        capcut_json_path=capcut_path,
    )
