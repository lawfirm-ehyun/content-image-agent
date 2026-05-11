"""Playwright + Jinja2 기반 카드 템플릿 렌더러.

templates/{name}.html을 변수로 채워 PNG로 캡처한다.
WebP 변환은 호출 측 (tools/image/webp_converter.py)에서.
데이터 검증/변호사법 §23 검사는 호출 측 (skills/meta/prompt_review)에서 끝난 상태로 가정.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT / "templates"


@dataclass(frozen=True)
class CardSize:
    width: int
    height: int


SIZES: dict[str, CardSize] = {
    "default":  CardSize(1200, 675),
    "square":   CardSize(1080, 1080),
    "vertical": CardSize(1080, 1350),
}


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(("html",)),
        undefined=StrictUndefined,                   # 누락 변수 = 즉시 에러 (조용한 빈셀 방지)
    )


async def render_template(
    template_name: str,
    variables: dict[str, Any],
    out_path: Path,
    size: str | CardSize = "default",
) -> Path:
    """templates/{template_name}.html을 렌더해 PNG로 저장. 저장 경로 반환.

    template_name: 'simple_table' / 'chart_line' (확장자 제외)
    variables: Jinja2에 주입될 dict
    out_path: PNG 저장 경로 (.png)
    size: SIZES key 또는 CardSize. .card 위에 inline override 적용은 안 하고 viewport만 맞춤.
          (.card는 _base.css에서 1200x675 fixed. vertical/square 카드는 향후 modifier class로.)
    """
    if isinstance(size, str):
        size = SIZES[size]

    html = _env().get_template(f"{template_name}.html").render(**variables)

    # 임시 HTML을 templates/ 안에 두어야 _base.css와 ../assets/fonts 상대 경로가 살아남는다.
    tmp = NamedTemporaryFile(
        mode="w", suffix=".html", prefix="_render_", dir=TEMPLATES_DIR,
        delete=False, encoding="utf-8",
    )
    tmp.write(html)
    tmp.close()
    tmp_path = Path(tmp.name)

    # §19.4 — Chart.js CDN / Pretendard 로드 실패 시 silent corruption 방지.
    # chart 템플릿은 `window.Chart` + 폰트 check, 그 외 템플릿은 폰트 check만.
    # 실패하면 빈 캔버스(>1KB 통과)나 fallback sans-serif 캡처라 사후 검증으로 못 잡음.
    is_chart = template_name.startswith("chart")
    if is_chart:
        wait_expr = "window.Chart != null && document.fonts.check('700 30px Pretendard')"
    else:
        wait_expr = "document.fonts.check('700 30px Pretendard')"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(
                viewport={"width": size.width, "height": size.height},
                device_scale_factor=1,
            )
            await page.goto(tmp_path.as_uri())
            # §19.4 — Chart.js + Pretendard 둘 다 ready인지 명시적 검증 (timeout 5s).
            await page.wait_for_function(wait_expr, timeout=5000)
            # Chart.js animation은 템플릿에서 off지만, 첫 페인트 안정화 위해 짧게 대기
            await page.wait_for_timeout(200)
            await page.locator(".card").screenshot(path=str(out_path))
            await browser.close()
    finally:
        tmp_path.unlink(missing_ok=True)

    return out_path
