"""chart_line 렌더 wrapper + 데이터 검증 게이트.

데이터 무결성은 AGENT_GUIDE 절대 룰 #1. 본문 → 슬롯 데이터 변환 단에서 LLM이 추출한
값을 chart_line 템플릿에 넘기기 전 형식적 일관성을 한 번 더 검증한다.

검증 책임 분담:
  - 여기 (chart_render): 형식 검증 (길이 일치, 포인트 개수, 라벨 길이)
  - prompt_review (skills/meta): 본문 일치 검증 (숫자 1:1, 변호사법 §23)

Phase 1은 line만. bar/donut/pie는 Phase 2에서 sub-type별 wrapper 추가.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from tools.render.template_render import CardSize, render_template

logger = logging.getLogger(__name__)

LABEL_WRAP_THRESHOLD = 12  # 1줄 라벨 글자 수 한계 (한글 기준). 초과 시 자동 줄바꿈.
LABEL_WARN_THRESHOLD = 14  # 그 이상이면 시각 잘림 위험 — sub_labels/point_labels에 적용.
MIN_POINTS = 2             # plan §7.3: 1개면 stat_highlight로 폴백 (Phase 1엔 미구현).


class ChartDataError(ValueError):
    """차트 데이터 검증 실패. orchestrator가 슬롯 단위로 catch + 로그에 기록."""


@dataclass(frozen=True)
class ChartLineData:
    """chart_line 템플릿 입력. dataclass라 호출자가 명시적으로 fields를 채워야 함.

    title        : 차트 제목 (h2 38px).
    labels       : x축 1행 라벨 (보통 연도). 길이 = N.
    values       : y값 (숫자). 길이 = N.
    point_labels : 각 포인트 위 표시 텍스트. 길이 = N.
                   caller가 단위/포맷팅 책임 (예: "44.6", "638억 원").
    sub_labels   : x축 2행 라벨 (옵션, 예: 개최도시명). 길이 = N 또는 None.
    y_unit       : y축 단위 캡션 ("(%)", "(억 원)" 등). 옵션.
    source       : 출처 문구 ("출처: ..."). 옵션이지만 통계/차트는 표기 권장.
    y_min, y_max : y축 범위 강제. 옵션 (None이면 Chart.js auto).
    """

    title: str
    labels: list[str]
    values: list[float]
    point_labels: list[str]
    sub_labels: list[str] | None = None
    y_unit: str | None = None
    source: str | None = None
    y_min: float | None = None
    y_max: float | None = None

    # internal: 검증 단계에서 자동 줄바꿈 처리된 labels 보관
    _resolved_labels: list[str] | None = field(default=None, init=False, repr=False)


def validate_chart_line(d: ChartLineData) -> ChartLineData:
    """형식 검증 + 라벨 자동 줄바꿈. 검증 통과 시 (필요하면 정규화된) data 반환.

    실패 사유:
      - 포인트 개수 < 2  (plan §7.3 — Phase 1엔 폴백 카드 없음)
      - labels/values/point_labels 길이 불일치
      - sub_labels 길이 ≠ labels (sub_labels 있을 때만)
    경고 (raise X):
      - sub_labels/point_labels 14자 초과 — 잘림 가능성
    자동 처리:
      - sub_labels 없는데 labels 12자 초과 → 공백/구분자 기준으로 split해 sub_labels로 보냄.
    """
    n = len(d.labels)
    if n < MIN_POINTS:
        raise ChartDataError(
            f"chart_line은 최소 {MIN_POINTS}개 포인트 필요 (받은 값: {n}). "
            f"1개면 stat_highlight로 폴백 (Phase 1엔 미구현)."
        )
    if len(d.values) != n:
        raise ChartDataError(f"values 길이({len(d.values)}) ≠ labels 길이({n})")
    if len(d.point_labels) != n:
        raise ChartDataError(f"point_labels 길이({len(d.point_labels)}) ≠ labels 길이({n})")
    if d.sub_labels is not None and len(d.sub_labels) != n:
        raise ChartDataError(f"sub_labels 길이({len(d.sub_labels)}) ≠ labels 길이({n})")

    # 자동 줄바꿈: labels 12자 초과 + sub_labels 미지정 → 공백/구분자 기준 split해서 보냄
    if d.sub_labels is None and any(len(label) > LABEL_WRAP_THRESHOLD for label in d.labels):
        primaries: list[str] = []
        subs: list[str] = []
        for label in d.labels:
            if len(label) <= LABEL_WRAP_THRESHOLD:
                primaries.append(label)
                subs.append("")
                continue
            head, tail = _split_label(label)
            primaries.append(head)
            subs.append(tail)
        # 모두 빈 sub면 sub_labels 자체를 None 유지
        new_subs: list[str] | None = subs if any(subs) else None
        # frozen dataclass라 새 인스턴스 반환
        d = ChartLineData(
            title=d.title,
            labels=primaries,
            values=d.values,
            point_labels=d.point_labels,
            sub_labels=new_subs,
            y_unit=d.y_unit,
            source=d.source,
            y_min=d.y_min,
            y_max=d.y_max,
        )

    # 경고 (raise X)
    for i, lbl in enumerate(d.sub_labels or []):
        if len(lbl) > LABEL_WARN_THRESHOLD:
            logger.warning("sub_labels[%d] %d자 (%d 초과) — 시각 잘림 가능: %r",
                           i, len(lbl), LABEL_WARN_THRESHOLD, lbl)
    for i, lbl in enumerate(d.point_labels):
        if len(lbl) > LABEL_WARN_THRESHOLD:
            logger.warning("point_labels[%d] %d자 (%d 초과) — 시각 잘림 가능: %r",
                           i, len(lbl), LABEL_WARN_THRESHOLD, lbl)

    return d


def _split_label(label: str) -> tuple[str, str]:
    """긴 라벨을 (head, tail) 두 부분으로 자른다. 공백/구분자 우선, 없으면 중간점."""
    # 우선순위: 공백 > '-' > '_' > 가운데 인덱스
    midpoint = len(label) // 2
    for sep in (" ", "-", "_"):
        if sep in label:
            # midpoint에 가장 가까운 sep 위치
            best = min(
                (i for i, c in enumerate(label) if c == sep),
                key=lambda i: abs(i - midpoint),
            )
            return label[:best].strip(), label[best + 1:].strip()
    return label[:midpoint], label[midpoint:]


async def render_chart_line(
    data: ChartLineData,
    out_path: Path,
    size: str | CardSize = "default",
) -> Path:
    """chart_line 카드를 PNG로 렌더. 검증 통과한 데이터만 템플릿에 주입."""
    d = validate_chart_line(data)
    return await render_template(
        "chart_line",
        dict(
            title=d.title,
            y_unit=d.y_unit,
            labels=d.labels,
            sub_labels=d.sub_labels,
            values=d.values,
            point_labels=d.point_labels,
            source=d.source,
            y_min=d.y_min,
            y_max=d.y_max,
        ),
        out_path,
        size=size,
    )
