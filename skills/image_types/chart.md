# chart

## When to use
본문에 시계열 추이, 분포, 비율, 카테고리 비교 데이터.

## Generation method
Template (HTML + Chart.js + Playwright) — `tools/render/chart_render.py`

## Sub-types
- `line` : 시계열 추이 — `render_chart_line` (Phase 1)
- `bar`  : 카테고리 비교 (연도별 건수, 지역별 비율 등) — `render_chart_bar` (Phase 2)
- `donut`: 분포/구성비 (전체 합에서 각 슬라이스 비율, 중앙 hole) — `render_chart_donut` (Phase 2)
- `pie`  : 분포/구성비 (donut과 동일, 중앙 채움) — `render_chart_pie` (Phase 2)

## Card size (plan §4 v1.2)
default — `width: 1200px` 고정, `height: auto`.
- Chart.js canvas 자체는 약 480px (시각 비율 일관성 — best practice)
- 카드 전체는 제목+canvas+출처 합산해 700~800px 범위에 수렴
- min_height: 700px / max_height: 800px (image_review가 자동 검증)
- 다른 카드(simple_table 등)와 달리 차트는 사실상 거의 fixed — 차트 비율 일관성 유지가 표보다 더 중요.

## Variables (line/bar — 동일 shape: `ChartLineData` / `ChartBarData`)
- `title` : str — **필수**. 본문 인접 H2/H3 그대로. (절대 룰 #1)
- `labels` : list[str]
- `values` : list[float]
- `point_labels` : list[str] (각 포인트/막대 위 표시. 단위 포함 권장)
- `sub_labels` : list[str] | None (x축 2행 라벨 — 긴 라벨 줄바꿈)
- `y_unit` : str | None ("(%)", "(억 원)" 등)
- `source` : str | None (통계는 표기 권장)
- `y_min` / `y_max` : float | None

### line vs bar 선택
- **line**: 본문에 연속된 시계열 (연도/월/분기 → 값). x축이 순서 의미 있음.
- **bar**: 카테고리 비교 (지역/유형/연도 카테고리 → 값). 순서 의미 없거나 약함.
- 같은 데이터를 둘 다 표현 가능하면 — 연속 추이는 line, 이산 비교는 bar.

## Variables (donut/pie — `ChartDonutData`)
- `title` : str — **필수**.
- `labels` : list[str] — slice 이름 (2-6개).
- `values` : list[float] — slice 값 (Chart.js가 자동 % 환산). 음수/합 0 X.
- `point_labels` : list[str] | None — slice 표시 텍스트 (예: "1,240건"). None이면 raw value 표시.
- `source` : str | None.

### donut vs pie 선택
- **donut**: 중앙 hole 있음 — 더 현대적 톤. 기본 권장.
- **pie**: 중앙 채움 — 전통적, 슬라이스 비교 더 명확.
- 본문이 "구성비" 강조 → donut. "비율 자체"가 중요 → pie. 보통 donut으로 가도 OK.

### 분포 vs 비교 선택 (donut/pie vs bar)
- **donut/pie**: 전체 합 = 100% (구성비 시각화). 카테고리 5-6개 이하.
- **bar**: 카테고리 간 절대값 비교 (서로 합산 의미 없음).
- 같은 데이터를 둘 다 표현 가능 — "이게 전체의 %냐"가 핵심이면 donut/pie, "어디가 큰가"가 핵심이면 bar.

## Style (donut/pie — `templates/chart_donut.html`)
- 좌측 chart canvas 480x480 + 우측 범례 list 좌우 분할.
- 컬러: `chart-mono-1~5` (brand wine-magenta monochromatic) + `chart-mono-other` (기타 카테고리는 neutral).
- 범례: 28px swatch + 40px label + 40px value (neutral.500).
- '기타'/'그 외'/'etc' label은 자동으로 neutral 톤 (brand 톤 강조 X).

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
