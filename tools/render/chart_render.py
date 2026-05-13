"""chart 렌더 wrapper + 데이터 검증 게이트.

데이터 무결성은 AGENT_GUIDE 절대 룰 #1. 본문 → 슬롯 데이터 변환 단에서 LLM이 추출한
값을 chart 템플릿에 넘기기 전 형식적 일관성을 한 번 더 검증한다.

검증 책임 분담:
  - 여기 (chart_render): 형식 검증 (길이 일치, 포인트 개수, 라벨 길이)
  - prompt_review (skills/meta): 본문 일치 검증 (숫자 1:1, 변호사법 §23)

Week 3a (plan §12.2 v1.7.3): 4 sub-type 통합. 외부 API는 `ChartSpec` + `render_chart` 단일.
ChartLineData/ChartDonutData/validate_chart_line/donut은 ChartSpec path 내부 재사용 (외부 X).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

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


# === donut / pie sub-type — distribution slice 검증 + 색 매핑 =================
# 분포 시각화 — slice별 비율. label + value 옆 범례 형식.
# donut: 중앙 hole 있음 (cutout 55%) / pie: 채워짐 (cutout 0). master_chart Jinja 분기.
# 컬러는 monochromatic chart-mono palette (brand wine-magenta 변형) — _base.css 토큰.

# CSS 토큰 미러 — Jinja에 inline 전달용. _base.css와 1:1 동기.
_CHART_MONO_COLORS = ["#7d1239", "#a91c51", "#c2456f", "#d56e8e", "#e498ad"]
_CHART_MONO_OTHER = "#a1a1aa"

MAX_DISTRIBUTION_SLICES = 6   # 5 brand 톤 + 1 기타. 6 초과면 시각 부담 + 색 부족.
MIN_DISTRIBUTION_SLICES = 2


@dataclass(frozen=True)
class ChartDonutData:
    """chart_donut / chart_pie 공용 입력. 단순 분포 (label → value).

    title        : 차트 제목.
    labels       : slice 이름 리스트 (예: ["이혼", "상속", "형사"]).
    values       : slice 값 (숫자, % 자동 계산). labels와 길이 일치.
    point_labels : slice 표시 텍스트 (예: ["1,240건", ...]). 옵션 — 없으면 자동 %.
    source       : 출처.
    """

    title: str
    labels: list[str]
    values: list[float]
    point_labels: list[str] | None = None
    source: str | None = None


def validate_chart_donut(d: ChartDonutData) -> ChartDonutData:
    """donut/pie 형식 검증. 길이 일치 + slice 개수 + 음수/0 합."""
    n = len(d.labels)
    if n < MIN_DISTRIBUTION_SLICES:
        raise ChartDataError(
            f"donut/pie는 최소 {MIN_DISTRIBUTION_SLICES} slice 필요 (받은 값: {n})"
        )
    if n > MAX_DISTRIBUTION_SLICES:
        raise ChartDataError(
            f"donut/pie는 최대 {MAX_DISTRIBUTION_SLICES} slice 권장 (받은 값: {n}). "
            "초과 카테고리는 '기타'로 합산 또는 슬롯 분할."
        )
    if len(d.values) != n:
        raise ChartDataError(f"values 길이({len(d.values)}) ≠ labels 길이({n})")
    if d.point_labels is not None and len(d.point_labels) != n:
        raise ChartDataError(
            f"point_labels 길이({len(d.point_labels)}) ≠ labels 길이({n})"
        )
    if any(v < 0 for v in d.values):
        raise ChartDataError("donut/pie values에 음수 포함 — 분포 시각화 부적합")
    if sum(d.values) <= 0:
        raise ChartDataError("donut/pie values 합이 0 이하 — 분포 시각화 불가")
    return d


def _assign_colors(labels: list[str]) -> list[str]:
    """labels에 mono palette 색 매핑. 마지막 라벨이 '기타' 류면 mono_other (neutral) 적용.

    '기타'/'그 외'/'others' 등 잔여 카테고리는 brand 톤 X — 의미 신호 (강조 X).
    """
    other_keywords = {"기타", "그 외", "그외", "etc", "others", "other"}
    colors: list[str] = []
    for i, label in enumerate(labels):
        if label.strip().lower() in other_keywords:
            colors.append(_CHART_MONO_OTHER)
        else:
            # brand 톤 5개 순환 — slice 개수가 5 이하면 mono-1부터 순서대로
            colors.append(_CHART_MONO_COLORS[i % len(_CHART_MONO_COLORS)])
    return colors


# Week 3b 색상 강조 (plan §12.2) — donut/pie용. brand-primary는 chart_mono-2.
_EMPHASIS_BRAND = "#a91c51"  # = _CHART_MONO_COLORS[1] = --brand-primary


def _apply_emphasis_donut(colors: list[str], emphasis_index: int | None) -> list[str]:
    """donut/pie 색상 강조 — emphasis_index slice만 brand-primary, 나머지는 chart_mono_other (neutral).

    None이면 _assign_colors() 결과 그대로 반환 (Week 3a path = byte-identity).
    legend swatch와 chart slice가 같은 colors 배열을 공유하므로 시각 일치 보장.
    """
    if emphasis_index is None:
        return colors
    return [
        _EMPHASIS_BRAND if i == emphasis_index else _CHART_MONO_OTHER
        for i in range(len(colors))
    ]


# === Week 3a (plan §12.2) — ChartSpec 단일 스키마 + master_chart 통합 path ======
# 옛 ChartLineData/ChartDonutData/validate_chart_line/donut 는 ChartSpec path에서
# 형식 검증 재사용. 외부에서 직접 쓰지 X.

ChartSubType = Literal["line", "bar", "donut", "pie"]
ChartOrientation = Literal["vertical", "horizontal"]


@dataclass(frozen=True)
class ChartSpec:
    """master_chart.html 입력 — 4 sub_type 통합 단일 스키마.

    sub_type별 의미:
      - line/bar: title/labels/values/point_labels 필수. sub_labels/y_unit/y_min/y_max 옵션.
                  colors/cutout은 사용 X (None).
      - donut/pie: title/labels/values 필수. point_labels None이면 raw value 표시.
                   sub_labels/y_unit/y_min/y_max 사용 X.

    Week 3b (plan §12.2) — 2축 parametric 추가:
      - orientation: 'vertical'(default) | 'horizontal'. **bar/line만** 의미 있음.
                     donut/pie는 원형 DOM이라 무시 (값 받아도 적용 X).
      - emphasis_index: int | None. **4 sub_type 공통.** None = 강조 없음 (Week 3a 동작).
                        값이면 해당 인덱스만 brand-primary, 나머지는 desaturated.
                        시각 표현은 **색상 강조 1개**로 고정 (라벨 강조/explode 등은 Week 4 후).
    """

    sub_type: ChartSubType
    title: str
    labels: list[str]
    values: list[float]
    point_labels: list[str] | None = None
    # line/bar 전용 —— donut/pie는 None 고정
    sub_labels: list[str] | None = None
    y_unit: str | None = None
    y_min: float | None = None
    y_max: float | None = None
    # 공통
    source: str | None = None
    # Week 3b parametric — default = Week 3a byte-identity 동작
    orientation: ChartOrientation = "vertical"
    emphasis_index: int | None = None


def _spec_to_line_bar(spec: ChartSpec) -> ChartLineData:
    """ChartSpec(line/bar) → ChartLineData (validate_chart_line 재사용 위해)."""
    if spec.point_labels is None:
        raise ChartDataError(
            f"chart sub_type={spec.sub_type}은 point_labels 필수 (None 받음)"
        )
    return ChartLineData(
        title=spec.title,
        labels=spec.labels,
        values=spec.values,
        point_labels=spec.point_labels,
        sub_labels=spec.sub_labels,
        y_unit=spec.y_unit,
        source=spec.source,
        y_min=spec.y_min,
        y_max=spec.y_max,
    )


def _line_bar_to_spec(d: ChartLineData, sub_type: ChartSubType) -> ChartSpec:
    """validate 후 ChartLineData → ChartSpec (sub_labels 자동 줄바꿈 결과 반영)."""
    return ChartSpec(
        sub_type=sub_type,
        title=d.title,
        labels=d.labels,
        values=d.values,
        point_labels=d.point_labels,
        sub_labels=d.sub_labels,
        y_unit=d.y_unit,
        source=d.source,
        y_min=d.y_min,
        y_max=d.y_max,
    )


def _spec_to_donut(spec: ChartSpec) -> ChartDonutData:
    """ChartSpec(donut/pie) → ChartDonutData."""
    return ChartDonutData(
        title=spec.title,
        labels=spec.labels,
        values=spec.values,
        point_labels=spec.point_labels,
        source=spec.source,
    )


def _validate_parametric(spec: ChartSpec) -> None:
    """Week 3b parametric 필드 검증 — orientation/emphasis_index 경계.

    - orientation: donut/pie에 'horizontal' 지정해도 무시 (raise X, 경고만).
    - emphasis_index: 0 ≤ i < len(values). 범위 밖이면 raise.
    """
    if spec.sub_type in ("donut", "pie") and spec.orientation != "vertical":
        # default 외 값을 줘도 master_chart는 donut/pie 분기에서 적용 안 함.
        # data error는 아니므로 경고만.
        logger.warning(
            "ChartSpec sub_type=%s에 orientation=%r 지정 — donut/pie 원형 DOM이라 무시됨.",
            spec.sub_type, spec.orientation,
        )
    if spec.emphasis_index is not None:
        if not (0 <= spec.emphasis_index < len(spec.values)):
            raise ChartDataError(
                f"emphasis_index={spec.emphasis_index}은 values 길이 {len(spec.values)} 범위 밖"
            )


def validate_chart(spec: ChartSpec) -> ChartSpec:
    """ChartSpec 형식 검증 + line/bar의 라벨 자동 줄바꿈. sub_type별 분기."""
    _validate_parametric(spec)
    if spec.sub_type in ("line", "bar"):
        line = _spec_to_line_bar(spec)
        line = validate_chart_line(line)
        # Week 3b: validate_chart_line이 sub_labels 줄바꿈으로 새 인스턴스를 만들 수 있으므로
        # parametric 필드를 함께 복원.
        return ChartSpec(
            sub_type=spec.sub_type,
            title=line.title,
            labels=line.labels,
            values=line.values,
            point_labels=line.point_labels,
            sub_labels=line.sub_labels,
            y_unit=line.y_unit,
            y_min=line.y_min,
            y_max=line.y_max,
            source=line.source,
            orientation=spec.orientation,
            emphasis_index=spec.emphasis_index,
        )
    if spec.sub_type in ("donut", "pie"):
        validate_chart_donut(_spec_to_donut(spec))
        return spec
    raise ChartDataError(f"unknown sub_type={spec.sub_type!r}")


async def render_chart(
    spec: ChartSpec,
    out_path: Path,
    size: str | CardSize = "default",
) -> Path:
    """master_chart.html로 렌더. sub_type별 Jinja 분기로 4 sub-type 단일 통합 (plan §12.2).

    회귀 가드(plan §12.4 가드 2 (b)): tests/fixtures/v1_6_4_chart_baseline/*.png SHA256과 동일해야 함.
    parity 검증은 `scripts/_spike_chart_parity.py`.
    """
    spec = validate_chart(spec)
    variables: dict = dict(
        sub_type=spec.sub_type,
        title=spec.title,
        labels=spec.labels,
        values=spec.values,
        point_labels=spec.point_labels,
        source=spec.source,
        # line/bar 전용 — donut/pie 분기에선 사용 X지만 Jinja StrictUndefined 대비 명시 전달
        sub_labels=spec.sub_labels,
        y_unit=spec.y_unit,
        y_min=spec.y_min,
        y_max=spec.y_max,
        # Week 3b parametric — default(vertical, None)은 master_chart에서 Chart.js config에
        # 키 추가 X path로 분기되어 byte-identity 유지.
        orientation=spec.orientation,
        emphasis_index=spec.emphasis_index,
    )
    if spec.sub_type in ("donut", "pie"):
        # Week 3b: emphasis_index가 None이면 _assign_colors 그대로 (byte-identity).
        # 값이면 emphasis slice = brand-primary, 나머지 = chart_mono_other.
        colors = _assign_colors(spec.labels)
        variables["colors"] = _apply_emphasis_donut(colors, spec.emphasis_index)
        variables["cutout"] = "55%" if spec.sub_type == "donut" else 0
    else:
        # line/bar 분기에서 사용 X — StrictUndefined 회피용 None
        variables["colors"] = None
        variables["cutout"] = None
    return await render_template("master_chart", variables, out_path, size=size)
