"""Phase 4.3 vision spike — Sonnet 4.6 vision via anthropic SDK 단일 호출 검증.

plan §14.4 (f505208 갱신): vision input path = anthropic SDK 별 path
  사유: claude-agent-sdk 0.1.77 ContentBlock(types.py:992-999) ImageBlock 정의 부재.
  vision은 plan §12 SDK 통일 결정과 직교 — anthropic.Anthropic().messages.create()
  multimodal content (image base64) 표준 path.

plan §14.6 4.3 진입 prerequisite — 1페이지 spike → cost / accuracy / latency 실측.

흐름:
  1. .env 로드 → ANTHROPIC_API_KEY 확인 (fail-fast)
  2. 노션 log DB query (NOTION_DB_LOG) — 타입="ai_visual" AND 셀프 리뷰=true 최근 1건
     → 관련 페이지 mention page_id 추출
  3. 콘텐츠 페이지 blocks.children.list (pagination) → image block 마지막 1건
     → image.file.url (Notion-hosted expire URL) 또는 external.url
  4. httpx.get(url).content → bytes → base64 + media_type 추정
  5. anthropic.messages.create() multimodal — Sonnet 4.6 vision
     system: text_rule=zero 검출 OCR JSON 스키마
  6. resp.usage → cost_usd (Sonnet 4.6 rate $3/M in, $15/M out, $3.75 cache_w, $0.30 cache_r)
  7. 콘솔 보고 — source / OCR result / 메트릭 (사용자 ground truth 대조 단계)

Production 0 touch. tools.notion / tools.llm._common 은 read-only import.

CLI:
  uv run python scripts/_spike_vision_review.py
    → 자동 sourcing (노션 log DB 최근 ai_visual 1건)
  uv run python scripts/_spike_vision_review.py --image-path <local.png>
    → 로컬 파일 강제 (노션 query skip — 디버그용)
  uv run python scripts/_spike_vision_review.py --page-id <uuid>
    → 노션 query skip, 콘텐츠 페이지 직접 image block fetch
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv  # noqa: PLC0415
    load_dotenv(dotenv_path=ROOT / ".env")
except ImportError:
    pass

import httpx  # noqa: E402
from anthropic import Anthropic  # noqa: E402

from tools.llm._common import _extract_json  # noqa: E402
from tools.notion import get_client, norm_uuid, resolve_data_source_id  # noqa: E402
from tools.notion._retry import notion_call  # noqa: E402


# Sonnet 4.6 vision pricing (anthropic 공식 docs, 2026-05-18 기준).
SONNET_46_RATE = {
    "input": 3.0,
    "output": 15.0,
    "cache_creation": 3.75,
    "cache_read": 0.30,
}


VISION_SYSTEM_PROMPT = """\
이 이미지를 OCR 하여 JSON 한 객체로만 반환하라. 설명/주석 X.

스키마:
{
  "text_detected": <bool>,
  "text_pixels_pct": <float, 0-100, 이미지 전체 대비 텍스트 영역 비율 추정>,
  "ocr_tokens": <int, 감지된 토큰(단어) 개수>,
  "korean_text": <str, 감지된 한글 원문 그대로. 없으면 빈 문자열>,
  "english_text": <str, 감지된 영문 원문 그대로. 없으면 빈 문자열>
}

text_detected = true 조건: 어떤 텍스트라도 감지됨 (간판, 자막, 워터마크, 캡션 포함).
text_detected = false 조건: 시각적 형태만 있고 글자 형태가 전혀 없음.
"""


def cost_from_usage(usage: Any) -> float:
    """anthropic.Usage → cost_usd 환산 (Sonnet 4.6 rate)."""
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    cache_w = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_r = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (
        inp * SONNET_46_RATE["input"]
        + out * SONNET_46_RATE["output"]
        + cache_w * SONNET_46_RATE["cache_creation"]
        + cache_r * SONNET_46_RATE["cache_read"]
    ) / 1_000_000


async def query_log_db_recent_ai_visual() -> dict[str, Any] | None:
    """노션 log DB 에서 타입=ai_visual AND 셀프 리뷰=true 최근 1건 page_id 반환.

    반환: {"log_row_id": str, "page_id": str, "slot_type": str} | None
    """
    log_db_id = os.environ["NOTION_DB_LOG"].strip()
    client = get_client()
    ds_id = resolve_data_source_id(log_db_id)

    notion_filter = {
        "and": [
            {"property": "타입", "select": {"equals": "ai_visual"}},
            {"property": "셀프 리뷰", "checkbox": {"equals": True}},
        ]
    }
    sorts = [{"timestamp": "created_time", "direction": "descending"}]

    if ds_id != log_db_id:
        resp = await notion_call(
            client.data_sources.query,
            data_source_id=ds_id, filter=notion_filter, sorts=sorts, page_size=1,
        )
    else:
        resp = await notion_call(
            client.databases.query,
            database_id=log_db_id, filter=notion_filter, sorts=sorts, page_size=1,
        )

    rows = resp.get("results") or []
    if not rows:
        return None
    row = rows[0]
    props = row.get("properties") or {}

    related = (props.get("관련 페이지") or {}).get("rich_text") or []
    page_id = None
    for item in related:
        if item.get("type") != "mention":
            continue
        page_id = ((item.get("mention") or {}).get("page") or {}).get("id")
        if page_id:
            break
    if not page_id:
        return None

    slot_type_val = ((props.get("타입") or {}).get("select") or {}).get("name") or "ai_visual"
    return {
        "log_row_id": row.get("id"),
        "page_id": norm_uuid(page_id),
        "slot_type": slot_type_val,
    }


async def fetch_image_url_from_page(page_id: str) -> str | None:
    """page_id 콘텐츠 페이지의 마지막 image block file URL 추출.

    pagination 처리. image block 의 file/external/file_upload 분기 모두 cover.
    """
    client = get_client()
    image_blocks: list[dict[str, Any]] = []

    cursor: str | None = None
    while True:
        kwargs: dict[str, Any] = {"block_id": page_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = await notion_call(client.blocks.children.list, **kwargs)
        for b in resp.get("results", []):
            if b.get("type") == "image":
                image_blocks.append(b)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")

    if not image_blocks:
        return None

    # 마지막 image block (최근 추가 우선).
    img = image_blocks[-1].get("image") or {}
    typ = img.get("type")
    if typ == "file":
        return (img.get("file") or {}).get("url")
    if typ == "external":
        return (img.get("external") or {}).get("url")
    if typ == "file_upload":
        return (img.get("file_upload") or {}).get("url")
    return None


def media_type_from_url_or_bytes(url: str | None, data: bytes) -> str:
    """media_type 추정. URL extension 우선, fallback magic bytes."""
    if url:
        low = url.lower().split("?")[0]
        if low.endswith(".png"):
            return "image/png"
        if low.endswith(".jpg") or low.endswith(".jpeg"):
            return "image/jpeg"
        if low.endswith(".webp"):
            return "image/webp"
        if low.endswith(".gif"):
            return "image/gif"
    # magic bytes
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    return "image/png"  # fallback


def call_vision(image_bytes: bytes, media_type: str) -> tuple[dict[str, Any], Any, float]:
    """anthropic SDK multimodal call. (parsed_json, usage, latency_s) 반환."""
    client = Anthropic()
    b64 = base64.b64encode(image_bytes).decode("ascii")

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64,
                    },
                },
                {"type": "text", "text": "이 이미지를 OCR 해줘. JSON 스키마 정확히 준수."},
            ],
        }
    ]

    t0 = time.perf_counter()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=VISION_SYSTEM_PROMPT,
        messages=messages,
    )
    latency_s = time.perf_counter() - t0

    # resp.content 는 list[TextBlock | ...]. 첫 TextBlock 의 text 추출.
    result_text = ""
    for block in resp.content:
        text = getattr(block, "text", None)
        if text:
            result_text += text

    parsed = _extract_json(result_text.strip()) if result_text else {}
    return parsed, resp.usage, latency_s


async def _amain(args: argparse.Namespace) -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[fail] ANTHROPIC_API_KEY 미설정 (.env 확인).")
        return 2

    # Step 1-3 — 이미지 source 결정
    image_bytes: bytes | None = None
    image_url: str | None = None
    source_label: str = ""
    page_id: str | None = args.page_id

    if args.image_path:
        p = Path(args.image_path)
        if not p.exists():
            print(f"[fail] --image-path 파일 부재: {p}")
            return 2
        image_bytes = p.read_bytes()
        source_label = f"local file: {p}"
    else:
        if not page_id:
            print("[info] 노션 log DB query (타입=ai_visual AND 셀프 리뷰=true) 최근 1건…")
            row = await query_log_db_recent_ai_visual()
            if not row:
                print("[skip] 노션 log DB 에 ai_visual + 셀프 리뷰 통과 row 없음.")
                print("       --image-path <local.png> 로 강제 또는 운영 e2e 후 재시도.")
                return 1
            page_id = row["page_id"]
            print(f"       log_row_id={row['log_row_id']} page_id={page_id} slot_type={row['slot_type']}")

        print(f"[info] 콘텐츠 페이지 blocks.children.list → image block 추출…")
        image_url = await fetch_image_url_from_page(page_id)
        if not image_url:
            print(f"[skip] page_id={page_id} 에 image block 없음.")
            return 1
        print(f"       image_url={image_url[:100]}…")

        async with httpx.AsyncClient(timeout=30.0) as cli:
            r = await cli.get(image_url)
            r.raise_for_status()
            image_bytes = r.content
        source_label = f"notion page_id={page_id}"

    media_type = media_type_from_url_or_bytes(image_url, image_bytes)
    print(f"[info] image_bytes={len(image_bytes):,} bytes / media_type={media_type}")

    # Step 4-6 — vision call
    print("[info] anthropic SDK Sonnet 4.6 vision call…")
    parsed, usage, latency_s = call_vision(image_bytes, media_type)
    cost_usd = cost_from_usage(usage)

    # Step 7 — 보고
    print()
    print("=" * 70)
    print("Phase 4.3 vision spike — Sonnet 4.6 (anthropic SDK 0.102)")
    print("=" * 70)
    print(f"source           : {source_label}")
    print(f"media_type       : {media_type}")
    print(f"image_bytes_size : {len(image_bytes):,} bytes")
    print()
    print("--- OCR result ---")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
    print()
    print("--- 메트릭 ---")
    print(f"cost_usd         : ${cost_usd:.6f}")
    print(f"latency_s        : {latency_s:.3f}s")
    print(f"input_tokens     : {getattr(usage, 'input_tokens', 0):,}")
    print(f"output_tokens    : {getattr(usage, 'output_tokens', 0):,}")
    print(f"cache_creation   : {getattr(usage, 'cache_creation_input_tokens', 0):,}")
    print(f"cache_read       : {getattr(usage, 'cache_read_input_tokens', 0):,}")
    print()
    print("--- 사용자 대조 ---")
    print("위 OCR result 의 korean_text / english_text 를 본문 사실과 비교.")
    print("text_rule=zero 스타일이면 text_detected=false 가 정상.")
    print("=" * 70)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--page-id", help="콘텐츠 페이지 id (노션 query skip)")
    parser.add_argument("--image-path", help="로컬 PNG/WebP/JPG 파일 (노션 query skip)")
    args = parser.parse_args()

    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        print("\n[abort] 사용자 중단")
        return 130
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
