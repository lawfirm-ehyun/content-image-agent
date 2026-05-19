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

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# Jinja2 StrictUndefined 환경의 missing key/attr 에러 — 데이터 결함 (재시도 무의미).
# 5/18 e2e: timeline의 옵션 필드 `duration` 누락이 매번 같은 에러를 일으켰음 → 3회 헛재시도.
from jinja2 import UndefinedError as JinjaUndefinedError

from tools.budget import RunBudget
from tools.image.webp_converter import png_to_webp
from tools.limits import (
    ALT_TEXT_MAX_CHARS,
    PER_PAGE_CAP_USD,
    PER_RUN_CAP_USD,
    PER_SLOT_ATTEMPTS,
    PER_SLOT_COST_CAP_USD,
)
from tools.llm._common import compact_blocks
from tools.llm.analyze_content import analyze_content
from tools.llm.image_review import review_image
from tools.llm.review import review_input
from tools.notion import extract_page_title, get_client, norm_uuid
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
from tools.visual_styles import load_visual_style

logger = logging.getLogger(__name__)

# v1.6.1: Phase 3 감성형 카드 (illustration / kakao_dialogue) 추가.
# v1.8 Phase 4.2 (2026-05-15): ai_visual 추가 — skills/visual_styles/*.md 기반 라이브러리 카드.
# illustration 은 backwards compat 유지 (ai_visual + point_color_line 으로 점진 흡수).
SUPPORTED_TYPES = {
    "simple_table", "chart", "comparison_table", "timeline", "key_points_card",
    "illustration", "kakao_dialogue", "ai_visual",
}
SUPPORTED_CHART_SUB_TYPES = {"line", "bar", "donut", "pie"}
AI_CARD_TYPES = {"illustration", "kakao_dialogue", "ai_visual"}  # ai_render path로 분기


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


def _resolve_gen_method(stype: str, data: dict[str, Any]) -> str:
    """카드 type별 `생성 방식` 노션 로그값 결정.

    5/18 발견 #1 (orchestrator drift): ai_visual 신설 후 분기 누락으로 항상 'template'
    로 찍히던 버그 fix. ai_visual은 visual_style frontmatter quality 에 따라 분기.

    렌더 성공 전(default) / 렌더 실패 fallback 양쪽에서 사용 — 같은 결정 룰 단일화.
    visual_style 누락/로드 실패면 안전하게 'gpt-image-2-instant' (보수적 = medium quality).
    """
    if stype == "illustration":
        return "gpt-image-2-instant"
    if stype == "kakao_dialogue":
        return "gpt-image-2-thinking"
    if stype == "ai_visual":
        vs_name = (data.get("visual_style") or "").strip()
        if vs_name:
            try:
                vs = load_visual_style(vs_name)
                return (
                    "gpt-image-2-thinking" if vs.quality == "high"
                    else "gpt-image-2-instant"
                )
            except Exception:
                # 폐기될 슬롯이지만 로그상 'template'로 찍히면 운영 혼란 — instant fallback.
                pass
        return "gpt-image-2-instant"
    return "template"


async def _render_slot(
    slot: dict[str, Any], out_png: Path,
) -> tuple[float, str]:
    """슬롯 type별 렌더 분기. 실패 시 예외 raise.

    반환: (image generation 비용 USD, 생성 방식).
      - template/chart: (0.0, "template").
      - AI 카드: (gpt-image 비용, "gpt-image-2-instant" | "gpt-image-2-thinking").
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
        return 0.0, "template"
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
        return 0.0, "template"
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
            # Gap B (2026-05-15): description은 string scalar 필수. LLM이 dict 산출 시
            # Jinja runtime error 대신 깔끔한 ChartDataError 로 dispose (3-retry 처리).
            desc = item.get("description")
            if desc is not None and not isinstance(desc, str):
                raise ChartDataError(
                    f"items[{i}].description 은 string scalar 필수 (받은 타입: {type(desc).__name__})"
                )
            # 5/18 fix: Jinja2 StrictUndefined 환경에서 옵션 필드 누락 = UndefinedError.
            # template의 `{% if item.description %}` 가 missing key 만나면 즉시 raise.
            item.setdefault("description", None)
        await render_template(
            "key_points_card",
            dict(
                title=data.get("title"),
                items=items,
                footnote=data.get("footnote"),
            ),
            out_png,
        )
        return 0.0, "template"
    elif stype == "timeline":
        steps = data.get("steps") or []
        if not steps or len(steps) < 3:
            raise ChartDataError(
                f"timeline은 최소 3 단계 필요 (받은 값: {len(steps)})"
            )
        # Gap B (2026-05-15): description / duration은 string scalar 필수. LLM 이 dict
        # ({value, unit} 등 구조화) 산출 시 Jinja runtime error 대신 깔끔한 ChartDataError
        # 로 dispose. slot_selection.md spec 명시 + 본 가드 = 1차/2차 방어.
        for i, step in enumerate(steps):
            for field in ("description", "duration"):
                val = step.get(field)
                if val is not None and not isinstance(val, str):
                    raise ChartDataError(
                        f"steps[{i}].{field} 은 string scalar 필수 "
                        f"(받은 타입: {type(val).__name__})"
                    )
        for i, step in enumerate(steps):
            if not step.get("label"):
                raise ChartDataError(f"steps[{i}]에 label 누락 (필수)")
            # 5/18 fix (root cause of timeline 100% 실패): timeline.html 의
            # `{% if step.duration %}` / `step.icon` / `step.description` 이 Jinja2
            # StrictUndefined 환경에서 missing key 만나면 즉시 UndefinedError.
            # LLM이 옵션 필드를 안 넣어도 정상이므로 None으로 명시.
            step.setdefault("description", None)
            step.setdefault("duration", None)
            step.setdefault("icon", None)
        await render_template(
            "timeline",
            dict(
                title=data.get("title"),
                steps=steps,
                footnote=data.get("footnote"),
            ),
            out_png,
        )
        return 0.0, "template"
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
        return 0.0, "template"
    elif stype in AI_CARD_TYPES:
        # v1.6.1 — AI 카드 (illustration / kakao_dialogue / ai_visual). ai_render가
        # gpt-image 호출 + PNG 저장. 5/18 fix: ai_visual gen_method가 항상 'template'로
        # 찍히던 분기 누락 버그 — ImageResult.quality 기반으로 instant/thinking 결정.
        result = await render_ai_card(stype, data, out_png)
        if stype == "illustration":
            gen_method = "gpt-image-2-instant"
        elif stype == "kakao_dialogue":
            gen_method = "gpt-image-2-thinking"
        else:  # ai_visual
            gen_method = (
                "gpt-image-2-thinking" if result.quality == "high"
                else "gpt-image-2-instant"
            )
        return result.cost_usd, gen_method
    else:
        raise ValueError(f"지원되지 않는 type={stype!r}")


async def _process_slot(
    slot: dict[str, Any],
    page_id: str,
    page_source: Literal["블로그", "웹"],
    page_text: str,
    log_db_id: str,
    work_dir: Path,
    page_cost_so_far: float,
    page_title: str = "",
    seen_alts: set[str] | None = None,
) -> SlotResult:
    """한 슬롯을 처리. 슬롯 단위 try/except는 호출자(run_for_page) 담당.

    page_title: alt_text target keyword 검증 source (v1.9 plan §13).
    seen_alts:  페이지 안 alt_text 중복 검사용 set (orchestrator mutates).
    """
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

    # review_input — 본문 일치 + §23 + alt_text 검증 (v1.9)
    try:
        review, c = await review_input(stype, slot["extracted_data"], page_text, page_title)
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
    # Phase 4.3 (plan §19.16): AI 카드 vision 검수 retry 1회 hard cap.
    # vision fail / 예외 발생 시 다음 attempt 에서 gpt-image 재호출 + vision 재검수.
    # retry 1회 소진 후에도 fail 이면 슬롯 폐기 (break).
    vision_retry_used = False
    # 5/18 fix: 렌더 성공 전(default)에도 노션 로그에 정확한 gen_method 박기 위해
    # slot 데이터 기반 사전 결정. 렌더 성공 시 _render_slot 반환값으로 덮어씀.
    gen_method: str = _resolve_gen_method(stype, slot["extracted_data"])
    while attempts < PER_SLOT_ATTEMPTS:
        attempts += 1
        try:
            png = work_dir / f"slot_{stype}_{attempts}.png"
            image_cost, gen_method = await _render_slot(slot, png)
            image_cost_total += image_cost
            slot_cost += image_cost
            webp = png_to_webp(png)

            # review_image (Phase 1 = 형식 검증만)
            if not webp.exists() or webp.stat().st_size < 1024:
                raise RuntimeError(f"산출 webp가 너무 작음: {webp.stat().st_size} B")

            # Phase 4.3 — AI 카드만 vision 검수 (text_rule=zero MVP).
            # 정보형 5종 (simple_table/chart/comparison_table/key_points_card/timeline) 은
            # _render_slot 가 template/chart path 로 렌더 — vision 환각 위험 0, skip.
            if stype in AI_CARD_TYPES:
                visual_style = (
                    slot["extracted_data"].get("visual_style")
                    if stype == "ai_visual" else None
                )
                try:
                    verdict, vision_cost = await review_image(
                        stype, webp, visual_style=visual_style,
                    )
                    slot_cost += vision_cost
                except Exception as e:
                    # plan §19.16 사상 — vision 예외도 폐기 (안전 측면).
                    # API 다운 / key 만료 / timeout → AI 카드 ship 차단.
                    issues.append(f"vision_review 예외 (시도 {attempts}): {e}")
                    logger.error(
                        "slot %s vision_review 예외 시도 %d: %s", stype, attempts, e,
                    )
                    if not vision_retry_used:
                        vision_retry_used = True
                        continue
                    break

                if not verdict["passed"]:
                    issues.append(
                        f"vision_review 폐기 (시도 {attempts}): {verdict['reason']}"
                    )
                    logger.warning(
                        "slot %s vision fail 시도 %d: %s",
                        stype, attempts, verdict["reason"],
                    )
                    if not vision_retry_used:
                        vision_retry_used = True
                        continue  # retry 1회 — 다음 attempt 에서 재시도
                    break  # retry 소진 — 폐기

            review_passed = True

            # v1.9 plan §13 — caption-only alt_text 트랙. 80자 초과/빈값/페이지 중복 시 caption 생략.
            alt_raw = (slot["extracted_data"].get("alt_text") or "").strip()
            alt_status: Literal["ok", "empty", "truncated", "duplicate"] = "ok"
            caption_to_send = ""
            if not alt_raw:
                alt_status = "empty"
            elif len(alt_raw) > ALT_TEXT_MAX_CHARS:
                alt_status = "truncated"
                logger.warning(
                    "slot %s alt_text %d자 > %d 한계 — caption 생략 (슬롯은 살림)",
                    stype, len(alt_raw), ALT_TEXT_MAX_CHARS,
                )
            elif seen_alts is not None and alt_raw in seen_alts:
                alt_status = "duplicate"
                logger.warning(
                    "slot %s alt_text 페이지 안 중복 — caption 생략: %r", stype, alt_raw,
                )
            else:
                caption_to_send = alt_raw
                if seen_alts is not None:
                    seen_alts.add(alt_raw)

            # upload + insert
            file_upload_id = await upload_image(webp)
            new_block_id = await insert_image_block(
                parent_id=page_id,
                after_block_id=slot["position_after_block_id"],
                file_upload_id=file_upload_id,
                caption=caption_to_send,
            )
            slot.setdefault("_runtime", {})["alt_text_status"] = alt_status
            break
        except (ChartDataError, ValueError, JinjaUndefinedError, KeyError) as e:
            # 5/18 fix (root cause #4 헛재시도 차단):
            # - ChartDataError: 정보형 카드 데이터 검증 실패
            # - ValueError: ai_render의 visual_style 누락 등 입력 결함
            # - JinjaUndefinedError: StrictUndefined 환경 옵션 필드 missing
            # - KeyError: dict access 누락
            # 모두 같은 input 으로 재시도해도 안 풀림 → 즉시 break.
            issues.append(f"데이터 결함 (시도 {attempts}): {type(e).__name__}: {e}")
            logger.warning(
                "slot %s 데이터 결함 시도 %d (재시도 중단): %s: %s",
                stype, attempts, type(e).__name__, e,
            )
            break
        except Exception as e:
            issues.append(f"시도 {attempts} 실패: {e}")
            logger.warning("slot %s 시도 %d 실패: %s", stype, attempts, e)

    # 비용 cap 체크 (시도 후)
    if slot_cost > PER_SLOT_COST_CAP_USD:
        issues.append(f"슬롯 비용 cap 초과 ({slot_cost:.3f} USD > {PER_SLOT_COST_CAP_USD})")
    if page_cost_so_far + slot_cost > PER_PAGE_CAP_USD:
        issues.append(f"페이지 비용 cap 초과 ({page_cost_so_far + slot_cost:.3f} USD)")

    # 5/18 fix: gen_method 결정 분기를 _render_slot/_resolve_gen_method 로 일원화.
    # ai_visual 분기 누락(stype else로 빠져 'template' 로 잘못 찍히던 버그) 해소.

    # 로그 기록 (성공/실패 무관) — gen_method 는 Literal 제약 만족 (Final 상수 set).
    _gm: Literal["template", "gpt-image-2-instant", "gpt-image-2-thinking"] = (
        gen_method  # type: ignore[assignment]
    )
    # v1.9 plan §13.8 — alt_text_status 운영 모니터링.
    # _runtime 은 caption 분기 시 set 됨. 렌더 전 폐기 케이스는 status 미정 ("unknown") 로 흡수.
    alt_runtime_status = (slot.get("_runtime") or {}).get("alt_text_status", "unknown")
    try:
        await log_metadata(
            log_db_id=log_db_id,
            page_id=page_id,
            page_source=page_source,
            slot_type=stype,
            slot_sub_type=sub,
            generation_method=_gm,
            input_data={
                **slot["extracted_data"],
                "notion_block_id": new_block_id,
                "alt_text_status": alt_runtime_status,
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

    # v1.9 plan §13 — alt_text target keyword source. 빈 title 도 OK (alt 생성은 가능, 일관성만 ↓).
    page_title = extract_page_title(page)
    if not page_title:
        logger.warning("page %s title 비어있음 — alt_text target keyword 일관성 ↓", page_id)

    blocks = await get_page_blocks(page_id)
    page_text = _blocks_to_text(blocks)

    slots, analyze_cost = await analyze_content(blocks, page_title=page_title)
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
    # v1.9 plan §13.5 #6 — 페이지 안 alt_text 중복 검사용 set. _process_slot 가 caption 박힐 때 add.
    seen_alts: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="ehyun_render_") as tmp:
        work_dir = Path(tmp)
        for slot in slots:
            try:
                r = await _process_slot(
                    slot, page_id, page_source, page_text,
                    log_db_id, work_dir, page_cost,
                    page_title=page_title, seen_alts=seen_alts,
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


async def list_pending_pages() -> list[dict[str, str]]:
    """matrix fan-out 용 `--mode list` 핸들러.

    블로그 + 웹 DB 에서 "이미지 필요" 페이지(각 DB 최대 `_DEFAULT_BATCH_LIMIT`)
    fetch 후, §19.1 멱등성 filter (`get_logged_page_ids`) 적용해 이미 처리된
    페이지 제거. GitHub Actions fetch job 이 stdout JSON 을 캡처해 matrix
    include 로 expose.

    반환 형식: `[{"page_id": "<id>", "source": "블로그"|"웹"}, ...]`.
    """
    log_db_id = os.environ["NOTION_DB_LOG"].strip()
    blog_db_id = os.environ["NOTION_DB_BLOG"].strip()
    web_db_id = os.environ["NOTION_DB_WEB"].strip()

    logged_ids = await get_logged_page_ids(log_db_id, limit=100)
    logger.info("list 모드: 로그 이력 페이지 %d건 로드 — skip 후보", len(logged_ids))

    out: list[dict[str, str]] = []
    for db_id, source in ((blog_db_id, "블로그"), (web_db_id, "웹")):
        pages = await fetch_pages_by_status(
            db_id, status="이미지 필요", limit=_DEFAULT_BATCH_LIMIT,
        )
        for page in pages:
            page_id = page["id"]
            if norm_uuid(page_id) in logged_ids:
                logger.info(
                    "[%s] page %s 처리 이력 발견 — list 제외 (§19.1).",
                    source, page_id,
                )
                continue
            out.append({"page_id": page_id, "source": source})
        logger.info("[%s] '이미지 필요' 페이지 %d건 (필터 후 %d건)",
                    source, len(pages), sum(1 for p in out if p["source"] == source))

    return out


async def process_single_page(
    page_id: str, source: Literal["블로그", "웹"],
) -> PageResult | None:
    """matrix fan-out 용 `--page-id` 핸들러 (cell 당 1회 호출).

    process_database 의 페이지 루프 1회차와 같은 가드 적용:
      - §19.1 멱등성 (race condition / 재시도 케이스 대비 재확인)
      - §19.9 page-level try/except (예외는 GHA cell 빨간 X 로 surface)
      - 자체 RunBudget(`PER_RUN_CAP_USD`) — cell 당 cap 으로 작동
      - PER_PAGE_CAP_USD 는 run_for_page 내부에서 슬롯 단위로 적용

    이미 로그된 페이지면 skip 으로 None 반환 (job exit 0).
    """
    log_db_id = os.environ["NOTION_DB_LOG"].strip()

    logged_ids = await get_logged_page_ids(log_db_id, limit=100)
    if norm_uuid(page_id) in logged_ids:
        logger.warning(
            "[%s] page %s 처리 이력 발견 — skip (§19.1 멱등성). "
            "재처리 원하면 로그 row + 기존 image block 수동 제거 필요.",
            source, page_id,
        )
        return None

    run_budget = RunBudget(cap_usd=PER_RUN_CAP_USD)
    logger.info("=== single-page run 시작 — cap $%.2f ===", PER_RUN_CAP_USD)

    r = await run_for_page(page_id, source, log_db_id)
    run_budget.add(r.cost_usd)
    logger.info(
        "[%s] page %s 완료 — 슬롯 %d/%d, $%.4f (cell 누적 $%.4f)",
        source, page_id, r.slots_passed, r.slots_total, r.cost_usd,
        run_budget.spent_usd,
    )
    return r


async def main() -> None:
    """cron / workflow_dispatch 진입점 — matrix fan-out only (v1.8 Phase 4.2).

    2 모드 (sweep 폐기, 2026-05-15 사용자 컨펌 + plan §14.9 §5):
      - `--mode list`: 페이지 목록 JSON 을 stdout 출력 (matrix fan-out fetch job).
      - `--page-id ID --source SRC`: 단일 페이지 처리 (matrix process job cell).

    인자 없음 → error. 이전 sweep 진입점은 v1.7.5-plan 시점에 cron.yml 2-step
    fan-out 으로 이미 대체되어 사용 사례 없음. `process_database` 함수 본체는
    backwards compat 유지 (외부 호출자 가능성).

    drift 처리 룰 — plan §3 / §12.8.3 / §14.9 §5 / Changelog v1.7.5-plan / v1.8.0-plan.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,  # stdout 은 list 모드 JSON 전용 — 로그 섞이지 않게.
    )

    # .env 지원 — GitHub Actions 는 secrets 로 환경변수 주입, 로컬은 .env 사용.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(
        description=(
            "cron / matrix fan-out 진입점. "
            "사용: '--mode list' (matrix fetch) 또는 '--page-id ID --source SRC' (process cell)."
        ),
    )
    parser.add_argument(
        "--mode", choices=["list"], default=None,
        help="list: '이미지 필요' 페이지(멱등성 필터 적용)를 JSON 으로 stdout 출력.",
    )
    parser.add_argument(
        "--page-id", default=None,
        help="단일 페이지 처리. --source 와 함께 사용.",
    )
    parser.add_argument(
        "--source", choices=["블로그", "웹"], default=None,
        help="단일 페이지 처리 시 페이지 출처 DB.",
    )
    args = parser.parse_args()

    # 분기 1 — list 모드 (matrix fetch job)
    if args.mode == "list":
        pages = await list_pending_pages()
        # ensure_ascii=True — Windows 콘솔 CP949 / Linux UTF-8 둘 다 안전 (한글 → \uXXXX 이스케이프).
        # GitHub Actions `fromJSON` 은 표준 JSON 파서라 이스케이프 자동 복원.
        sys.stdout.buffer.write(json.dumps(pages, ensure_ascii=True).encode("ascii") + b"\n")
        return

    # 분기 2 — 단일 페이지 (matrix process job cell)
    if args.page_id:
        if not args.source:
            parser.error("--page-id 사용 시 --source 필수 (블로그|웹).")
        await process_single_page(args.page_id, args.source)
        return

    # 인자 없음 → error (sweep 폐기, Phase 4.2)
    parser.error(
        "모드 미지정: '--mode list' (페이지 목록) 또는 "
        "'--page-id ID --source SRC' (단일 페이지) 필요. "
        "전체 sweep 은 v1.8 Phase 4.2 에서 폐기됨 (cron.yml 2-step fan-out 사용)."
    )


if __name__ == "__main__":
    asyncio.run(main())
