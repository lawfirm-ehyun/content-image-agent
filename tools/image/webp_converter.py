"""PNG → WebP 변환. Pillow 기반.

Notion inline 이미지 용량을 줄이기 위해 카드 PNG 산출물을 WebP로 변환한다.

기본 lossless: 카드 콘텐츠는 텍스트 + 단색 배경 + 단순 차트라 WebP lossless 알고리즘이
lossy보다 오히려 더 작게 압축됨 (실측: PNG 34KB → lossless 14KB / lossy q=92 24KB).
+ 텍스트 가장자리 손상 없음. 일반 사진과는 반대 패턴이라 주의.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from tools.limits import WEBP_LOSSLESS_DEFAULT, WEBP_METHOD


def png_to_webp(
    png_path: Path,
    webp_path: Path | None = None,
    *,
    lossless: bool = WEBP_LOSSLESS_DEFAULT,
    quality: int = 92,
) -> Path:
    """PNG을 WebP로 변환. 변환된 경로 반환.

    동기 함수 (Pillow는 동기 + CPU 바운드). orchestrator에서 비동기 흐름이면
    `asyncio.to_thread(png_to_webp, ...)`로 감싸 호출.

    png_path  : 입력 PNG 경로 (반드시 존재).
    webp_path : 출력 경로. None이면 입력 옆에 동일 stem + .webp.
    lossless  : 기본 True (카드 콘텐츠 최적). lossy로 강제할 때만 False.
    quality   : 0-100. lossless=True면 무시. lossy 사용 시(예: 사진/스크린샷) 92 권장.
    """
    if webp_path is None:
        webp_path = png_path.with_suffix(".webp")

    with Image.open(png_path) as im:
        im.save(
            webp_path,
            format="WEBP",
            quality=quality,
            lossless=lossless,
            method=WEBP_METHOD,
        )
    return webp_path
