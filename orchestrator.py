"""한 사이클 실행 — 한 페이지의 이미지 슬롯을 결정/생성/업로드하고 status 변경.

pipeline_defs/blog_image.yaml의 명세를 코드로 구현. Phase 1엔 수동 trigger
(scripts/test_phase1.py 또는 scripts/run_one_page.py)에서 호출.

비용 가드 (regen_policy.md):
  - 페이지당 cap $0.30 / 슬롯당 시도 3회 (첫 시도 + 재시도 2회)

에러 핸들링 (AGENT_GUIDE §4):
  - 슬롯 단위 try/except — 1개 슬롯 실패해도 다음 슬롯 진행
  - 1개 이상 슬롯 failed → 페이지 status = "이미지 작업 중" (사람 개입 대기)
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from tools.image.webp_converter import png_to_webp
from tools.llm._common import compact_blocks
from tools.llm.analyze_content import analyze_content
from tools.llm.review import review_input
from tools.notion import get_client
from tools.notion.fetch_pages import fetch_pages_by_status  # noqa: F401 (run_many에서 사용 예정)
from tools.notion.get_page_content import get_page_blocks
from tools.notion.insert_image_block import insert_image_block
from tools.notion.log_metadata import log_metadata
from tools.notion.update_status import update_page_status
from tools.notion.upload_image import upload_image
from tools.render.chart_render import (
    ChartDataError,
    ChartLineData,
    render_chart_line,
)
from tools.render.template_render import render_template

logger = logging.getLogger(__name__)

# Phase 1 검증 단계 한정 — 안정화 후 plan §13 기준 0.30 복귀 목표.
# 슬롯 3개 페이지: analyze ~$0.19 + (review ~$0.10 + 기타) × 3 = 합 ~$0.70 실측.
# Phase 2에서 비용 최적화 (CLI auto-mode Haiku 보조 호출 끄기, review_input 본문 압축 등).
PER_PAGE_CAP_USD = 1.00
PER_SLOT_ATTEMPTS = 3
SUPPORTED_TYPES = {"simple_table", "chart"}
SUPPORTED_CHART_SUB_TYPES = {"line"}


@dataclass
class SlotResult:
    type: str
    sub_type: str | None
    passed: bool
    new_block_id: str | None
    issues: list[str]
    cost_usd: float
    attempts: int


@dataclass
class PageResult:
    page_id: str
    slots_total: int
    slots_passed: int
    slots_failed: int
    cost_usd: float
    final_status: str
    slot_results: list[SlotResult]


def _blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    """본문 일치 검증(review_input)을 위한 plain text 추출.

    `compact_blocks`와 동일 source 사용 — table_row.cells 등 모든 본문 구조 포함.
    두 path가 갈라지면 analyze는 보고 review는 못 보는 false-positive 위반 발생.
    """
    return "\n".join(c["text"] for c in compact_blocks(blocks))


async def _render_slot(
    slot: dict[str, Any], out_png: Path,
) -> None:
    """슬롯 type별 렌더 분기. 실패 시 예외 raise."""
    stype = slot["type"]
    data = slot["extracted_data"]
    if stype == "chart":
        sub = slot.get("sub_type")
        if sub != "line":
            raise ValueError(f"Phase 1엔 chart sub_type='line'만 지원 (받은 값: {sub!r})")
        chart = ChartLineData(
            title=data["title"],
            labels=data["labels"],
            values=data["values"],
            point_labels=data["point_labels"],
            sub_labels=data.get("sub_labels"),
            y_unit=data.get("y_unit"),
            source=data.get("source"),
            y_min=data.get("y_min"),
            y_max=data.get("y_max"),
        )
        await render_chart_line(chart, out_png)
    elif stype == "simple_table":
        await render_template(
            "simple_table",
            dict(
                title=data.get("title"),
                headers=data["headers"],
                rows=data["rows"],
                footnote=data.get("footnote"),
                highlight_first_col=data.get("highlight_first_col", False),
            ),
            out_png,
        )
    else:
        raise ValueError(f"Phase 1엔 type={stype!r} 미지원")


async def _process_slot(
    slot: dict[str, Any],
    page_id: str,
    page_source: Literal["블로그", "웹"],
    page_text: str,
    log_db_id: str,
    work_dir: Path,
    page_cost_so_far: float,
) -> SlotResult:
    """한 슬롯을 처리. 슬롯 단위 try/except는 호출자(run_for_page) 담당."""
    stype = slot["type"]
    sub = slot.get("sub_type")
    issues: list[str] = []
    slot_cost = 0.0
    attempts = 0
    new_block_id: str | None = None
    review_passed = False

    # 형식 검증 (코드)
    if stype not in SUPPORTED_TYPES:
        issues.append(f"Phase 1 미지원 type: {stype}")
        return SlotResult(stype, sub, False, None, issues, 0.0, 0)

    # review_input — 본문 일치 + §23
    try:
        review, c = await review_input(stype, slot["extracted_data"], page_text)
        slot_cost += c
        if not review["passed"]:
            issues.extend(review.get("issues", []))
            if review.get("revised_data"):
                # 1회 재시도용 revised_data로 교체
                slot = {**slot, "extracted_data": review["revised_data"]}
                logger.info("review_input 자동 수정 적용")
            else:
                return SlotResult(stype, sub, False, None, issues, slot_cost, 0)
    except Exception as e:
        issues.append(f"review_input 예외: {e}")
        return SlotResult(stype, sub, False, None, issues, slot_cost, 0)

    # 렌더 + 업로드 (시도 PER_SLOT_ATTEMPTS회)
    while attempts < PER_SLOT_ATTEMPTS:
        attempts += 1
        try:
            png = work_dir / f"slot_{stype}_{attempts}.png"
            await _render_slot(slot, png)
            webp = png_to_webp(png)

            # review_image (Phase 1 = 형식 검증만)
            if not webp.exists() or webp.stat().st_size < 1024:
                raise RuntimeError(f"산출 webp가 너무 작음: {webp.stat().st_size} B")
            review_passed = True

            # upload + insert
            file_upload_id = await upload_image(webp)
            new_block_id = await insert_image_block(
                parent_id=page_id,
                after_block_id=slot["position_after_block_id"],
                file_upload_id=file_upload_id,
            )
            break
        except ChartDataError as e:
            issues.append(f"차트 데이터 검증 실패: {e}")
            break  # 데이터 검증은 재시도 무의미
        except Exception as e:
            issues.append(f"시도 {attempts} 실패: {e}")
            logger.warning("slot %s 시도 %d 실패: %s", stype, attempts, e)

    # 페이지 비용 cap 체크 (시도 후)
    if page_cost_so_far + slot_cost > PER_PAGE_CAP_USD:
        issues.append(f"페이지 비용 cap 초과 ({page_cost_so_far + slot_cost:.3f} USD)")

    # 로그 기록 (성공/실패 무관)
    try:
        await log_metadata(
            log_db_id=log_db_id,
            page_id=page_id,
            page_source=page_source,
            slot_type=stype,
            slot_sub_type=sub,
            generation_method="template",
            input_data={
                **slot["extracted_data"],
                "notion_block_id": new_block_id,
            },
            cost_usd=slot_cost,
            attempts=attempts,
            review_passed=review_passed and new_block_id is not None,
        )
    except Exception as e:
        logger.error("log_metadata 실패 (계속 진행): %s", e)

    return SlotResult(
        type=stype,
        sub_type=sub,
        passed=new_block_id is not None,
        new_block_id=new_block_id,
        issues=issues,
        cost_usd=slot_cost,
        attempts=attempts,
    )


async def run_for_page(
    page_id: str,
    page_source: Literal["블로그", "웹"],
    log_db_id: str,
) -> PageResult:
    """한 페이지 처리. 슬롯 분석 → 슬롯별 생성/업로드 → status 변경."""
    # update_page_status가 status 속성 타입(select/status) 감지하려면 database_id 필요.
    # multi-source DB도 parent.database_id 항상 채워주므로 page retrieve 한 번으로 추출.
    page = await asyncio.to_thread(lambda: get_client().pages.retrieve(page_id))
    content_db_id = (page.get("parent") or {}).get("database_id")
    if not content_db_id:
        raise RuntimeError(f"page {page_id} parent에 database_id 없음: {page.get('parent')}")

    blocks = await get_page_blocks(page_id)
    page_text = _blocks_to_text(blocks)

    slots, analyze_cost = await analyze_content(blocks)
    logger.info("analyze_content: %d 슬롯, $%.4f", len(slots), analyze_cost)

    page_cost = analyze_cost
    results: list[SlotResult] = []

    with tempfile.TemporaryDirectory(prefix="ehyun_render_") as tmp:
        work_dir = Path(tmp)
        for slot in slots:
            try:
                r = await _process_slot(
                    slot, page_id, page_source, page_text,
                    log_db_id, work_dir, page_cost,
                )
            except Exception as e:
                logger.exception("슬롯 %r 예외 — 다음 슬롯 진행", slot.get("type"))
                r = SlotResult(
                    type=slot.get("type", "?"), sub_type=slot.get("sub_type"),
                    passed=False, new_block_id=None,
                    issues=[f"orchestrator 예외: {e}"], cost_usd=0.0, attempts=0,
                )
            results.append(r)
            page_cost += r.cost_usd
            if page_cost > PER_PAGE_CAP_USD:
                logger.warning("페이지 비용 cap 초과 — 남은 슬롯 폐기")
                break

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    final_status = "이미지 작업 중" if failed > 0 else "발행 필요"

    try:
        await update_page_status(page_id, final_status, database_id=content_db_id)
    except Exception:
        logger.exception("update_page_status 실패")

    return PageResult(
        page_id=page_id,
        slots_total=len(results),
        slots_passed=passed,
        slots_failed=failed,
        cost_usd=page_cost,
        final_status=final_status,
        slot_results=results,
    )
