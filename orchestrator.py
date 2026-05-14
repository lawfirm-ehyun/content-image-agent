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
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from tools.budget import RunBudget
from tools.image.webp_converter import png_to_webp
from tools.limits import (
    PER_PAGE_CAP_USD,
    PER_RUN_CAP_USD,
    PER_SLOT_ATTEMPTS,
    PER_SLOT_COST_CAP_USD,
)
from tools.llm._common import compact_blocks
from tools.llm.analyze_content import analyze_content
from tools.llm.review import review_input
from tools.notion import get_client, norm_uuid
from tools.notion.fetch_pages import fetch_pages_by_status
from tools.notion.get_page_content import get_page_blocks
from tools.notion.insert_image_block import insert_image_block
from tools.notion.log_metadata import get_logged_page_ids, log_metadata
from tools.notion.update_status import update_page_status
from tools.notion.upload_image import upload_image
from tools.render.ai_render import render_ai_card
from tools.render.chart_render import (
    ChartDataError,
    ChartSpec,
    render_chart,
)
from tools.render.template_render import render_template

logger = logging.getLogger(__name__)

# v1.6.1: Phase 3 감성형 카드 (illustration / kakao_dialogue) 추가.
SUPPORTED_TYPES = {
    "simple_table", "chart", "comparison_table", "timeline", "key_points_card",
    "illustration", "kakao_dialogue",
}
SUPPORTED_CHART_SUB_TYPES = {"line", "bar", "donut", "pie"}
AI_CARD_TYPES = {"illustration", "kakao_dialogue"}  # ai_render path로 분기되는 카드


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


async def _log_review_dispose(
    *,
    log_db_id: str,
    page_id: str,
    page_source: Literal["블로그", "웹"],
    slot_type: str,
    slot_sub_type: str | None,
    issues: list[str],
    cost_usd: float,
) -> None:
    """review_input 단계에서 슬롯이 폐기됐을 때 로그 DB 1행 기록 (plan v1.2 §19.5).

    attempts=0 = "review_input 단계 폐기"의 운영 신호.
    regen_policy.md "모든 시도 1행 기록" 룰을 review fail path에서도 충족시키기 위함.
    """
    try:
        await log_metadata(
            log_db_id=log_db_id,
            page_id=page_id,
            page_source=page_source,
            slot_type=slot_type,
            slot_sub_type=slot_sub_type,
            generation_method="template",
            input_data={"notion_block_id": None, "issues": list(issues)},
            cost_usd=cost_usd,
            attempts=0,
            review_passed=False,
        )
    except Exception as e:
        logger.error("log_metadata (review dispose) 실패 (계속 진행): %s", e)


async def _render_slot(
    slot: dict[str, Any], out_png: Path,
) -> float:
    """슬롯 type별 렌더 분기. 실패 시 예외 raise.

    반환: image generation 비용 USD (template/chart는 0.0, AI 카드는 gpt-image 비용).
    LLM review 비용은 caller(_process_slot)가 별도 누적.
    """
    stype = slot["type"]
    data = slot["extracted_data"]
    if stype == "chart":
        sub = slot.get("sub_type")
        if sub not in SUPPORTED_CHART_SUB_TYPES:
            raise ValueError(
                f"지원되지 않는 chart sub_type={sub!r} "
                f"(지원: {sorted(SUPPORTED_CHART_SUB_TYPES)})"
            )
        # 필수 필드 누락은 ChartDataError로 raise — orchestrator가 재시도 없이 즉시 폐기.
        # line/bar는 point_labels 필수, donut/pie는 옵션 (자동 % 계산 가능).
        line_bar_required = ("title", "labels", "values", "point_labels")
        donut_pie_required = ("title", "labels", "values")
        required = donut_pie_required if sub in {"donut", "pie"} else line_bar_required
        missing = [k for k in required if k not in data]
        if missing:
            raise ChartDataError(f"chart sub_type={sub} 필수 필드 누락: {missing}")

        # Week 3a (plan §12.2): 4 sub-type 단일 ChartSpec + master_chart.html path.
        # Week 3b: orientation(line/bar) + emphasis_index(공통) 2축 parametric.
        # 둘 다 default(vertical, None)면 Week 3a byte-identity 동작 유지.
        # line/bar는 sub_labels/y_unit/y_min/y_max를 사용, donut/pie는 무시(ChartSpec에선 None).
        spec = ChartSpec(
            sub_type=sub,
            title=data["title"],
            labels=data["labels"],
            values=data["values"],
            point_labels=data.get("point_labels"),
            sub_labels=data.get("sub_labels"),
            y_unit=data.get("y_unit"),
            y_min=data.get("y_min"),
            y_max=data.get("y_max"),
            source=data.get("source"),
            orientation=data.get("orientation", "vertical"),
            emphasis_index=data.get("emphasis_index"),
        )
        await render_chart(spec, out_png)
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
    elif stype == "key_points_card":
        items = data.get("items") or []
        if len(items) < 3:
            raise ChartDataError(
                f"key_points_card는 최소 3개 항목 필요 (받은 값: {len(items)})"
            )
        if len(items) > 6:
            raise ChartDataError(
                f"key_points_card는 최대 5개 권장, 6개+면 슬롯 분할 (받은 값: {len(items)})"
            )
        for i, item in enumerate(items):
            if not item.get("label"):
                raise ChartDataError(f"items[{i}]에 label 누락 (필수)")
        await render_template(
            "key_points_card",
            dict(
                title=data.get("title"),
                items=items,
                footnote=data.get("footnote"),
            ),
            out_png,
        )
    elif stype == "timeline":
        steps = data.get("steps") or []
        if not steps or len(steps) < 3:
            raise ChartDataError(
                f"timeline은 최소 3 단계 필요 (받은 값: {len(steps)})"
            )
        for i, step in enumerate(steps):
            if not step.get("label"):
                raise ChartDataError(f"steps[{i}]에 label 누락 (필수)")
        await render_template(
            "timeline",
            dict(
                title=data.get("title"),
                steps=steps,
                footnote=data.get("footnote"),
            ),
            out_png,
        )
    elif stype == "comparison_table":
        # 구조 검증 — column_headers/rows length mismatch는 LLM 환각 신호 → 즉시 폐기.
        # v1.4: highlight_column_index 제거 (§23 광고성 신호 회피) — 모든 비교 컬럼 동등.
        headers = data["column_headers"]
        rows = data["rows"]
        expected_values_len = len(headers) - 1
        for i, row in enumerate(rows):
            if len(row.get("values", [])) != expected_values_len:
                raise ChartDataError(
                    f"rows[{i}].values 길이({len(row.get('values', []))}) ≠ "
                    f"column_headers - 1 ({expected_values_len})"
                )
        await render_template(
            "comparison_table",
            dict(
                title=data.get("title"),
                column_headers=headers,
                rows=rows,
                footnote=data.get("footnote"),
            ),
            out_png,
        )
    elif stype in AI_CARD_TYPES:
        # v1.6.1 — AI 카드 (illustration / kakao_dialogue). ai_render가 gpt-image 호출 + PNG 저장.
        result = await render_ai_card(stype, data, out_png)
        return result.cost_usd
    else:
        raise ValueError(f"지원되지 않는 type={stype!r}")
    return 0.0  # template / chart는 generation 비용 0 (LLM review만 누적)


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
                # §19.5 — review fail + 자동 수정 불가 시에도 로그 1행 기록 (attempts=0).
                await _log_review_dispose(
                    log_db_id=log_db_id, page_id=page_id, page_source=page_source,
                    slot_type=stype, slot_sub_type=sub,
                    issues=issues, cost_usd=slot_cost,
                )
                return SlotResult(stype, sub, False, None, issues, slot_cost, 0)
    except Exception as e:
        issues.append(f"review_input 예외: {e}")
        # §19.5 — review_input 자체 예외도 폐기. 동일 룰 적용.
        await _log_review_dispose(
            log_db_id=log_db_id, page_id=page_id, page_source=page_source,
            slot_type=stype, slot_sub_type=sub,
            issues=issues, cost_usd=slot_cost,
        )
        return SlotResult(stype, sub, False, None, issues, slot_cost, 0)

    # 렌더 + 업로드 (시도 PER_SLOT_ATTEMPTS회)
    image_cost_total = 0.0  # v1.6.1 — AI 카드(gpt-image) 비용 누적
    while attempts < PER_SLOT_ATTEMPTS:
        attempts += 1
        try:
            png = work_dir / f"slot_{stype}_{attempts}.png"
            image_cost = await _render_slot(slot, png)
            image_cost_total += image_cost
            slot_cost += image_cost
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

    # 비용 cap 체크 (시도 후)
    if slot_cost > PER_SLOT_COST_CAP_USD:
        issues.append(f"슬롯 비용 cap 초과 ({slot_cost:.3f} USD > {PER_SLOT_COST_CAP_USD})")
    if page_cost_so_far + slot_cost > PER_PAGE_CAP_USD:
        issues.append(f"페이지 비용 cap 초과 ({page_cost_so_far + slot_cost:.3f} USD)")

    # v1.6.1 — generation_method: AI 카드 분기. quality에 따라 instant/thinking.
    if stype == "illustration":
        gen_method: Literal["template", "gpt-image-2-instant", "gpt-image-2-thinking"] = (
            "gpt-image-2-instant"
        )
    elif stype == "kakao_dialogue":
        gen_method = "gpt-image-2-thinking"
    else:
        gen_method = "template"

    # 로그 기록 (성공/실패 무관)
    try:
        await log_metadata(
            log_db_id=log_db_id,
            page_id=page_id,
            page_source=page_source,
            slot_type=stype,
            slot_sub_type=sub,
            generation_method=gen_method,
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

    # §19.6 — 슬롯 0개 페이지도 운영 추적용 1행 기록. 운영팀이 "왜 이미지가 안 들어갔지?"
    # 확인 가능하게. 로그 DB '타입' select에 '없음' 옵션이 추가돼야 통과 (plan §19.6 운영 작업).
    if not slots:
        try:
            await log_metadata(
                log_db_id=log_db_id,
                page_id=page_id,
                page_source=page_source,
                slot_type="없음",
                slot_sub_type=None,
                generation_method="template",
                input_data={"reason": "no_slots", "blocks_count": len(blocks)},
                cost_usd=analyze_cost,
                attempts=0,
                review_passed=False,
            )
        except Exception as e:
            logger.error(
                "log_metadata (empty slots) 실패 — '타입' select에 '없음' 옵션 추가 필요?: %s", e,
            )

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


# === Phase 2 batch entry (plan §15.2) =========================================
# cron/workflow_dispatch에서 호출. 한 DB의 "이미지 필요" 페이지를 RunBudget 한도 안에서 처리.
# - 페이지 사이 0.5s sleep (Notion rate limit 보호 — §19.3)
# - page-level try/except로 한 페이지 실패가 다음 페이지 차단 X (§19.9)
# - run_budget.exceeded() 도달 시 즉시 중단 (§15.2)

_PAGE_INTERVAL_S = 0.5
_DEFAULT_BATCH_LIMIT = 5


async def process_database(
    db_id: str,
    source: Literal["블로그", "웹"],
    log_db_id: str,
    run_budget: RunBudget,
    *,
    limit: int = _DEFAULT_BATCH_LIMIT,
) -> list[PageResult]:
    """한 콘텐츠 DB의 '이미지 필요' 페이지를 RunBudget 한도 안에서 처리.

    db_id     : 콘텐츠 DB id (블로그 또는 웹).
    source    : 로그 DB '출처' select 값 ("블로그" | "웹").
    log_db_id : 로그 DB id.
    run_budget: run-level 누적 비용 추적 (limit 도달 시 break).
    limit     : 한 호출에서 fetch할 페이지 수 (default 5).
    """
    pages = await fetch_pages_by_status(db_id, status="이미지 필요", limit=limit)
    logger.info("[%s] '이미지 필요' 페이지 %d건 fetch", source, len(pages))

    # §19.1 멱등성 — 로그 DB 최근 100건에서 처리 이력 있는 page_id set 조회.
    # batch 시작 시 1회만 fetch. cron 5건 처리 + 1시간 주기라 최근 100건이면 충분.
    logged_ids = await get_logged_page_ids(log_db_id, limit=100)
    logger.info("[%s] 로그 이력 페이지 %d건 로드 — skip 후보", source, len(logged_ids))

    out: list[PageResult] = []
    for page in pages:
        if run_budget.exceeded():
            logger.warning(
                "[%s] run-level 비용 cap 도달 ($%.4f > $%.2f) — 남은 페이지 폐기",
                source, run_budget.spent_usd, run_budget.cap_usd,
            )
            break

        page_id = page["id"]
        if norm_uuid(page_id) in logged_ids:
            logger.warning(
                "[%s] page %s 처리 이력 발견 — skip (§19.1 멱등성). "
                "재처리 원하면 로그 row + 기존 image block 수동 제거 필요.",
                source, page_id,
            )
            continue

        try:
            r = await run_for_page(page_id, source, log_db_id)
            run_budget.add(r.cost_usd)
            out.append(r)
            logger.info(
                "[%s] page %s 완료 — 슬롯 %d/%d, $%.4f (run 누적 $%.4f)",
                source, page_id, r.slots_passed, r.slots_total, r.cost_usd,
                run_budget.spent_usd,
            )
        except Exception:
            logger.exception("[%s] page %s 처리 실패 — 다음 페이지 진행", source, page_id)

        await asyncio.sleep(_PAGE_INTERVAL_S)

    return out


async def main() -> None:
    """cron / workflow_dispatch 진입점. 블로그 + 웹 DB 순차 처리."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # .env 지원 — GitHub Actions는 secrets로 환경변수 주입, 로컬은 .env 사용.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    log_db_id = os.environ["NOTION_DB_LOG"].strip()
    blog_db_id = os.environ["NOTION_DB_BLOG"].strip()
    web_db_id = os.environ["NOTION_DB_WEB"].strip()

    budget = RunBudget(cap_usd=PER_RUN_CAP_USD)
    logger.info("=== run 시작 — cap $%.2f ===", PER_RUN_CAP_USD)

    blog_results = await process_database(blog_db_id, "블로그", log_db_id, budget)
    web_results = await process_database(web_db_id, "웹", log_db_id, budget)

    total_pages = len(blog_results) + len(web_results)
    total_passed = sum(r.slots_passed for r in blog_results + web_results)
    total_slots = sum(r.slots_total for r in blog_results + web_results)
    logger.info(
        "=== run 완료 — 페이지 %d (블로그 %d + 웹 %d), 슬롯 %d/%d 통과, $%.4f / $%.2f ===",
        total_pages, len(blog_results), len(web_results),
        total_passed, total_slots, budget.spent_usd, budget.cap_usd,
    )


if __name__ == "__main__":
    asyncio.run(main())
