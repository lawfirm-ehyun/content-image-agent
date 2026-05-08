# chart

## When to use
본문에 시계열 추이, 분포, 비율, 카테고리 비교 데이터.

## Generation method
Template (HTML + Chart.js + Playwright) — `tools/render/chart_render.py`

## Sub-types
- `line` : 시계열 추이 ← **Phase 1 활성** (`render_chart_line`)
- `bar` / `donut` / `pie` : Phase 2에서 점진 추가

## Card size (plan §4 v1.2)
default — `width: 1200px` 고정, `height: auto`.
- Chart.js canvas 자체는 약 480px (시각 비율 일관성 — best practice)
- 카드 전체는 제목+canvas+출처 합산해 700~800px 범위에 수렴
- min_height: 700px / max_height: 800px (image_review가 자동 검증)
- 다른 카드(simple_table 등)와 달리 차트는 사실상 거의 fixed — 차트 비율 일관성 유지가 표보다 더 중요.

## Variables (line — `ChartLineData`)
- `title` : str — **필수**. 본문 인접 H2/H3 그대로. (절대 룰 #1)
- `labels` : list[str]
- `values` : list[float]
- `point_labels` : list[str] (각 포인트 위 표시. 단위 포함 권장)
- `sub_labels` : list[str] | None (x축 2행 라벨)
- `y_unit` : str | None ("(%)", "(억 원)" 등)
- `source` : str | None (통계는 표기 권장)
- `y_min` / `y_max` : float | None

## Style (`templates/chart_line.html`)
- 카드 배경 neutral.100, 라인 brand.primary 4px, 포인트 8px
- 포인트 라벨 28px bold neutral.900
- x/y 축 라벨 24px neutral.500
- 출처 20px neutral.400 bottom-left

## Reference
- `reference_library/chart/infographic.jpg`
- `reference_library/chart/tmp_kor_03.png`

## Data validation (CRITICAL — `chart_render.py`가 강제)
- 본문 명시 숫자 1:1 매칭 (slot_selection 단)
- 최소 2 포인트 (1개면 stat_highlight 폴백 — Phase 1 미완)
- labels/values/point_labels 길이 일치
- labels 12자 초과 + sub_labels 미지정 → 자동 줄바꿈

## Quality criteria
- [ ] 데이터 라벨 본문과 1:1
- [ ] 출처 표기됨
- [ ] brand.primary는 메인 라인에만
- [ ] 변호사법 §23 금지 표현 없음
